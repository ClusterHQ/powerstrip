from ._config import PluginConfiguration
from ._parser import EndpointParser
from treq.client import HTTPClient
from twisted.internet import reactor, defer
from twisted.internet.interfaces import IHalfCloseableProtocol
from twisted.python import log
from twisted.python.failure import Failure
from twisted.web import server, proxy
from twisted.web.client import Agent
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET
from urllib import quote as urlquote
from zope.interface import directlyProvides
import StringIO
import json
import treq
import urlparse

class NoPostHooks(Exception):
    """
    Do not run any post-hooks, because of an incompatible Docker response type
    (streaming/hijacked or chunked).
    """

class DockerProxyClient(proxy.ProxyClient):
    """
    An HTTP proxy which knows how to break HTTP just right so that Docker
    stream (attach/events) API calls work.

    self.http: A boolean which reflects whether the connection is in HTTP mode
        (True) or "hijack" mode (False). See
        https://docs.docker.com/reference/api/docker_remote_api_v1.14/#32-hijacking
    """

    http = True
    _streaming = False
    _listener = None
    _responsePartBuffer = b""

    def _fireListener(self, result):
        if self._listener is not None:
            d = self._listener
            self._listener = None
            d.callback(result)

    def registerListener(self, d):
        """
        Register a one shot listener, which can fire either with:
           * Failure(NoPostHooks()) if the proxy is handling comms back to
             the client (streaming/chunked modes), or
           * A tuple containing the (response, code, content-type).
        """
        self._listener = d

    def dataReceived(self, data):
        # print "DATA!", repr(data)
        return proxy.ProxyClient.dataReceived(self, data)

    def handleHeader(self, key, value):
        # print key, "=>", value
        if key.lower() == "content-type" and value == "application/vnd.docker.raw-stream":
            def loseWriteConnectionReason(reason):
                # discard the reason, for compatibility with readConnectionLost
                self.transport.loseWriteConnection()
            self.father.transport.readConnectionLost = loseWriteConnectionReason
            directlyProvides(self.father.transport, IHalfCloseableProtocol)
            self.http = False
            self.father.transport.write(
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/vnd.docker.raw-stream\r\n"
                "\r\n")
            self._streaming = True
            self._fireListener(Failure(NoPostHooks()))
        # XXX Turns out, the build endpoint doesn't actually used chunked
        # encoding. It just sends some JSON documents which maybe happen to
        # line up with packet boundaries. So the following if statement is both
        # untested and potentially never triggered in practice. :(
        if key.lower() == "transfer-encoding" and value == "chunked":
            self._streaming = True
            self._fireListener(Failure(NoPostHooks()))
        return proxy.ProxyClient.handleHeader(self, key, value)


    def handleResponsePart(self, buffer):
        """
        If we're not in streaming mode, buffer the response part(s).
        """
        if self._streaming:
            proxy.ProxyClient.handleResponsePart(self, buffer)
        else:
            # print "BUFFER!", buffer
            self._responsePartBuffer += buffer


    def handleResponseEnd(self):
        """
        If we're completing a chunked response, up-call to handle it like a
        regular reverse proxy.

        If we're completing a non-chunked response, fire the post-hooks.

        If we're completing a hijacked response, pass through the connection
        close.
        """
        if self.http:
            if self._streaming:
                return proxy.ProxyClient.handleResponseEnd(self)
            else:
                contentType = self.father.responseHeaders.getRawHeaders("content-type")
                if contentType:
                    contentType = contentType[0]
                else:
                    contentType = None
                body = self._responsePartBuffer
                self._fireListener(
                        {"PowerstripProtocolVersion": 1,
                         "ModifiedServerResponse":
                            {"Body": body,
                             "Code": self.father.code,
                             "ContentType": contentType}})
        else:
            self.father.transport.loseConnection()


    def rawDataReceived(self, data):
        if self.http:
            return proxy.ProxyClient.rawDataReceived(self, data)
        self.father.transport.write(data)



class DockerProxyClientFactory(proxy.ProxyClientFactory):
    protocol = DockerProxyClient
    _listener = None
    def onCreate(self, d):
        self._listener = d

    def _fireListener(self, result):
        if self._listener is not None:
            d = self._listener
            self._listener = None
            d.callback(result)

    def buildProtocol(self, addr):
        client = proxy.ProxyClientFactory.buildProtocol(self, addr)
        self._fireListener(client)
        return client



