from twisted.internet import protocol, reactor
from zope.interface import implementer
from twisted.internet.interfaces import IHalfCloseableProtocol
from twisted.web import server, proxy
from twisted.protocols import basic
from urllib import quote as urlquote

_debug = []

USE_HTTP_PROXY = True

@implementer(IHalfCloseableProtocol)
class ServerProtocol(protocol.Protocol):
    def __init__(self, dockerAddr, dockerPort):
        self.buffer = ""
        self.client = None
        self.dockerAddr = dockerAddr
        self.dockerPort = dockerPort

    def connectionMade(self):
        factory = protocol.ClientFactory()
        factory.protocol = ClientProtocol
        factory.server = self

        reactor.connectTCP(
            self.dockerAddr, self.dockerPort, factory)

    # Client => Proxy
    def dataReceived(self, data):
        if self.client:
            self.client.write(data)
        else:
            self.buffer += data

    # Proxy => Client
    def write(self, data):
        self.transport.write(data)

    def readConnectionLost(self):
        self.client.transport.loseWriteConnection()

    def connectionLost(self, reason):
        self.client.transport.loseConnection()


class ClientProtocol(protocol.Protocol):

    def connectionMade(self):
        self.factory.server.client = self
        if self.factory.server.buffer:
            self.write(self.factory.server.buffer)
            self.factory.server.buffer = ''

    # Server => Proxy
    def dataReceived(self, data):
        self.factory.server.write(data)

    # Proxy => Server
    def write(self, data):
        if data:
            self.transport.write(data)


    def connectionLost(self, reason):
        self.factory.server.transport.loseConnection()



class ServerProtocolFactory(protocol.ServerFactory):

    protocol = ServerProtocol

    def __init__(self, dockerAddr, dockerPort):
        self.dockerAddr = dockerAddr
        self.dockerPort = dockerPort

    def buildProtocol(self, addr):
        p = self.protocol(self.dockerAddr, self.dockerPort)
        p.factory = self
        return p



def channelLog(loc, val):
    print val


class DockerProxyClient(proxy.ProxyClient):

    def __init__(self, command, rest, version, headers, data, father):
        self.log = "attach" in father.uri
        if self.log:
            channelLog("dockerapi/%d" % (id(self),), "started:",
                    self, command, rest, version, headers, data, father)
        proxy.ProxyClient.__init__(
                self, command, rest, version, headers, data, father)
        # Having identified differences between stream which hangs (with proxy)
        # and stream which works (without proxy) this was the only visible
        # difference in the TCP streams, except for "HTTP/1.0" vs "HTTP/1.1"...
        # so let's try changing one thing at a time.
        del self.headers["connection"]


    def sendCommand(self, command, path):
        self.transport.writeSequence([command, b' ', path, b' HTTP/1.1\r\n'])


    def connectionMade(self):
        if self.log:
            channelLog("dockerapi/%d" % (id(self),), "connection made!")
        return proxy.ProxyClient.connectionMade(self)


    def handleStatus(self, version, code, message):
        if self.log:
            channelLog("dockerapi/%d" % (id(self),), "handling status", version, code, message)
        return proxy.ProxyClient.handleStatus(self, version, code, message)


    def handleHeader(self, key, value):
        if self.log:
            channelLog("dockerapi/%d" % (id(self),), "handling header", key, value)
        return proxy.ProxyClient.handleHeader(self, key, value)


    def handleResponsePart(self, buffer):
        if self.log:
            channelLog("dockerapi/%d" % (id(self),), "got response part:", repr(buffer))
        return proxy.ProxyClient.handleResponsePart(self, buffer)


    def handleResponseEnd(self):
        if self.log:
            channelLog("dockerapi/%d" % (id(self),), "response end!")
        return proxy.ProxyClient.handleResponseEnd(self)


    def dataReceived(self, data):
        if self.log:
            channelLog("dockerapi/%d" % (id(self),),
                    "line_mode:", self.line_mode, "data:", repr(data))
        return basic.LineReceiver.dataReceived(self, data)


class DockerProxyClientFactory(proxy.ProxyClientFactory):
    protocol = DockerProxyClient


class DockerProxy(proxy.ReverseProxyResource):
    proxyClientFactoryClass = DockerProxyClientFactory

    def __init__(self, dockerAddr, dockerPort, path='', reactor=reactor):
        # XXX requires Docker to be run with -H 0.0.0.0:2375, shortcut to avoid
        # making ReverseProxyResource cope with UNIX sockets.
        proxy.ReverseProxyResource.__init__(self, dockerAddr, dockerPort, path, reactor)


    def getChild(self, path, request):
        channelLog("dockerapi", "getChild called with", self, path, request)
        """
        fragments = path.split("/")
        if fragments[1:2] == ["containers", "create"] and request.method == "POST":
            return CreateContainerResource()
        elif fragments[1] == "containers" and request.method == "DELETE":
            return DeleteContainerResource()
        """
        resource = DockerProxy(
            self.host, self.port, self.path + '/' + urlquote(path, safe=""),
            self.reactor)
        _debug.append((request, resource))
        return resource




class HTTPServerProtocolFactory(server.Site):
    def __init__(self, dockerAddr, dockerPort):
        self.root = DockerProxy(dockerAddr, dockerPort)
        server.Site.__init__(self, self.root)


if USE_HTTP_PROXY:
    ServerProtocolFactory = HTTPServerProtocolFactory
