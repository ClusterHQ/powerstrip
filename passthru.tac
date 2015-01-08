import os
from twisted.application import service, internet
from twisted.protocols.policies import TrafficLoggingFactory
from urlparse import urlparse

from passthru.passthru import ServerProtocolFactory

application = service.Application("Docker API Passthru")

DOCKER_HOST = os.environ.get('DOCKER_HOST')
if "://" not in DOCKER_HOST:
    DOCKER_HOST = "tcp://" + DOCKER_HOST
parsed = urlparse(DOCKER_HOST)

dockerAPI = ServerProtocolFactory(parsed.hostname, parsed.port)
logged = TrafficLoggingFactory(dockerAPI, "api-")
dockerServer = internet.TCPServer(4243, logged, interface='0.0.0.0')
dockerServer.setServiceParent(application)

print r'export DOCKER_HOST=tcp://localhost:4243'
