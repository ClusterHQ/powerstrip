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
    DOCKER_HOST = "unix:///host-var-run/docker.real.sock"
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

# Refuse to listen on a TCP port, until
# https://github.com/ClusterHQ/powerstrip/issues/56 is resolved.
# TODO: maybe allow to specify a numberic Docker group (gid) as environment
# variable, and also (optionally) the name of the socket file it creates...
dockerServer = internet.UNIXServer("/host-var-run/docker.sock", dockerAPI, mode=0660)
dockerServer.setServiceParent(application)