class DockerProxy(proxy.ReverseProxyResource):
    proxyClientFactoryClass = DockerProxyClientFactory

    def __init__(self, dockerAddr=None, dockerPort=None, dockerSocket=None,
            path='', reactor=reactor, config=None):
        """
        A docker proxy resource which knows how to connect to real Docker
        daemon either via socket (dockerSocket specified) or address + port for
        TCP connection (dockerAddr + dockerPort specified).
        """
        if config is None:
            # Try to get the configuration from the default place on the
            # filesystem.
            self.config = PluginConfiguration()
        else:
            self.config = config
        self.config.read_and_parse()
        self.parser = EndpointParser(self.config)
        Resource.__init__(self)
        self.host = dockerAddr
        self.port = dockerPort
        self.socket = dockerSocket
        self.path = path
        self.reactor = reactor
        proxy.ReverseProxyResource.__init__(self, dockerAddr, dockerPort, path, reactor) # NB dockerAddr is not actually used
        self.agent = Agent(reactor) # no connectionpool
        self.client = HTTPClient(self.agent)


    def render(self, request, reactor=reactor):
        # We are processing a leaf request.
        # Get the original request body from the client.
        skipPreHooks = False
        if request.requestHeaders.getRawHeaders('content-type') == ["application/json"]:
            originalRequestBody = request.content.read()
            request.content.seek(0) # hee hee
        elif request.requestHeaders.getRawHeaders('content-type') == ["application/tar"]:
            # XXX We can't JSON encode binary data.
            skipPreHooks = True
            originalRequestBody = None
        else:
            originalRequestBody = None
        preHooks = []
        postHooks = []
        d = defer.succeed(None)
        for endpoint in self.parser.match_endpoint(request.method, request.uri.split("?")[0]):
            # It's possible for a request to match multiple endpoint
            # definitions.  Order of matched endpoint is not defined in
            # that case.
            adapters = self.config.endpoint(endpoint)
            preHooks.extend(adapters.pre)
            postHooks.extend(adapters.post)
        def callPreHook(result, hookURL):
            if result is None:
                newRequestBody = originalRequestBody
            else:
                newRequestBody = result["ModifiedClientRequest"]["Body"]
            return self.client.post(hookURL, json.dumps({
                        "PowerstripProtocolVersion": 1,
                        "Type": "pre-hook",
                        "ClientRequest": {
                            "Method": request.method,
                            "Request": request.uri,
                            "Body": newRequestBody,
                            # XXX This would need a ContentType header... if we
                            # were to support non-JSON POST bodies, like build
                            # contexts.
                        }
                    }), headers={'Content-Type': ['application/json']})
        if not skipPreHooks:
            for preHook in preHooks:
                hookURL = self.config.adapter_uri(preHook)
                d.addCallback(callPreHook, hookURL=hookURL)
                d.addCallback(treq.json_content)
        def doneAllPrehooks(result):
            # Finally pass through the request to actual Docker.  For now we
            # mutate request in-place in such a way that ReverseProxyResource
            # understands it.
            if result is not None:
                requestBody = b""
                bodyFromAdapter = result["ModifiedClientRequest"]["Body"]
                if bodyFromAdapter is not None:
                    requestBody = bodyFromAdapter.encode("utf-8")
                request.content = StringIO.StringIO(requestBody)
                request.requestHeaders.setRawHeaders(b"content-length",
                        [str(len(requestBody))])
            ###########################
            # The following code is copied from t.w.proxy.ReverseProxy so that
            # clientFactory reference can be kept.
            if not self.socket:
                if self.port == 80:
                    host = self.host
                else:
                    host = "%s:%d" % (self.host, self.port)
                request.requestHeaders.setRawHeaders(b"host", [host])
            request.content.seek(0, 0)
            qs = urlparse.urlparse(request.uri)[4]
            if qs:
                rest = self.path + '?' + qs
            else:
                rest = self.path
            allRequestHeaders = request.getAllHeaders()
            if ("transfer-encoding" in allRequestHeaders
                    and allRequestHeaders["transfer-encoding"] == "chunked"):
                del allRequestHeaders["transfer-encoding"]
            # XXX Streaming the contents of the request body into memory could
            # cause OOM issues for large build contexts POSTed through
            # powerstrip.
            body = request.content.read()
            allRequestHeaders["content-length"] = str(len(body))
            clientFactory = self.proxyClientFactoryClass(
                request.method, rest, request.clientproto,
                allRequestHeaders, body, request)
            ###########################
            if self.socket:
                self.reactor.connectUNIX(self.socket, clientFactory)
            else:
                self.reactor.connectTCP(self.host, self.port, clientFactory)
            d = defer.Deferred()
            clientFactory.onCreate(d)
            return d
        d.addCallback(doneAllPrehooks)
        def inspect(client):
            d = defer.Deferred()
            client.registerListener(d)
            return d
        d.addCallback(inspect)
        def callPostHook(result, hookURL):
            serverResponse = result["ModifiedServerResponse"]
            return self.client.post(hookURL, json.dumps({
                        # TODO Write tests for the information provided to the adapter.
                        "PowerstripProtocolVersion": 1,
                        "Type": "post-hook",
                        "ClientRequest": {
                            "Method": request.method,
                            "Request": request.uri,
                            "Body": originalRequestBody,
                            },
                        "ServerResponse": {
                            "ContentType": serverResponse["ContentType"],
                            "Body": serverResponse["Body"],
                            "Code": serverResponse["Code"],
                        },
                    }), headers={'Content-Type': ['application/json']})
        # XXX Need to skip post-hooks for tar archives from e.g. docker export.
        for postHook in postHooks:
            hookURL = self.config.adapter_uri(postHook)
            d.addCallback(callPostHook, hookURL=hookURL)
            d.addCallback(treq.json_content)
        def sendFinalResponseToClient(result):
            # Write the final response to the client.
            request.write(result["ModifiedServerResponse"]["Body"].encode("utf-8"))
            request.finish()
        d.addCallback(sendFinalResponseToClient)
        def squashNoPostHooks(failure):
            failure.trap(NoPostHooks)
        d.addErrback(squashNoPostHooks)
        d.addErrback(log.err, 'while running chain')
        return NOT_DONE_YET


    def getChild(self, path, request):
        fragments = request.uri.split("/")
        fragments.pop(0)
        proxyArgs = (self.host, self.port, self.socket, self.path + '/' + urlquote(path, safe=""),
                     self.reactor)
        #if not request.postpath:
        resource = DockerProxy(*proxyArgs, config=self.config)
        return resource


class ServerProtocolFactory(server.Site):
    def __init__(self, dockerAddr=None, dockerPort=None, dockerSocket=None, config=None):
        self.root = DockerProxy(dockerAddr, dockerPort, dockerSocket, config=config)
        server.Site.__init__(self, self.root)
