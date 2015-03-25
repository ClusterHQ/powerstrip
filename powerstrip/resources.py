"""
Some Resources used by powerstrip.
"""
from twisted.web import proxy
from twisted.internet import reactor
from twisted.internet.task import deferLater
from twisted.web.server import NOT_DONE_YET
import os
from urlparse import urlparse
from powerstrip import ServerProtocolFactory

class BaseProxyResource(proxy.ReverseProxyResource):
    def getChild(self, path, request):
        raise Exception("There should be no children of a BaseProxyResource")


class CreateContainerResource(BaseProxyResource):
    def render(self, request, reactor=reactor):
        def run():
            return BaseProxyResource.render(self, request)
        deferLater(reactor, 1, run)
        return NOT_DONE_YET


class DeleteContainerResource(BaseProxyResource):
    pass

def GetDockerHost(DOCKER_HOST=None):
    """
    Logic for getting the default value of DOCKER_HOST if its either not given or
    only partially given.
    The DOCKER_HOST must either start with tcp:// or unix://
    If no scheme is provided - we check for a leading slash to determine if its tcp or unix

    it is normal to pass the ENV var DOCKER_HOST to this function:

    dockerHost = GetDockerHost(os.environ.get('DOCKER_HOST'))
    """
    
    if DOCKER_HOST is None:
        # Default to assuming we've got a Docker socket bind-mounted into a
        # container we're running in.
        DOCKER_HOST = "unix:///host-var-run/docker.real.sock"
    if "://" not in DOCKER_HOST:
        if DOCKER_HOST.startswith("/"):
          DOCKER_HOST = "unix://" + DOCKER_HOST
        else:
          DOCKER_HOST = "tcp://" + DOCKER_HOST
    return DOCKER_HOST

def GetDockerAPI(DOCKER_HOST):
    """
    Logic for getting a ServerProtocolFactory based on either the dockerAddr or dockerSocket
    which in turn depends on the scheme of the DOCKER_HOST  
    """
    if DOCKER_HOST.startswith("tcp://"):
        parsed = urlparse(DOCKER_HOST)
        dockerAPI = ServerProtocolFactory(dockerAddr=parsed.hostname,
            dockerPort=parsed.port)
    elif DOCKER_HOST.startswith("unix://"):
        socketPath = DOCKER_HOST[len("unix://"):]
        dockerAPI = ServerProtocolFactory(dockerSocket=socketPath)