# Copyright ClusterHQ Limited. See LICENSE file for details.

"""
Tests that verify that Docker behaviour is unchanged when running through
Powerstrip.

Run these tests as so:

$ docker run -d --name powerstrip \
           -v /var/run/docker.sock:/var/run/docker.sock \
           -v ./blank_adapters.yml:/etc/powerstrip/adapters.yml \
           -p 2375:2375 \
           clusterhq/powerstrip
$ docker run --name powerstrip-test
           -v /var/run/docker.sock:/var/run/docker.sock \
            --link powerstrip:powerstrip
            clusterhq/powerstrip tox powerstrip.test.test_passthru
"""

import os

from twisted.internet.utils import getProcessOuput
from twisted.trial.unittest import TestCase

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
    POWERSTRIP = b"tcp://powerstrip:2375"

    d = getProcessOuput(b"/bin/bash", ["-c", cmd], { b"DOCKER_HOST": DOCKER },
        errortoo=True)

    def got_result(docker_result):
        if not docker_result:
            raise ValueError("Command did not produce any output went sent to "
                    "Docker daemon.")
        d = getProcessOuput(b"/bin/bash", ["-c", cmd], { b"DOCKER_HOST": POWERSTRIP },
            errortoo=True)

        def compare_result(powerstrip_result, docker_result):
            test_case.assertEquals(docker_result, powerstrip_result)

        d.addCallback(compare_result, docker_result)

    d.addCallback(got_result)
    return d


class BasicTests(TestCase):
    """
    Tests for basic Docker functionality.
    """

    if "TEST_PASSTHRU" not in os.environ:
        skip = "Skipping passthru tests."

    def test_run(self):
        """
        Test basic ``docker run`` functionality.
        """

        # XXX this will need to prime the Docker instance in most cases, e.g.
        # docker pull
        return CompareDockerAndPowerstrip(self,
            "echo ls | docker run -i ubuntu")
