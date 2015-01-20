# Copyright ClusterHQ Limited. See LICENSE file for details.

"""
Tests that verify that Docker behaviour is unchanged when running through
Powerstrip.
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

    :return: A ``Deferred`` which fires when the test has been completed.
    """
    DOCKER = b"unix:///var/run/docker.sock"
    POWERSTRIP = b"tcp://powerstrip:2375"

    os.environ[b"DOCKER_HOST"] = DOCKER

    d = 
