"""
Some Resources used by passthru.
"""
from twisted.web import proxy
from twisted.internet import reactor
from twisted.internet.task import deferLater

class BaseProxyResource(proxy.ReverseProxyResource):
    def getChild(self, path, request):
        raise Exception("There should be no children of a BaseProxyResource")


class CreateContainerResource(BaseProxyResource):
    def render(self, request, reactor=reactor):
        def run():
            return BaseProxyResource.render(request)
        return deferLater(reactor, 1, run)


class DeleteContainerResource(BaseProxyResource):
    pass
