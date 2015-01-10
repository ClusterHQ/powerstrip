"""
Some Resources used by passthru.
"""
from twisted.web import proxy
from twisted.internet import reactor
from twisted.internet.task import deferLater
from twisted.web.server import NOT_DONE_YET

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
