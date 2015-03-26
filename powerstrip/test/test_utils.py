# Copyright ClusterHQ Limited. See LICENSE file for details.
# -*- test-case-name: powerstrip.test.test_utils -*-

from twisted.trial.unittest import TestCase
from ..resources import GetDockerHost,GetDockerAPICredentials

"""
Tests for the utils.
"""

class TestDockerHost(TestCase):

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

    def test_get_path_based_docker_host_unchanged(self):
        """
        Check that if a path with no scheme is supplied then we get a unix socket
        """
        dockerHost = GetDockerHost('unix:///var/run/yobedisfileyo')
        self.assertEqual(dockerHost, "unix:///var/run/yobedisfileyo")

    def test_get_tcp_based_docker_host_unchanged(self):
        """
        Check that if a path with no scheme is supplied then we get a unix socket
        """
        dockerHost = GetDockerHost('tcp://127.0.0.1:2375')
        self.assertEqual(dockerHost, "tcp://127.0.0.1:2375")


class TestDockerAPICredentials(TestCase):

    def test_get_default_dockerapi_credentials(self):
        """
        Test that if nothing is supplied we get the default UNIX socket
        """
        dockerAPICredentials = GetDockerAPICredentials()
        
        self.assertEqual(dockerAPICredentials['dockerSocket'], "/host-var-run/docker.real.sock")
        self.assertEqual(dockerAPICredentials['scheme'], "unixsocket")
        
        self.assertNotIn("dockerAddr", dockerAPICredentials)
        self.assertNotIn("dockerPort", dockerAPICredentials)

    def test_get_tcp_dockerapi_credentials(self):
        """
        Test that if TCP is supplied we get the IP / port returned
        """
        dockerAPICredentials = GetDockerAPICredentials('tcp://127.0.0.1:2375')
        self.assertEqual(dockerAPICredentials['scheme'], "tcp")
        
        self.assertEqual(dockerAPICredentials['dockerAddr'], "127.0.0.1")
        self.assertEqual(dockerAPICredentials['dockerPort'], 2375)
        self.assertNotIn("dockerSocket", dockerAPICredentials)

    def test_get_unixsocket_dockerapi_credentials(self):
        """
        Test that if UNIX is supplied
        """
        dockerAPICredentials = GetDockerAPICredentials('unix:///var/run/yobedisfileyo')
        self.assertEqual(dockerAPICredentials['scheme'], "unixsocket")
        
        self.assertEqual(dockerAPICredentials['dockerSocket'], "/var/run/yobedisfileyo")
        self.assertNotIn("dockerAddr", dockerAPICredentials)
        self.assertNotIn("dockerPort", dockerAPICredentials)