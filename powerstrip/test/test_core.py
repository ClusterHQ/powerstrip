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
from .._config import PluginConfiguration
from .._parser import EndpointParser
from twisted.python.filepath import FilePath
from ..testtools import AdderPlugin

from twisted.protocols.policies import TrafficLoggingFactory

class ProxyTests(TestCase):

    def setUp(self):
        """
        Construct a fake "Docker daemon" (one which does much less than the
        actual Docker daemon) and a Proxy instance.

        Pre- and post-hook API servers are provided by the individual tests.
        """
        self.agent = Agent(reactor) # no connectionpool
        self.client = HTTPClient(self.agent)

    def tearDown(self):
        shutdowns = [
            self.dockerServer.stopListening(),
            self.proxyServer.stopListening()]
        if hasattr(self, 'adderServer'):
            shutdowns.append(self.adderServer.stopListening())
        if hasattr(self, 'adderTwoServer'):
            shutdowns.append(self.adderTwoServer.stopListening())
        return defer.gatherResults(shutdowns)

    def _configure(self, config_yml, dockerArgs={}, dockerOnSocket=False):
        self.dockerAPI = TrafficLoggingFactory(testtools.FakeDockerServer(**dockerArgs), "docker-")
        if dockerOnSocket:
            self.socketPath = self.mktemp()
            self.dockerServer = reactor.listenUNIX(self.socketPath, self.dockerAPI)
        else:
            self.dockerServer = reactor.listenTCP(0, self.dockerAPI)
            self.dockerPort = self.dockerServer.getHost().port

        self.config = PluginConfiguration()
        tmp = self.mktemp()
        self.config._default_file = tmp
        fp = FilePath(tmp)
        fp.setContent(config_yml)
        self.parser = EndpointParser(self.config)
        if dockerOnSocket:
            self.proxyAPI = TrafficLoggingFactory(powerstrip.ServerProtocolFactory(
                    dockerSocket=self.socketPath, config=self.config), "proxy-")
        else:
            self.proxyAPI = TrafficLoggingFactory(
                                powerstrip.ServerProtocolFactory(
                                dockerAddr="127.0.0.1", dockerPort=self.dockerPort,
                                config=self.config), "proxy-")
        self.proxyServer = reactor.listenTCP(0, self.proxyAPI)
        self.proxyPort = self.proxyServer.getHost().port

    def test_empty_endpoints(self):
        """
        The proxy passes through requests when no endpoints are specified.

        In particular, when POST to the /towel endpoint on the *proxy*, we get
        to see that we were seen by the (admittedly fake) Docker daemon.
        """
        self._configure("endpoints: {}\nadapters: {}")
        d = self.client.post('http://127.0.0.1:%d/towel' % (self.proxyPort,),
                      json.dumps({"hiding": "things"}),
                      headers={'Content-Type': ['application/json']})
        d.addCallback(treq.json_content)
        def verify(response):
            self.assertEqual(response,
                    {"hiding": "things", "SeenByFakeDocker": 42})
        d.addCallback(verify)
        return d

    def test_empty_endpoints_socket(self):
        """
        The proxy is able to connect to Docker on a UNIX socket.
        """
        self._configure("endpoints: {}\nadapters: {}", dockerOnSocket=True)
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
        endpoint = "/towel"
        self._configure("""endpoints:
  "POST %s":
    pre: []
    post: []
adapters: {}""" % (endpoint,))
        d = self.client.post('http://127.0.0.1:%d%s' % (self.proxyPort, endpoint),
                             json.dumps({"hiding": "things"}),
                             headers={'Content-Type': ['application/json']})
        d.addCallback(treq.json_content)
        def verify(response):
            self.assertEqual(response,
                    {"hiding": "things", "SeenByFakeDocker": 42})
        d.addCallback(verify)
        return d

    def _getAdder(self, *args, **kw):
        self.adderAPI = TrafficLoggingFactory(AdderPlugin(*args, **kw), "adder-")
        self.adderServer = reactor.listenTCP(0, self.adderAPI)
        self.adderPort = self.adderServer.getHost().port

    def _getAdderTwo(self, *args, **kw):
        kw["incrementBy"] = 2
        self.adderTwoAPI = TrafficLoggingFactory(AdderPlugin(*args, **kw), "adder2-")
        self.adderTwoServer = reactor.listenTCP(0, self.adderTwoAPI)
        self.adderTwoPort = self.adderTwoServer.getHost().port

    def _hookTest(self, config_yml, adderArgs=dict(pre=True), adderTwoArgs=dict(pre=True)):
        """
        Generalised version of a pre-hook test.
        """
        self._getAdder(**adderArgs)
        self._getAdderTwo(**adderTwoArgs)
        self.dockerEndpoint = "/towel"
        self.adapterEndpoint = "/adapter"
        self.args = dict(dockerEndpoint=self.dockerEndpoint,
                         adapterEndpoint=self.adapterEndpoint,
                         adderPort=self.adderPort,
                         adderTwoPort=self.adderTwoPort)
        self._configure(config_yml % self.args)
        self.args["proxyPort"] = self.proxyPort
        d = self.client.post('http://127.0.0.1:%(proxyPort)d%(dockerEndpoint)s' % self.args,
                      json.dumps({"Number": 1}),
                      headers={'Content-Type': ['application/json']})
        d.addCallback(treq.json_content)
        def debug(result, *args, **kw):
            return result
        d.addCallback(debug)
        return d

    def test_adding_pre_hook_adapter(self):
        """
        A adapter has a pre-hook which increments an integral field in the JSON
        POST body called "Number" which starts with value 1.  Calling that
        pre-hook once increments the number to 2.
        """
        d = self._hookTest("""endpoints:
  "POST %(dockerEndpoint)s":
    pre: [adder]
    post: []
adapters:
  adder: http://127.0.0.1:%(adderPort)d%(adapterEndpoint)s""")
        def verify(response):
            self.assertEqual(response,
                    {"Number": 2, "SeenByFakeDocker": 42})
        d.addCallback(verify)
        return d

    def test_adding_pre_hook_twice_adapter(self):
        """
        Chaining pre-hooks: adding twice means you get +2.
        """
        d = self._hookTest("""endpoints:
  "POST %(dockerEndpoint)s":
    pre: [adder, adder2]
    post: []
adapters:
  adder: http://127.0.0.1:%(adderPort)d%(adapterEndpoint)s
  adder2: http://127.0.0.1:%(adderPort)d%(adapterEndpoint)s""")
        def verify(response):
            self.assertEqual(response,
                    {"Number": 3, "SeenByFakeDocker": 42})
        d.addCallback(verify)
        return d

    def test_adding_one_then_two_pre_hook_adapter(self):
        """
        Chaining pre-hooks: adding +1 and then +2 gives you +3.
        """
        d = self._hookTest("""endpoints:
  "POST %(dockerEndpoint)s":
    pre: [adder, adder2]
    post: []
adapters:
  adder: http://127.0.0.1:%(adderPort)d%(adapterEndpoint)s
  adder2: http://127.0.0.1:%(adderTwoPort)d%(adapterEndpoint)s""")
        def verify(response):
            self.assertEqual(response,
                    {"Number": 4, "SeenByFakeDocker": 42})
        d.addCallback(verify)
        return d

    def test_adding_post_hook_adapter(self):
        """
        A adapter has a post-hook which increments an integral field in the JSON
        (Docker) response body called "Number".
        """
        d = self._hookTest("""endpoints:
  "POST %(dockerEndpoint)s":
    pre: []
    post: [adder]
adapters:
  adder: http://127.0.0.1:%(adderPort)d%(adapterEndpoint)s""", adderArgs=dict(post=True))
        def verify(response):
            self.assertEqual(response,
                    {"Number": 2, "SeenByFakeDocker": 42})
        d.addCallback(verify)
        return d

    def test_adding_post_hook_twice_adapter(self):
        """
        Chaining post-hooks: adding twice means you get +2.
        """
        d = self._hookTest("""endpoints:
  "POST %(dockerEndpoint)s":
    pre: []
    post: [adder, adder2]
adapters:
  adder: http://127.0.0.1:%(adderPort)d%(adapterEndpoint)s
  adder2: http://127.0.0.1:%(adderTwoPort)d%(adapterEndpoint)s""",
            adderArgs=dict(post=True),
            adderTwoArgs=dict(post=True))
        def verify(response):
            self.assertEqual(response,
                    {"Number": 4, "SeenByFakeDocker": 42})
        d.addCallback(verify)
        return d

    def test_stream_endpoint(self):
        """
        A streaming (aka hijacking) endpoint like /attach is permitted with no
        post-hooks (the Docker response's content-type is detected and the
        entire connection switched down into simple TCP-proxying mode (with
        support for half-close).
        """
        self._configure("endpoints: {}\nadapters: {}", dockerArgs=dict(rawStream=True))
        d = self.client.post('http://127.0.0.1:%d/towel' % (self.proxyPort,),
                      json.dumps({"raw": "stream"}),
                      headers={'Content-Type': ['application/json']})
        def verify(response):
            self.assertEqual(response.headers.getRawHeaders("content-type"),
                             ["application/vnd.docker.raw-stream"])
            # TODO Verify that half-close, and bi-directional TCP proxying
            # works.
        d.addCallback(verify)
        return d

    def test_chunked_endpoint(self):
        """
        A chunking endpoint like /pull is permitted with no post-hooks (the
        Docker response's Content-Encoding is chunked).
        """
        self._configure("endpoints: {}\nadapters: {}", dockerArgs=dict(chunkedResponse=True))
        d = self.client.post('http://127.0.0.1:%d/towel' % (self.proxyPort,),
                      json.dumps({"chunked": "response"}),
                      headers={'Content-Type': ['application/json']})
        def verify(response):
            self.assertEqual(response.headers.getRawHeaders("content-encoding"),
                             ["chunked"])
        d.addCallback(verify)
        return d

    def test_endpoint_GET_args(self):
        """
        An endpoint is matched when it has ?-style GET arguments (and no JSON
        body), and the GET request is passed through.
        """
        self._configure("endpoints: {}\nadapters: {}", dockerArgs=dict(chunkedResponse=True))
        d = self.client.get('http://127.0.0.1:%d/info?return=fish' % (self.proxyPort,))
        d.addCallback(treq.content)
        def verify(response):
            self.assertEqual(response,
                    "INFORMATION FOR YOU: fish")
        d.addCallback(verify)
        return d

    def test_stream_endpoint_reject_post_hook(self):
        """
        A streaming (aka hijacking) endpoint like /attach is rejected if a
        post-hook is attached: a runtime error is raised when the Content-Type
        is detected.
        """
    test_stream_endpoint_reject_post_hook.skip = "not implemented yet"

    def test_chunked_endpoint_reject_post_hook(self):
        """
        A chunking endpoint like /pull is rejected if a post-hook is attached:
        a runtime error is raised when the Content-Encoding is detected.
        """
    test_chunked_endpoint_reject_post_hook.skip = "not implemented yet"

    def test_prehook_error_does_not_call_docker(self):
        """
        An error in the pre-hook does not call through to Docker and returns
        the error to the user.
        """
    test_prehook_error_does_not_call_docker.skip = "not implemented yet"

    def test_prehook_error_stops_chain(self):
        """
        An error in the pre-hook stops the chain when there are multiple
        pre-hooks.
        """
    test_prehook_error_stops_chain.skip = "not implemented yet"

    def test_posthook_error_stops_chain(self):
        """
        An error in the post-hook stops the chain and returns the error to the
        user.
        """
    test_posthook_error_stops_chain.skip = "not implemented yet"

    def test_docker_error_does_not_stop_posthooks(self):
        """
        If Docker returns an HTTP error code, the post-hooks are given a chance
        to take a look at it/modify it.
        """
    test_docker_error_does_not_stop_posthooks.skip = "not implemented yet"

    def test_second_pre_hook_gets_new_request_and_method(self):
        """
        Chaining pre-hooks: the next pre-hook gets the request and method from
        the previous.
        """
    test_second_pre_hook_gets_new_request_and_method.skip = "not implemented yet"

    def test_second_post_hook_gets_new_request_and_code(self):
        """
        Chaining post-hooks: the next post-hook gets the request and code from
        the previous.  Also content-type.
        """
    test_second_post_hook_gets_new_request_and_code.skip = "not implemented yet"

    def test_endpoint_globbing(self):
        """
        An endpoint is matched when there are '*' characters in the string
        """
    test_endpoint_globbing.skip = "not implemented yet"
