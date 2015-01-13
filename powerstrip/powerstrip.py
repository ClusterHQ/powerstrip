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
    streaming = False
    _listener = None
    responsePartBuffer = None

    # TODO maybe call handlResponsePart and handleReponseEnd manually?

    def registerListener(self, d):
        """
        Register a one shot listener, which can fire either with:
           * Failure(NoPostHooks()) if the proxy is handling comms back to
             the client (streaming/chunked modes), or
           * A tuple containing the (response, code, content-type).
        """
        # TODO handle ...
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
            if self._listener is not None:
                self._listener.callback(Failure(NoPostHooks()))
        if key.lower() == "content-encoding" and value == "chunked":
            self._streaming = True
            if self._listener is not None:
                self._listener.callback(Failure(NoPostHooks()))
        return proxy.ProxyClient.handleHeader(self, key, value)


    def handleReponsePart(self, buffer):
        # If we're not in streaming mode, buffer the (only) response part.
        if self._streaming:
            proxy.ProxyClient.handleResponsePart(buffer)
        else:
            self.responsePartBuffer = buffer


    def handleResponseEnd(self):
        if self.http:
            if self._streaming:
                return proxy.ProxyClient.handleResponseEnd(self)
        self.father.transport.loseConnection()


    def rawDataReceived(self, data):
        if self.http:
            return proxy.ProxyClient.rawDataReceived(self, data)
        self.father.transport.write(data)



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

            # In order to support post-hooks, we need two modes:
            #
            # 1. The response from Docker came as a single chunk, and we want
            #    to buffer it in memory and not pass it on to the user until we've
            #    passed it through all of the post-hooks.  This is much like a
            #    regular treq request.
            #
            # 2. It's a streaming request, in which case we want normal
            #    ReverseProxyResource.render behaviour (do not buffer entire
            #    response, handle streaming protocols, etc).
            #

            # TODO We are not handling case 2 yet.  That is what the "if True"
            # is for.
            # XXX not chunked and not hijacked is a property of the Docker
            # *response*, which we don't have until we make the request.
            if True:
                # TODO Should be something like "not chunked and not hijacked".
                # TODO Could also use "not postHooks"... because it's only if
                # you want postHooks that you have to do this. But then it
                # might be confusing that you get slightly different behaviour
                # if you add a postHook.

                # TODO write tests for the following stanza, or throw it away.
                # Use treq to make request to Docker
                if self.port == 80:
                    host = self.host
                else:
                    host = "%s:%d" % (self.host, self.port)
                #request.requestHeaders.setRawHeaders(b"host", [host])
                request.content.seek(0, 0)
                qs = urlparse.urlparse(request.uri)[4]
                if qs:
                    rest = self.path + '?' + qs
                else:
                    rest = self.path

                # Make a request to Docker, based on the client's request.
                # We can only handle JSON.  XXX Think about GET requests...
                d = self.client.request(
                        request.method, "http://%s%s" % (host, rest),
                        data=request.content.read(),
                        headers={'Content-Type': ["application/json"]})
                d.addCallback(treq.json_content)
                return d
            else:
                # Join up the connections like a true proxy for chunked or
                # hijacked responses.  This returns NOT_DONE_YET.  TODO
                # Shortcut processing all the ensuing post-hooks, there's no
                # point running them.
                # TODO Write some tests which require this else clause.
                proxy.ReverseProxyResource.render(self, request)
                raise NoPostHooks()
        d.addCallback(doneAllPrehooks)
        d.addErrback(log.err, 'while processing docker request')
        def decorateDockerResponse(result):
            # Make Docker's response look like it came from an upstream plugin.
            return {"ContentType": "application/json",
                    "Body": result,
                    "Code": 200} # TODO Should support passing through a
                                 # non-JSON non-success response from Docker
                                 # (and test that a non-success response from
                                 # Docker is correctly reported to the plugin).
        d.addCallback(decorateDockerResponse)
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
            d.addErrback(log.err, 'while processing post-hooks')
        def sendFinalResponseToClient(result):
            # Write the final response to the client.
            request.write(json.dumps(result["Body"]))
            request.finish()
        d.addCallback(sendFinalResponseToClient)
        def squashNoPostHooks(failure):
            failure.trap(NoPostHooks)
        d.addErrback(squashNoPostHooks)
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
