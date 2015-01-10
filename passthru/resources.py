"""
Some Resources used by passthru.
"""
from twisted.web import proxy


class BaseProxyResource(proxy.ReverseProxyResource):
    def getChild(self, path, request):
        raise Exception("There should be no children of a BaseProxyResource")


class CreateContainerResource(BaseProxyResource):
    pass


class DeleteContainerResource(BaseProxyResource):
    pass


