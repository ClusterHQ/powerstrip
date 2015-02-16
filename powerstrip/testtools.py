# Copyright ClusterHQ Limited. See LICENSE file for details.

"""
Test utilties for testing the proxy.
"""

from twisted.web import server, resource
import json

import testtools, powerstrip
from ._config import PluginConfiguration
from ._parser import EndpointParser
from twisted.python.filepath import FilePath
from twisted.internet import reactor

class GenerallyUsefulPowerstripTestMixin(object):
    def _getNullAdapter(self):
        self.nullAPI = getNullAdapter()
        self.nullServer = reactor.listenTCP(0, self.nullAPI)
        self.nullPort = self.nullServer.getHost().port

    def _configure(self, config_yml, dockerArgs={}, dockerOnSocket=False,
            realDockerSocket=False, powerstripPort=0, nullAdapter=False):
        if not realDockerSocket:
            self.dockerAPI = testtools.FakeDockerServer(**dockerArgs)
            if dockerOnSocket:
                self.socketPath = self.mktemp()
                self.dockerServer = reactor.listenUNIX(self.socketPath, self.dockerAPI)
            else:
                self.dockerServer = reactor.listenTCP(0, self.dockerAPI)
                self.dockerPort = self.dockerServer.getHost().port
        else:
            # NB: only supports real docker on socket (not tcp) at the
            # moment
            assert dockerOnSocket, ("must pass dockerOnSocket=True "
                        "if specifying realDockerSocket")
            self.socketPath = realDockerSocket

        self.config = PluginConfiguration()
        tmp = self.mktemp()
        self.config._default_file = tmp
        fp = FilePath(tmp)
        fp.setContent(config_yml)
        self.parser = EndpointParser(self.config)
        if dockerOnSocket:
            self.proxyAPI = powerstrip.ServerProtocolFactory(
                    dockerSocket=self.socketPath, config=self.config)
        else:
            self.proxyAPI = powerstrip.ServerProtocolFactory(
                                dockerAddr="127.0.0.1", dockerPort=self.dockerPort,
                                config=self.config)
        self.proxyServer = reactor.listenTCP(powerstripPort, self.proxyAPI)
        self.proxyPort = self.proxyServer.getHost().port


class FakeDockerServer(server.Site):
    def __init__(self, **kw):
        self.root = FakeDockerRoot(**kw)
        server.Site.__init__(self, self.root)


class FakeDockerRoot(resource.Resource):
    isLeaf = False
    def __init__(self, **kw):
        resource.Resource.__init__(self)
        self.putChild("towel", FakeDockerTowelResource(**kw))
        self.putChild("info", FakeDockerInfoResource(**kw))


class FakeDockerTowelResource(resource.Resource):
    isLeaf = True

    def __init__(self, rawStream=False, chunkedResponse=False):
        self.rawStream = rawStream
        self.chunkedResponse = chunkedResponse
        resource.Resource.__init__(self)

    def render_POST(self, request):
        """
        Take a JSON POST body, add an attribute to it "SeenByFakeDocker", then pass
        it back as a response.
        """
        jsonPayload = request.content.read()
        jsonParsed = json.loads(jsonPayload)
        if "SeenByFakeDocker" in jsonParsed:
            raise Exception("already seen by a fake docker?!")
        jsonParsed["SeenByFakeDocker"] = 42
        if not self.rawStream:
            request.setHeader("Content-Type", "application/json")
        else:
            request.setHeader("Content-Type", "application/vnd.docker.raw-stream")
        if self.chunkedResponse:
            request.setHeader("Transfer-Encoding", "chunked")
        return json.dumps(jsonParsed)


class FakeDockerInfoResource(resource.Resource):
    isLeaf = True

    def __init__(self, **kw):
        # disregard kwargs for now (they're used in TowelResource...)
        resource.Resource.__init__(self)

    def render_GET(self, request):
        """
        Tell some information.
        """
        return "INFORMATION FOR YOU: %s" % (request.args["return"][0],)


