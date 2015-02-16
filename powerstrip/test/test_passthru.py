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

    :param usePTY: Execute the given command with a pseudo-terminal, to
        encourage Docker to feel comfortable writing out streaming responses (like
        `docker pull` output) that are supposed to be consumed by a human.

    :param expectDifferentResults: If True, then don't make an assertion in
        here. Whether this is true or not, the raw responses from docker and
        powerstrip are passed back to the caller as a tuple for further inspection
        if they wish to make any additional assertions about the contents of the
        results.

    :return: A ``Deferred`` which fires when the test has been completed.
    """
    DOCKER = b"unix:///var/run/docker.sock"
    POWERSTRIP = b"tcp://localhost:%(proxyPort)d"

    d = getProcessOutputPTY(b"/bin/bash", ["-c", cmd], { b"DOCKER_HOST": DOCKER },
        errortoo=True, usePTY=usePTY)

    def got_result(docker_result):
        if not docker_result:
            raise ValueError("Command did not produce any output when sent to "
                    "Docker daemon.")
        d = getProcessOutputPTY(b"/bin/bash", ["-c", cmd],
                { b"DOCKER_HOST": POWERSTRIP % dict(proxyPort=test_case.proxyPort) },
            errortoo=True, usePTY=usePTY)

        def compare_result(powerstrip_result, docker_result):
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
        if hasattr(self, "nullServer"):
            shutdowns.append(self.nullServer.stopListening())
        return defer.gatherResults(shutdowns)

    def test_run(self):
        """
        Test basic ``docker run`` functionality.
        """
        # XXX this will need to prime the Docker instance in most cases, e.g.
        # docker pull

        # Actually run the current (local) version of powerstrip on
        # localhost:something.
        self._configure("endpoints: {}\nadapters: {}", dockerOnSocket=True,
                realDockerSocket="/var/run/docker.sock")
        self.config.read_and_parse()
        d = CompareDockerAndPowerstrip(self,
            "docker run ubuntu echo hello")
        def assertions((powerstrip, docker)):
            self.assertNotIn("fatal", docker)
            self.assertNotIn("fatal", powerstrip)
            self.assertIn("hello", docker)
            self.assertIn("hello", powerstrip)
        d.addCallback(assertions)
        return d

    def test_run_post_hook(self):
        """
        Test basic ``docker run`` functionality when there's a post-hook (the
        post-hook should get skipped).

        Post-hooks are skipped on attach commands because they have streaming
        (aka "hijacked") responses.

        Note that http://devnull/ should never be attempted because one
        should always skip a post-hook when Docker responds with a hijacked
        response type (`application/vnd.docker.raw-stream` as an example, such
        as the TCP-stream hijacking that `docker attach` does). If the
        implementation *does* attempt to connect to `devnull`, the test will
        fail with a DNS lookup error. This could be made better.
        """
        self._configure("""
endpoints:
  "POST /*/containers/*/attach":
    post: [nothing]
adapters:
  nothing: http://devnull/
