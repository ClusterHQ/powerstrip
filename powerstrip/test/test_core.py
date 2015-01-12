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

class ProxyTests(TestCase):

    def setUp(self):
        """
        Construct a fake "Docker daemon" (one which does much less than the
        actual Docker daemon) and a Proxy instance.

        Pre- and post-hook API servers are provided by the individual tests.
        """
        self.dockerAPI = testtools.FakeDockerServer()
        self.dockerServer = reactor.listenTCP(0, self.dockerAPI)
        self.dockerPort = self.dockerServer.getHost().port

        self.agent = Agent(reactor) # no connectionpool
        self.client = HTTPClient(self.agent)

    def tearDown(self):
        shutdowns = [
            self.dockerServer.stopListening(),
            self.proxyServer.stopListening()]
        if hasattr(self, 'adderServer'):
            shutdowns.append(self.adderServer.stopListening())
        return defer.gatherResults(shutdowns)

    def _get_proxy_instance(self, configuration):
        """
        Given a yaml configuration (with placeholders for interpolation of
        current runtime ports for the test), return an appropriately configured
        proxy instance.
        """

    def _configure(self, config_yml):
        self.config = PluginConfiguration()
        tmp = self.mktemp()
        self.config._default_file = tmp
        fp = FilePath(tmp)
        fp.setContent(config_yml)
        self.config.read_and_parse()
        self.parser = EndpointParser(self.config)
        self.proxyAPI = powerstrip.ServerProtocolFactory(
                dockerAddr="127.0.0.1", dockerPort=self.dockerPort,
                config=self.config)
        self.proxyServer = reactor.listenTCP(0, self.proxyAPI)
        self.proxyPort = self.proxyServer.getHost().port

    def test_empty_endpoints(self):
        """
        The proxy passes through requests when no endpoints are specified.

        In particular, when POST to the /towel endpoint on the *proxy*, we get
        to see that we were seen by the (admittedly fake) Docker daemon.
        """
        self._configure("endpoints: {}\nplugins: {}")
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
plugins: {}""" % (endpoint,))
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
        self.adderAPI = AdderPlugin(*args, **kw)
        self.adderServer = reactor.listenTCP(0, self.adderAPI)
        self.adderPort = self.adderServer.getHost().port


    def _preHookTest(self, config_yml):
        """
        Generalised version of a pre-hook test.
        """
        self._getAdder(pre=True)
        self.dockerEndpoint = "/towel"
        self.pluginEndpoint = "/plugin"
        self.args = dict(dockerEndpoint=self.dockerEndpoint,
                    pluginEndpoint=self.pluginEndpoint,
                    adderPort=self.adderPort)
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


    def test_adding_pre_hook_plugin(self):
        """
        A plugin has a pre-hook which increments an integral field in the JSON
        POST body called "Number".

        TODO: Assert that Docker saw it, as well as that it came out the end.
        """
        d = self._preHookTest("""endpoints:
  "POST %(dockerEndpoint)s":
    pre: [adder]
    post: []
plugins:
  adder: http://127.0.0.1:%(adderPort)d%(pluginEndpoint)s""")
        def verify(response):
            self.assertEqual(response,
                    {"Number": 2, "SeenByFakeDocker": 42})
        d.addCallback(verify)
        return d

    def test_adding_pre_hook_twice_plugin(self):
        """
        Chaining pre-hooks: adding twice means you get +2.
        """
        d = self._preHookTest("""endpoints:
  "POST %(dockerEndpoint)s":
    pre: [adder, adder2]
    post: []
plugins:
  adder: http://127.0.0.1:%(adderPort)d%(pluginEndpoint)s
  adder2: http://127.0.0.1:%(adderPort)d%(pluginEndpoint)s""")
        def verify(response):
            self.assertEqual(response,
                    {"Number": 3, "SeenByFakeDocker": 42})
        d.addCallback(verify)
        return d

    def test_second_pre_hook_gets_new_request_and_method(self):
        """
        Chaining pre-hooks: the next pre-hook gets the request and method from
        the previous.
        """
    test_second_pre_hook_gets_new_request_and_method.skip = "not implemented yet"

    def test_adding_post_hook_plugin(self):
        """
        A plugin has a post-hook which increments an integral field in the JSON
        (Docker) response body called "Number".
        """
    test_adding_post_hook_plugin.skip = "not implemented yet"

    def test_adding_post_hook_twice_plugin(self):
        """
        Chaining post-hooks: adding twice means you get +2.
        """
    test_adding_post_hook_twice_plugin.skip = "not implemented yet"

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

    def test_endpoint_GET_args(self):
        """
        An endpoint is matched when the GET arguments change.
        """
    test_endpoint_GET_args.skip = "not implemented yet"

    def test_endpoint_globbing(self):
        """
        An endpoint is matched when there are '*' characters in the string
        """
    test_endpoint_globbing.skip = "not implemented yet"

    def test_stream_endpoint(self):
        """
        A streaming (aka hijacking) endpoint like /attach is rejected from
        endpoints: a runtime error is raised when the Content-Type is detected.
        """
    test_stream_endpoint.skip = "not implemented yet"

    def test_chunked_endpoint(self):
        """
        A chunking endpoint like /pull is rejected from endpoints: a runtime
        error is raised when the Content-Encoding is detected.
        """
    test_chunked_endpoint.skip = "not implemented yet"
