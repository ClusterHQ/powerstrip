from ._config import PluginConfiguration
from ._parser import EndpointParser
from treq.client import HTTPClient
from twisted.internet import reactor, defer
from twisted.internet.interfaces import IHalfCloseableProtocol
from twisted.python import log
from twisted.python.failure import Failure
from twisted.web import server, proxy
from twisted.web.client import Agent
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
    """

    http = True
    _streaming = False
    _listener = None
    _responsePartBuffer = None

    def _fireListener(self, result):
        if self._listener is not None:
            print "firing listener with", result
            d = self._listener
            self._listener = None
            d.callback(result)
        else:
            print "no listener, discarding result", result

    # TODO maybe call handlResponsePart and handleReponseEnd manually?

    def registerListener(self, d):
        """
        Register a one shot listener, which can fire either with:
           * Failure(NoPostHooks()) if the proxy is handling comms back to
             the client (streaming/chunked modes), or
           * A tuple containing the (response, code, content-type).
        """
        self._listener = d

    def handleHeader(self, key, value):
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
            print "streaming raw"
            self._fireListener(Failure(NoPostHooks()))
        if key.lower() == "content-encoding" and value == "chunked":
            self._streaming = True
            print "streaming chunked"
            self._fireListener(Failure(NoPostHooks()))
        return proxy.ProxyClient.handleHeader(self, key, value)


    def handleReponsePart(self, buffer):
        print ">>>", buffer
        # If we're not in streaming mode, buffer the (only) response part.
        if self._streaming:
            proxy.ProxyClient.handleResponsePart(buffer)
        else:
            self._responsePartBuffer = buffer


    def handleResponseEnd(self):
        if self.http:
            if self._streaming:
                return proxy.ProxyClient.handleResponseEnd(self)
            else:
                # TODO handle code, content-type; handle non-JSON
                # content-types.
                print "not streaming"
                self._fireListener(
                        {"Body": json.loads(self._responsePartBuffer),
                         "Code": -1,
                         "ContentType": "elves"})
        else:
            self.father.transport.loseConnection()


    def rawDataReceived(self, data):
        if self.http and not self._streaming:
            # XXX rawDataReceived feels like ENTIRELY the wrong place to put
            # this. But handleResponsePart doesn't seem to be getting called!?
            self._responsePartBuffer = data
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
            print "firing factory listener with", result
            d = self._listener
            self._listener = None
            d.callback(result)
        else:
            print "no listener, discarding factory result", result

    def buildProtocol(self, addr):
        client = proxy.ProxyClientFactory.buildProtocol(self, addr)
        self._fireListener(client)
        return client



class DockerProxy(proxy.ReverseProxyResource):
    proxyClientFactoryClass = DockerProxyClientFactory

    def __init__(self, dockerAddr, dockerPort, path='', reactor=reactor, config=None):
        # XXX requires Docker to be run with -H 0.0.0.0:2375, shortcut to avoid
        # making ReverseProxyResource cope with UNIX sockets.
        if config is None:
            # Try to get the configuration from the default place on the
            # filesystem.
            self.config = PluginConfiguration()
        else:
            self.config = config
        self.parser = EndpointParser(self.config)
        proxy.ReverseProxyResource.__init__(self, dockerAddr, dockerPort, path, reactor)
        self.agent = Agent(reactor) # no connectionpool
        self.client = HTTPClient(self.agent)


    def render(self, request, reactor=reactor):
        # We are processing a leaf request.
        # Get the original request body from the client.
        # TODO: add a test for this assert
        assert request.requestHeaders.getRawHeaders('content-type') == ["application/json"]
        originalRequestBody = json.loads(request.content.read())
        request.content.seek(0) # hee hee
        preHooks = []
        postHooks = []
        d = defer.succeed(None)
        for endpoint in self.parser.match_endpoint(request.method, request.uri):
            # It's possible for a request to match multiple endpoint
            # definitions.  Order of matched endpoint is not defined in
            # that case.
            plugins = self.config.endpoint(endpoint)
            preHooks.extend(plugins.pre)
            postHooks.extend(plugins.post)
        def callPreHook(result, hookURL):
            if result is None:
                newRequestBody = originalRequestBody
            else:
                newRequestBody = result["Body"]
            # TODO also handle Method and Request
            return self.client.post(hookURL, json.dumps({
                        "Type": "pre-hook",
                        "Method": request.method,
                        "Request": request.method,
                        "Body": newRequestBody,
                    }), headers={'Content-Type': ['application/json']})
        for preHook in preHooks:
            hookURL = self.config.plugin_uri(preHook)
            d.addCallback(callPreHook, hookURL=hookURL)
            d.addCallback(treq.json_content)
            d.addErrback(log.err, 'while processing pre-hooks')
        def doneAllPrehooks(result):
            # Finally pass through the request to actual Docker.  For now we
            # mutate request in-place in such a way that ReverseProxyResource
            # understands it.
            if result is not None:
                request.content = StringIO.StringIO(json.dumps(result["Body"]))
            # TODO get a reference to the deferred on the not-yet-existing
            # client.
            ###########################
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
            clientFactory = self.proxyClientFactoryClass(
                request.method, rest, request.clientproto,
                request.getAllHeaders(), request.content.read(), request)
            self.reactor.connectTCP(self.host, self.port, clientFactory)
            def debug(result):
                print ">> d", result
                return result
            d = defer.Deferred()
            clientFactory.onCreate(d)
            d.addCallback(debug)
            return d
            ###########################
        d.addCallback(doneAllPrehooks)
        def inspect(client):
            d = defer.Deferred()
            def debug(result):
                print ">> d2", result
                return result
            d.addCallback(debug)
            client.registerListener(d)
            return d
        d.addCallback(inspect)
        # XXX Warning - mutating request could lead to odd results when we try
        # to reproduce the original client queries below.
        def callPostHook(result, hookURL):
            # TODO differentiate between Docker response and previous plugin
            # response somehow...
            # TODO also handle Method and Request
            return self.client.post(hookURL, json.dumps({
                        # TODO Write tests for the information provided to the plugin.
                        "Type": "post-hook",
                        "OriginalClientMethod": request.method,
                        "OriginalClientRequest": request.uri,
                        "OriginalClientBody": originalRequestBody,
                        "DockerResponseContentType": result["ContentType"],
                        "DockerResponseBody": result["Body"],
                        "DockerResponseCode": result["Code"],
                    }), headers={'Content-Type': ['application/json']})
        for postHook in postHooks:
            hookURL = self.config.plugin_uri(postHook)
            d.addCallback(callPostHook, hookURL=hookURL)
            d.addCallback(treq.json_content)
        def sendFinalResponseToClient(result):
            # Write the final response to the client.
            request.write(json.dumps(result["Body"]))
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
        proxyArgs = (self.host, self.port, self.path + '/' + urlquote(path, safe=""),
                     self.reactor)
        #if not request.postpath:
        resource = DockerProxy(*proxyArgs, config=self.config)
        return resource


class ServerProtocolFactory(server.Site):
    def __init__(self, dockerAddr, dockerPort, config=None):
        self.root = DockerProxy(dockerAddr, dockerPort, config=config)
        server.Site.__init__(self, self.root)