""",
                dockerOnSocket=True,
                realDockerSocket="/var/run/docker.sock")
        self.config.read_and_parse()
        d = CompareDockerAndPowerstrip(self,
            "docker run ubuntu echo hello")
        def assertions((powerstrip, docker)):
            self.assertNotIn("fatal", docker)
            self.assertNotIn("fatal", powerstrip)
            self.assertIn("hello", docker)
            self.assertIn("hello", powerstrip)
        d.addCallback(assertions)
        return d

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
                realDockerSocket="/var/run/docker.sock")
        self.config.read_and_parse()
        d = CompareDockerAndPowerstrip(self,
            "docker run -ti ubuntu echo hello", usePTY=True)
        def assertions((powerstrip, docker)):
            self.assertNotIn("fatal", docker)
            self.assertNotIn("fatal", powerstrip)
            self.assertIn("hello", docker)
            self.assertIn("hello", powerstrip)
        d.addCallback(assertions)
        return d

    def test_run_tty(self):
        """
        Test basic ``docker run`` functionality with -ti args. (terminal;
        interactive).
        """
        self._configure("endpoints: {}\nadapters: {}", dockerOnSocket=True,
                realDockerSocket="/var/run/docker.sock")
        self.config.read_and_parse()
        d = CompareDockerAndPowerstrip(self,
            "docker run -ti ubuntu echo hello", usePTY=True)
        def assertions((powerstrip, docker)):
            self.assertNotIn("fatal", docker)
            self.assertNotIn("fatal", powerstrip)
            self.assertIn("hello", docker)
            self.assertIn("hello", powerstrip)
        d.addCallback(assertions)
        return d

    def test_logs(self):
        """
        Run a container and then get the logs from it.
        """
        self._configure("""endpoints: {}\nadapters: {}""",
                dockerOnSocket=True,
                realDockerSocket="/var/run/docker.sock")
        self.config.read_and_parse()
        d = CompareDockerAndPowerstrip(self,
            """
            id=$(docker run -d ubuntu bash -c \\
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

    NULL_CONFIG = """
endpoints:
    "* *":
      pre: [nothing]
      post: [nothing]
adapters:
    nothing: http://localhost:%d/null-adapter
"""

    NULL_TWICE_CONFIG = """
endpoints:
    "* *":
      pre: [nothing, nothing2]
      post: [nothing, nothing2]
adapters:
    nothing: http://localhost:%d/null-adapter
    nothing2: http://localhost:%d/null-adapter
"""


    def test_run_null_adapter(self):
        """
        Test basic ``docker run`` functionality with null adapter matching all
        possible API requests to exercise as much codepath as possible.
        """
        self._getNullAdapter()
        self._configure(self.NULL_CONFIG % (self.nullPort,),
                dockerOnSocket=True,
                realDockerSocket="/var/run/docker.sock")
        self.config.read_and_parse()
        d = CompareDockerAndPowerstrip(self,
            "docker run -ti ubuntu echo hello", usePTY=True)
        def assertions((powerstrip, docker)):
            self.assertNotIn("fatal", docker)
            self.assertNotIn("fatal", powerstrip)
            self.assertIn("hello", docker)
            self.assertIn("hello", powerstrip)
        d.addCallback(assertions)
        return d

    def test_run_null_twice_adapter(self):
        """
        Test basic ``docker run`` functionality with null adapter matching all
        possible API requests to exercise as much codepath as possible.  Twice.
        """
        self._getNullAdapter()
        self._configure(self.NULL_TWICE_CONFIG % (self.nullPort, self.nullPort),
                dockerOnSocket=True,
                realDockerSocket="/var/run/docker.sock")
        self.config.read_and_parse()
        d = CompareDockerAndPowerstrip(self,
            "docker run -ti ubuntu echo hello", usePTY=True)
        def assertions((powerstrip, docker)):
            self.assertNotIn("fatal", docker)
            self.assertNotIn("fatal", powerstrip)
            self.assertIn("hello", docker)
            self.assertIn("hello", powerstrip)
        d.addCallback(assertions)
        return d

    def test_run_docker_pull(self):
        """
        Test basic ``docker pull`` functionality.
        """
        self._getNullAdapter()
        self._configure(self.NULL_CONFIG % (self.nullPort,),
                dockerOnSocket=True,
                realDockerSocket="/var/run/docker.sock")
        self.config.read_and_parse()
        d = CompareDockerAndPowerstrip(self,
            "docker rmi busybox; docker pull busybox", usePTY=True,
            expectDifferentResults=True)
        def assertions((powerstrip, docker)):
            self.assertNotIn("fatal", docker)
            # The outputs vary per test run due to e.g. download speed, but
            # there should be some common themes...
            text = ["Downloaded newer image for busybox",
                    "Untagged",
                    "Deleted",
                    "Downloading",
                    "Extracting"]
            for textLine in text:
                self.assertIn(textLine, powerstrip)
                self.assertIn(textLine, docker)
        d.addCallback(assertions)
        return d

    def test_run_docker_build(self):
        """
        Test basic ``docker build`` functionality.
        """
        self._getNullAdapter()
        self._configure(self.NULL_CONFIG % (self.nullPort,),
                dockerOnSocket=True,
                realDockerSocket="/var/run/docker.sock")
        self.config.read_and_parse()
        d = CompareDockerAndPowerstrip(self,
            "cd ../fixtures/free-dockerfile; docker build .", usePTY=True)
        def assertions((powerstrip, docker)):
            self.assertNotIn("fatal", docker)
        d.addCallback(assertions)
        return d

    def test_run_stdin(self):
        """
        Test basic ``docker run`` functionality when piped stdin.
        """
        self._configure("endpoints: {}\nadapters: {}", dockerOnSocket=True,
                realDockerSocket="/var/run/docker.sock")
        self.config.read_and_parse()
        return CompareDockerAndPowerstrip(self,
            "echo hello |docker run -i ubuntu cat")


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
