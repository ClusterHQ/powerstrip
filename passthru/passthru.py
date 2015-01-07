from twisted.internet import protocol, reactor
from zope.interface import implementer
from twisted.internet.interfaces import IHalfCloseableProtocol

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