class AdderPlugin(server.Site):
    """
    The first powerstrip adapter: a pre-hook and post-hook implementation of a
    simple adder which can optionally blow up on demand.
    """
    def __init__(self, pre=False, post=False, explode=False, incrementBy=1):
        self.root = AdderRoot(pre, post, explode, incrementBy)
        server.Site.__init__(self, self.root)


class AdderResource(resource.Resource):
    isLeaf = True
    def __init__(self, pre, post, explode, incrementBy):
        self.pre = pre
        self.post = post
        self.explode = explode
        self.incrementBy = incrementBy
        resource.Resource.__init__(self)


    def _renderPreHook(self, request, jsonParsed):
        parsedBody = json.loads(jsonParsed["ClientRequest"]["Body"])
        parsedBody["Number"] += self.incrementBy
        request.setHeader("Content-Type", "application/json")
        # TODO: Don't decode the JSON, probably. Or, special-case Content-Type
        # logic everywhere.
        return json.dumps({"PowerstripProtocolVersion": 1,
                           "ModifiedClientRequest": {
                               "Method": jsonParsed["ClientRequest"]["Method"],
                               "Request": jsonParsed["ClientRequest"]["Request"],
                               "Body": json.dumps(parsedBody)}})


    def _renderPostHook(self, request, jsonParsed):
        parsedBody = json.loads(jsonParsed["ServerResponse"]["Body"])
        parsedBody["Number"] += self.incrementBy
        request.setHeader("Content-Type", "application/json")
        return json.dumps({
            "PowerstripProtocolVersion": 1,
            "ModifiedServerResponse": {
                "ContentType": jsonParsed["ServerResponse"]["ContentType"],
                "Body": json.dumps(parsedBody),
                "Code": jsonParsed["ServerResponse"]["Code"]}})

    def render_POST(self, request):
        """
        OK, we got to the meat of it.

        This render handles JSON POST requests.

        If pre is set, it succeeds on JSON which looks like.
            Type: "pre-hook"

        If post is set, it succeeds on JSON which looks like.
            Type: "post-hook"

        If explode is set, it always returns a 500 error.
        """
        jsonPayload = request.content.read()
        jsonParsed = json.loads(jsonPayload)

        if self.explode:
            request.setResponseCode(500)
            return "sadness for you, today."

        if jsonParsed["Type"] == "pre-hook" and self.pre:
            return self._renderPreHook(request, jsonParsed)
        elif jsonParsed["Type"] == "post-hook" and self.post:
            return self._renderPostHook(request, jsonParsed)


class AdderRoot(resource.Resource):
    isLeaf = False
    def __init__(self, pre, post, explode, incrementBy):
        self.pre = pre
        self.post = post
        self.explode = explode
        self.incrementBy = incrementBy
        resource.Resource.__init__(self)
        self.putChild("adapter", AdderResource(self.pre, self.post, self.explode, self.incrementBy))


class NullAdapterResource(resource.Resource):
    isLeaf = True
    def render_POST(self, request):
        """
        Handle a pre-hook.
        """
        requestJson = json.loads(request.content.read())
        if requestJson["Type"] == "pre-hook":
            return self._handlePreHook(request, requestJson)
        elif requestJson["Type"] == "post-hook":
            return self._handlePostHook(request, requestJson)
        else:
            raise Exception("unsupported hook type %s" %
                (requestJson["Type"],))

    def _handlePreHook(self, request, requestJson):
        # The desired response is the entire client request
        # payload, unmodified.
        return json.dumps({
            "PowerstripProtocolVersion": 1,
            "ModifiedClientRequest":
                requestJson["ClientRequest"]})

    def _handlePostHook(self, request, requestJson):
        # The desired response is the entire server response
        # payload, unmodified.
        return json.dumps({
            "PowerstripProtocolVersion": 1,
            "ModifiedServerResponse":
                requestJson["ServerResponse"]})


def getNullAdapter():
    root = resource.Resource()
    root.putChild("null-adapter", NullAdapterResource())
    site = server.Site(root)
    return site
