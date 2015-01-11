# Copyright ClusterHQ Limited. See LICENSE file for details.

"""
Tests for the test tools.
"""

from twisted.trial.unittest import TestCase
from twisted.internet import reactor
import treq
import json
from ..testtools import FakeDockerServer

class TestFakeDockerServer(TestCase):
    def setUp(self):
        self.dockerAPI = FakeDockerServer()
        self.dockerServer = reactor.listenTCP(0, self.dockerAPI)
        self.dockerPort = self.dockerServer.getHost().port

    def tearDown(self):
        return self.dockerServer.stopListening()

    def test_douglas_adams_would_be_proud(self):
        d = treq.post('http://127.0.0.1:%d/post' % (self.dockerPort,),
                      json.dumps({"hiding": "things"}),
                      headers={'Content-Type': ['application/json']})
        def verify(response):
            self.assertEqual(json.loads(response),
                    {"hiding": "things", "SeenByFakeDocker": 42})
        d.addCallback(verify)
