import os
import sys
from twisted.application import service, internet
#from twisted.protocols.policies import TrafficLoggingFactory

from powerstrip.powerstrip import ServerProtocolFactory
#from powerstrip.tools import GetDockerHost,GetDockerAPI

TARGET_DOCKER_SOCKET = "/host-var-run/docker.sock"

application = service.Application("Powerstrip")

# we create a connection to the Docker server based on DOCKER_HOST (can be tcp or unix socket)
DOCKER_HOST = GetDockerHost(os.environ.get('DOCKER_HOST'))
dockerAPICredentials = GetDockerAPICredentials(DOCKER_HOST)

# check that /var/run is mounted from the host (so we can write docker.sock to it)
if !os.path.isdir("/host-var-run"):
  print("/var/run must be mounted as /host-var-run in the powerstrip container", file=sys.stderr)
  sys.exit(1)

# check that the docker unix socket that we are trying to connect to actually exists
if dockerAPICredentials['scheme'] == "unixsocket" && os.path.exists(dockerAPICredentials["dockerSocket"]):
  print(dockerAPICredentials["dockerSocket"] + " does not exist as a docker unix socket to connect to", file=sys.stderr)
  sys.exit(1)

# check that the unix socket we want to listen on does not already exist
if os.path.exists(TARGET_DOCKER_SOCKET):
  print(TARGET_DOCKER_SOCKET + " already exists - we want to listen on this path", file=sys.stderr)
  sys.exit(1)

dockerAPI = ServerProtocolFactory(**dockerAPICredentials)
dockerServer = internet.UNIXServer(TARGET_DOCKER_SOCKET, dockerAPI, mode=0660)
dockerServer.setServiceParent(application)
