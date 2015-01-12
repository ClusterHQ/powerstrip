# Copyright ClusterHQ Limited. See LICENSE file for details.

"""
Test the actual proxy implementation, given certain configurations.
"""

from twisted.trial.unittest import TestCase
from twisted.internet import reactor, defer
from twisted.web.client import Agent
from treq.client import HTTPClient
import json
import treq

from .. import testtools, powerstrip

class ProxyTests(TestCase):

    def setUp(self):
        """
        Construct a fake "Docker daemon" (one which does much less than the
        actual Docker daemon) and a Proxy instance.

        Pre- and post-hook API servers are provided by the individual tests.
        """
        self.dockerAPI = testtools.FakeDockerServer()
        self.dockerServer = reactor.listenTCP(0, self.dockerAPI)
        self.dockerPort = self.dockerServer.getHost().port

        self.proxyAPI = powerstrip.ServerProtocolFactory(
                dockerAddr="127.0.0.1", dockerPort=self.dockerPort)
        self.proxyServer = reactor.listenTCP(0, self.proxyAPI)
        self.proxyPort = self.proxyServer.getHost().port
        
        self.agent = Agent(reactor) # no connectionpool
        self.client = HTTPClient(self.agent)

    def tearDown(self):
        return defer.gatherResults([
            self.dockerServer.stopListening(),
            self.proxyServer.stopListening()])

    def _get_proxy_instance(self, configuration):
        """
        Given a yaml configuration (with placeholders for interpolation of
        current runtime ports for the test), return an appropriately configured
        proxy instance.
        """

    def test_empty_endpoints(self):
        """
        The proxy passes through requests when no endpoints are specified.

        In particular, when POST to the /towel endpoint on the *proxy*, we get
        to see that we were seen by the (admittedly fake) Docker daemon.
        """
        # TODO: specify an empty configuration
        d = self.client.post('http://127.0.0.1:%d/towel' % (self.proxyPort,),
                      json.dumps({"hiding": "things"}),
                      headers={'Content-Type': ['application/json']})
        d.addCallback(treq.json_content)
        def verify(response):
            self.assertEqual(response,
                    {"hiding": "things", "SeenByFakeDocker": 42})
        d.addCallback(verify)
        return d

    def test_endpoint_and_empty_hooks(self):
        """
        An endpoint is specified, but no pre-or post hooks are added to it.
        Requests to the endpoint are proxied.
        """

    def test_adding_pre_hook_plugin(self):
        """
        A plugin has a pre-hook which increments an integral field in the JSON
        POST body called "Number".

        TODO: Assert that Docker saw it, as well as that it came out the end.
        """

    def test_adding_pre_hook_twice_plugin(self):
        """
        Chaining pre-hooks: adding twice means you get +2.
        """

    def test_adding_post_hook_plugin(self):
        """
        A plugin has a post-hook which increments an integral field in the JSON
        response body called "Number".
        """
    
    def test_adding_post_hook_twice_plugin(self):
        """
        Chaining post-hooks: adding twice means you get +2.
        """

    def test_prehook_error_does_not_call_docker(self):
        """
        An error in the pre-hook does not call through to Docker and returns
        the error to the user.
        """

    def test_prehook_error_stops_chain(self):
        """
        An error in the pre-hook stops the chain when there are multiple
        pre-hooks.
        """

    def test_posthook_error_stops_chain(self):
        """
        An error in the post-hook stops the chain and returns the error to the
        user.
        """

    def test_endpoint_GET_args(self):
        """
        An endpoint is matched when the GET arguments change.
        """
    
    def test_endpoint_globbing(self):
        """
        An endpoint is matched when there are '*' characters in the string
        """

    def test_stream_endpoint(self):
        """
        A streaming (aka hijacking) endpoint like /attach is rejected from
        endpoints: a runtime error is raised when the Content-Type is detected.
        """

    def test_chunked_endpoint(self):
        """
        A chunking endpoint like /pull is rejected from endpoints: a runtime
        error is raised when the Content-Encoding is detected.
        """
