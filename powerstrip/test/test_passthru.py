# Copyright ClusterHQ Limited. See LICENSE file for details.

"""
Tests that verify that Docker behaviour is unchanged when running through
Powerstrip.

Run these tests as so. Ensure Docker is running on /var/run/docker.sock.

$ TEST_PASSTHRU=1 trial powerstrip.test.test_passthru
"""

import os
from twisted.internet import defer
from twisted.trial.unittest import TestCase
from ..testtools import GenerallyUsefulPowerstripTestMixin


def CompareDockerAndPowerstrip(test_case, cmd, usePTY=False,
        expectDifferentResults=False):
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

    d = getProcessOutputPTY(b"/bin/bash", ["-c", cmd], { b"DOCKER_HOST": DOCKER },
        errortoo=True, usePTY=usePTY)

    def got_result(docker_result):
        if not docker_result:
            raise ValueError("Command did not produce any output when sent to "
                    "Docker daemon.")
        d = getProcessOutputPTY(b"/bin/bash", ["-c", cmd], { b"DOCKER_HOST": POWERSTRIP },
            errortoo=True, usePTY=usePTY)

        def compare_result(powerstrip_result, docker_result):
            #print "Got powerstrip result: %s" % (powerstrip_result,)
            #print "Got docker result: %s" % (docker_result,)
            if not expectDifferentResults:
                test_case.assertEquals(docker_result, powerstrip_result)
            return powerstrip_result, docker_result

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

        # Actually run the current (local) version of powerstrip on
        # localhost:2375.
        self._configure("endpoints: {}\nadapters: {}", dockerOnSocket=True,
                realDockerSocket="/var/run/docker.sock",
                powerstripPort=2375)
        self.config.read_and_parse()
        return CompareDockerAndPowerstrip(self,
            "docker run ubuntu echo hello")

    def test_run_post_hook(self):
        """
        Test basic ``docker run`` functionality when there's a post-hook (the
        post-hook should get skipped).
        """
        # Note that http://devnull/ should never be attempted because one
        # should always skip a post-hook when Docker responds with a hijacked
        # response type.
        self._configure("""
endpoints:
  "POST /*/containers/*/attach":
    post: [nothing]
adapters:
  nothing: http://devnull/
""",
                dockerOnSocket=True,
                realDockerSocket="/var/run/docker.sock",
                powerstripPort=2375)
        self.config.read_and_parse()
        return CompareDockerAndPowerstrip(self,
            "docker run ubuntu echo hello")

    def test_run_post_hook_tty(self):
        """
        Test basic ``docker run`` functionality with -ti when there's a
        post-hook (the post-hook should get skipped).
        """
        self._configure("""
endpoints:
  "POST /*/containers/*/attach":
    post: [nothing]
adapters:
  nothing: http://devnull/
""",
                dockerOnSocket=True,
                realDockerSocket="/var/run/docker.sock",
                powerstripPort=2375)
        self.config.read_and_parse()
        return CompareDockerAndPowerstrip(self,
            "docker run -ti ubuntu echo hello", usePTY=True)

    def test_run_tty(self):
        """
        Test basic ``docker run`` functionality with -ti args. (terminal;
        interactive).
        """
        self._configure("endpoints: {}\nadapters: {}", dockerOnSocket=True,
                realDockerSocket="/var/run/docker.sock",
                powerstripPort=2375)
        self.config.read_and_parse()
        d = CompareDockerAndPowerstrip(self,
            "docker run -ti ubuntu echo hello", usePTY=True)
        def assertions((powerstrip, docker)):
            self.assertNotIn("fatal", docker)
        d.addCallback(assertions)
        return d

    def test_logs(self):
        """
        Run a container and then get the logs from it.
        """
        self._configure("""endpoints: {}\nadapters: {}""",
                dockerOnSocket=True,
                realDockerSocket="/var/run/docker.sock",
                powerstripPort=2375)
        self.config.read_and_parse()
        d = CompareDockerAndPowerstrip(self,
            """
            id=$(docker run -d ubuntu bash -c
              "for X in range {1..10000}; do echo \\$X; done");
            docker wait $id >/dev/null; echo $id
            """,
            expectDifferentResults=True)
        def extractDockerPS((powerstrip, docker)):
            # Doesn't actually matter which one we use here.
            containerID = docker.split("\n")[0]
            return CompareDockerAndPowerstrip(self,
                    "docker logs %s" % (containerID,))
        d.addCallback(extractDockerPS)
        return d


# XXX Ripped from twisted.internet.utils.getProcessOutput (to add PTY support
# to getProcessOutput):
from twisted.internet.utils import _BackRelay

def getProcessOutputPTY(executable, args=(), env={}, path=None, reactor=None,
                     errortoo=0, usePTY=False):
    """
    A version of getProcessOutput with a usePTY arg.
    """
    return _callProtocolWithDeferredPTY(lambda d:
                                        _BackRelay(d, errortoo=errortoo),
                                     executable, args, env, path,
                                     reactor, usePTY=usePTY)

def _callProtocolWithDeferredPTY(protocol, executable, args, env, path,
        reactor=None, usePTY=False):
    if reactor is None:
        from twisted.internet import reactor
    d = defer.Deferred()
    p = protocol(d)
    reactor.spawnProcess(p, executable, (executable,)+tuple(args), env, path,
            usePTY=usePTY)
    return d

# End ripping.
