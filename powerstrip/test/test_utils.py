# Copyright ClusterHQ Limited. See LICENSE file for details.
# -*- test-case-name: powerstrip.test.test_utils -*-

from twisted.trial.unittest import TestCase
from ..resources import GetDockerHost,GetDockerAPI

"""
Tests for the utils.
"""

class TestUtils(TestCase):

    def test_get_default_docker_host(self):
        """
        Test that if nothing is supplied we get the default UNIX socket
        """
        dockerHost = GetDockerHost()
        self.assertEqual(dockerHost, "unix:///host-var-run/docker.real.sock")

    def test_get_path_based_docker_host(self):
        """
        Check that if a path with no scheme is supplied then we get a unix socket
        """
        dockerHost = GetDockerHost('/var/run/my.sock')
        self.assertEqual(dockerHost, "unix:///var/run/my.sock")

    def test_get_tcp_based_docker_host(self):
        """
        Check that if a path with no scheme is supplied then we get a unix socket
        """
        dockerHost = GetDockerHost('localhost:2375')
        self.assertEqual(dockerHost, "tcp://localhost:2375")