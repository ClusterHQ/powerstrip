import os
import sys
from twisted.application import service, internet
#from twisted.protocols.policies import TrafficLoggingFactory

from powerstrip.powerstrip import ServerProtocolFactory
from powerstrip.resources import GetDockerHost,GetDockerAPICredentials

TARGET_DOCKER_SOCKET = "/host-var-run/docker.sock"

application = service.Application("Powerstrip")

# we create a connection to the Docker server based on DOCKER_HOST (can be tcp or unix socket)
DOCKER_HOST = GetDockerHost(os.environ.get('DOCKER_HOST'))
dockerAPICredentials = GetDockerAPICredentials(DOCKER_HOST)

# check that /var/run is mounted from the host (so we can write docker.sock to it)
if not os.path.isdir("/host-var-run"):
  sys.stderr.write("/var/run must be mounted as /host-var-run in the powerstrip container\n")
  sys.exit(1)

# check that the docker unix socket that we are trying to connect to actually exists
if dockerAPICredentials['dockerSocket'] and not os.path.exists(dockerAPICredentials["dockerSocket"]):
  sys.stderr.write(dockerAPICredentials["dockerSocket"] + " does not exist as a docker unix socket to connect to\n")
  sys.exit(1)

# check that the unix socket we want to listen on does not already exist
if os.path.exists(TARGET_DOCKER_SOCKET):
  sys.stderr.write(TARGET_DOCKER_SOCKET + " already exists - we want to listen on this path\n")
  sys.exit(1)

dockerAPI = ServerProtocolFactory(**dockerAPICredentials)
dockerServer = internet.UNIXServer(TARGET_DOCKER_SOCKET, dockerAPI, mode=0660)
dockerServer.setServiceParent(application)
