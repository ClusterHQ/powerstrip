import os
from twisted.application import service, internet
#from twisted.protocols.policies import TrafficLoggingFactory
from urlparse import urlparse

from powerstrip.powerstrip import ServerProtocolFactory

application = service.Application("Powerstrip")

DOCKER_HOST = os.environ.get('DOCKER_HOST')
if DOCKER_HOST is None:
    # Default to assuming we've got a Docker socket bind-mounted into a
    # container we're running in.
    DOCKER_HOST = "unix:///var/run/docker.sock"
if "://" not in DOCKER_HOST:
    DOCKER_HOST = "tcp://" + DOCKER_HOST
if DOCKER_HOST.startswith("tcp://"):
    parsed = urlparse(DOCKER_HOST)
    dockerAPI = ServerProtocolFactory(dockerAddr=parsed.hostname,
        dockerPort=parsed.port)
elif DOCKER_HOST.startswith("unix://"):
    socketPath = DOCKER_HOST[len("unix://"):]
    dockerAPI = ServerProtocolFactory(dockerSocket=socketPath)
#logged = TrafficLoggingFactory(dockerAPI, "api-")
dockerServer = internet.TCPServer(4243, dockerAPI, interface='0.0.0.0')
dockerServer.setServiceParent(application)

print r'export DOCKER_HOST=tcp://localhost:4243'
