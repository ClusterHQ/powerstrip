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


    def _getProxyInstance(self, configuration):
        """
        Given a yaml configuration (with placeholders for interpolation of
        current runtime ports for the test), return an appropriately configured
        proxy instance.
        """

    def test_emptyEndpoints(self):
        """
        The proxy passes through requests when no endpoints are specified.
        """

    def test_endpointAndEmptyHooks(self):
        """
        An endpoint is specified, but no pre-or post hooks are added to it.
        Requests to the endpoint are proxied.
        """

    def test_addingPreHookPlugin(self):
        """
        A plugin has a pre-hook which increments an integral field in the JSON
        POST body called "Number".
        """

    def test_addingPreHookTwicePlugin(self):
        """
        Chaining pre-hooks: adding twice means you get +2.
        """

    def test_addingPostHookPlugin(self):
        """
        A plugin has a post-hook which increments an integral field in the JSON
        response body called "Number".
        """
    
    def test_addingPostHookTwicePlugin(self):
        """
        Chaining post-hooks: adding twice means you get +2.
        """

    def test_prehookErrorDoesNotCallDocker(self):
        """
        An error in the pre-hook does not call through to Docker and returns
        the error to the user.
        """

    def test_prehookErrorStopsChain(self):
        """
        An error in the pre-hook stops the chain when there are multiple
        pre-hooks.
        """

    def test_posthookErrorStopsChain(self):
        """
        An error in the post-hook stops the chain and returns the error to the
        user.
        """

    def test_endpointGETArgs(self):
        """
        An endpoint is matched when the GET arguments change.
        """
    
    def test_endpointGlobbing(self):
        """
        An endpoint is matched when there are '*' characters in the string
        """
