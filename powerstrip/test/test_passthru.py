# Copyright ClusterHQ Limited. See LICENSE file for details.

"""
Tests that verify that Docker behaviour is unchanged when running through
Powerstrip.

Run these tests as so. Ensure Docker is running on /var/run/docker.sock.

$ TEST_PASSTHRU=1 trial powerstrip.test.test_passthru
"""

import os
from twisted.internet import defer
from twisted.internet.utils import getProcessOutput
from twisted.trial.unittest import TestCase
from ..testtools import GenerallyUsefulPowerstripTestMixin

def CompareDockerAndPowerstrip(test_case, cmd):
    """
    Compare the output of a real Docker server against a Powerstrip passthu.

    There will be environment variables set which determine whether any
    ``docker`` execs will talk to Docker or Powerstrip.

    :param test_case: The current ``TestCase`` context.

    :param cmd: A shell command. E.g. ``echo ls | docker run -i ubuntu bash``.
        This command should include at least one call to Docker.

    :return: A ``Deferred`` which fires when the test has been completed.
    """
    DOCKER = b"unix:///var/run/docker.sock"
    POWERSTRIP = b"tcp://localhost:2375"

    d = getProcessOutput(b"/bin/bash", ["-c", cmd], { b"DOCKER_HOST": DOCKER },
        errortoo=True)

    def got_result(docker_result):
        if not docker_result:
            raise ValueError("Command did not produce any output went sent to "
                    "Docker daemon.")
        d = getProcessOutput(b"/bin/bash", ["-c", cmd], { b"DOCKER_HOST": POWERSTRIP },
            errortoo=True)

        def compare_result(powerstrip_result, docker_result):
            print "Got powerstrip result: %s" % (powerstrip_result,)
            print "Got docker result: %s" % (docker_result,)
            test_case.assertEquals(docker_result, powerstrip_result)

        d.addCallback(compare_result, docker_result)
        return d

    d.addCallback(got_result)
    return d


class BasicTests(TestCase, GenerallyUsefulPowerstripTestMixin):
    """
    Tests for basic Docker functionality.
    """

    if "TEST_PASSTHRU" not in os.environ:
        skip = "Skipping passthru tests."

    def setUp(self):
        """
        Actually run the current (local) version of powerstrip on
        localhost:2375.
        """
        self._configure("endpoints: {}\nplugins: {}", dockerOnSocket=True,
                realDockerSocket="/var/run/docker.sock",
                powerstripPort=2375)

    def tearDown(self):
        shutdowns = [
            self.proxyServer.stopListening()]
        return defer.gatherResults(shutdowns)

    def test_run(self):
        """
        Test basic ``docker run`` functionality.
        """

        # XXX this will need to prime the Docker instance in most cases, e.g.
        # docker pull
        return CompareDockerAndPowerstrip(self,
            "docker run ubuntu echo hello")

    def test_run_tty(self):
        """
        Test basic ``docker run`` functionality with -ti args. (terminal;
        interactive).
        """

        # XXX this will need to prime the Docker instance in most cases, e.g.
        # docker pull
        return CompareDockerAndPowerstrip(self,
            "docker run ubuntu -ti echo hello")
        # TODO: need to make twisted spawnProcess with a pty
