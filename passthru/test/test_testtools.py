# Copyright ClusterHQ Limited. See LICENSE file for details.

"""
Tests for the test tools.
"""

from twisted.trial.unittest import TestCase
from twisted.internet import reactor
import treq
from treq.client import HTTPClient
import json
from ..testtools import FakeDockerServer
from twisted.web.client import Agent

class TestFakeDockerServer(TestCase):
    def setUp(self):
        self.dockerAPI = FakeDockerServer()
        self.dockerServer = reactor.listenTCP(0, self.dockerAPI)
        self.dockerPort = self.dockerServer.getHost().port
        self.agent = Agent(reactor) # no connectionpool
        self.client = HTTPClient(self.agent)

    def tearDown(self):
        return self.dockerServer.stopListening()

    def test_douglas_adams_would_be_proud(self):
        d = self.client.post('http://127.0.0.1:%d/towel' % (self.dockerPort,),
                      json.dumps({"hiding": "things"}),
                      headers={'Content-Type': ['application/json']})
        d.addCallback(treq.json_content)
        def verify(response):
            self.assertEqual(response,
                    {"hiding": "things", "SeenByFakeDocker": 42})
        d.addCallback(verify)
        return d
