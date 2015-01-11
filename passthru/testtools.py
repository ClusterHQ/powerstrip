# Copyright ClusterHQ Limited. See LICENSE file for details.

"""
Test utilties for testing the proxy.
"""

from twisted.web import server, resource
from twisted.internet import reactor
import json


class FakeDockerServer(server.Site):
    def __init__(self):
        self.root = Root()
        server.Site.__init__(self, self.root)
        
        
class Root(resource.Resource):
    isLeaf = False
    def getChild(self, path, request):
        if path == "towel":
            return FakeDockerResource()


class FakeDockerResource(resource.Resource):
    isLeaf = True
    def render(self, request, reactor=reactor):
        """
        Take a JSON POST body, add an attribute to it "SeenByFakeDocker", then pass
        it back as a response.
        """
        jsonPayload = request.content.read()
        jsonParsed = json.loads(jsonPayload)
        if "SeenByFakeDocker" in jsonParsed:
            raise Exception("already seen by a fake docker?!")
        jsonParsed["SeenByFakeDocker"] = 42
        return json.dumps(jsonParsed)
