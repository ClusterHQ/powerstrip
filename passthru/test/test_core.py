# Copyright ClusterHQ Limited. See LICENSE file for details.

"""
Test the actual proxy implementation, given certain configurations.
"""

from twisted.trial.unittest import TestCase
from twisted.internet import reactor

from .. import testtools

class ProxyTests(TestCase):

    def setUp(self):
        """
        Construct a fake "Docker daemon" (one which does much less than the
        actual Docker daemon)

        Pre- and post-hook API servers are provided by the individual tests.
        """
        self.dockerAPI = testtools.FakeDockerDaemon()
        self.dockerServer = reactor.listenTCP(0, self.dockerAPI)
        self.dockerPort = self.server.getHost().port


    def _get_proxy_instance(self, configuration):
        """
        Given a yaml configuration (with placeholders for interpolation of
        current runtime ports for the test), return an appropriately configured
        proxy instance.
        """

    def test_empty_endpoints(self):
        """
        The proxy passes through requests when no endpoints are specified.
        """

    def test_endpoint_and_empty_hooks(self):
        """
        An endpoint is specified, but no pre-or post hooks are added to it.
        Requests to the endpoint are proxied.
        """

    def test_adding_pre_hook_plugin(self):
        """
        A plugin has a pre-hook which increments an integral field in the JSON
        POST body called "Number".
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
