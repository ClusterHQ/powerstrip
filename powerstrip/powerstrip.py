from twisted.internet import reactor
from zope.interface import directlyProvides
from twisted.internet.interfaces import IHalfCloseableProtocol
from twisted.web import server, proxy
from urllib import quote as urlquote

import resources

class DockerProxyClient(proxy.ProxyClient):
    """
    An HTTP proxy which knows how to break HTTP just right so that Docker
    stream (attach/events) API calls work.
    """

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



class DockerProxyClientFactory(proxy.ProxyClientFactory):
    protocol = DockerProxyClient


class DockerProxy(proxy.ReverseProxyResource):
    proxyClientFactoryClass = DockerProxyClientFactory

    def __init__(self, dockerAddr, dockerPort, path='', reactor=reactor):
        # XXX requires Docker to be run with -H 0.0.0.0:2375, shortcut to avoid
        # making ReverseProxyResource cope with UNIX sockets.
        proxy.ReverseProxyResource.__init__(self, dockerAddr, dockerPort, path, reactor)


    def getChild(self, path, request):
        fragments = request.uri.split("/")
        fragments.pop(0)
        proxyArgs = (self.host, self.port, self.path + '/' + urlquote(path, safe=""),
                     self.reactor)
        if not request.postpath:
            # we are processing a leaf request
            pass
        resource = DockerProxy(*proxyArgs)
        return resource


class ServerProtocolFactory(server.Site):
    def __init__(self, dockerAddr, dockerPort):
        self.root = DockerProxy(dockerAddr, dockerPort)
        server.Site.__init__(self, self.root)
