from ._config import PluginConfiguration
from ._parser import EndpointParser
from treq.client import HTTPClient
from twisted.internet import reactor, defer
from twisted.internet.interfaces import IHalfCloseableProtocol
from twisted.python import log
from twisted.web import server, proxy
from twisted.web.client import Agent
from twisted.web.server import NOT_DONE_YET
from urllib import quote as urlquote
from zope.interface import directlyProvides
import StringIO
import json
import treq
import urlparse

class DockerProxyClient(proxy.ProxyClient):
    """
    An HTTP proxy which knows how to break HTTP just right so that Docker
    stream (attach/events) API calls work.
    """

    latestResponsePart = None
    http = True

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
        return proxy.ProxyClient.handleHeader(self, key, value)


    def handleResponseEnd(self):
        if self.http:
            return proxy.ProxyClient.handleResponseEnd(self)
        self.father.transport.loseConnection()


    def rawDataReceived(self, data):
        if self.http:
            return proxy.ProxyClient.rawDataReceived(self, data)
        self.father.transport.write(data)


    def handleResponsePart(self, buffer):
        self.latestResponsePart = buffer
        return proxy.ProxyClient.handleResponsePart(self, buffer)




class DockerProxyClientFactory(proxy.ProxyClientFactory):
    protocol = DockerProxyClient


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
            # XXX need to test with different hookURLs.
            d.addCallback(callPreHook, hookURL=hookURL)
            d.addCallback(treq.json_content)
            d.addErrback(log.err, 'while processing pre-hooks')
        def doneAllPrehooks(result):
            # Finally pass through the request to actual Docker.  For now we
            # mutate request in-place in such a way that ReverseProxyResource
            # understands it.
            if result is not None:
                request.content = StringIO.StringIO(json.dumps(result["Body"]))
            # TODO also handle Method and Request
            ################
            # RFC 2616 tells us that we can omit the port if it's the default port,
            # but we have to provide it otherwise
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
            self.clientFactory = self.proxyClientFactoryClass(
                request.method, rest, request.clientproto,
                request.getAllHeaders(), request.content.read(), request)
            self.reactor.connectTCP(self.host, self.port, self.clientFactory)
            return NOT_DONE_YET
            ################
            return proxy.ReverseProxyResource.render(self, request)
        d.addCallback(doneAllPrehooks)
        d.addErrback(log.err, 'while processing docker request')
        def decorateDockerResponse(result):
            self
            import pdb; pdb.set_trace()
            return result
        d.addCallback(decorateDockerResponse)
        def callPostHook(result, hookURL):
            # TODO differentiate between Docker response and previous plugin
            # response somehow...
            newRequestBody = result["Body"]
            # TODO also handle Method and Request
            return self.client.post(hookURL, json.dumps({
                        "Type": "post-hook",
                        "OriginalClientMethod": "POST", # TODO
                        "OriginalClientRequest": "/v1.16/containers/create", # TODO
                        "OriginalClientBody": originalRequestBody,
                        "DockerResponseContentType": "text/plain", # TODO
                        "DockerResponseBody": {}, # TODO
                        "DockerResponseCode": 404 # TODO
                    }), headers={'Content-Type': ['application/json']})
        for postHook in postHooks:
            hookURL = self.config.plugin_uri(postHook)
            # XXX need to test with different hookURLs.
            d.addCallback(callPostHook, hookURL=hookURL)
            d.addCallback(treq.json_content)
            d.addErrback(log.err, 'while processing post-hooks')
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
