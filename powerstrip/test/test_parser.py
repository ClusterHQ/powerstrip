# Copyright ClusterHQ Limited. See LICENSE file for details.
# -*- test-case-name: powerstrip.test.test_parser -*-

from twisted.trial.unittest import TestCase
from twisted.python.filepath import FilePath

from .._config import PluginConfiguration
from .._parser import EndpointParser, InvalidRequest

class EndpointParserTests(TestCase):
    """
    Tests for ``EndpointParser``.
    """

    def setUp(self):
        config_yml = """endpoints:
  "POST /v1.16/containers/create":
    pre: [alpha, beta, gamma]
    post: [alpha, gamma]
  "GET /v1.16/images/*/json":
    pre: [gamma]
  "* /v*/images/*/json":
    post: [beta]
plugins:
  alpha: http://alpha/alpha
  beta: http://beta/beta
  gamma: http://gamma/gamma"""
        self.config = PluginConfiguration()
        tmp = self.mktemp()
        self.config._default_file = tmp
        fp = FilePath(tmp)
        fp.setContent(config_yml)
        
        self.config.read_and_parse()

        self.parser = EndpointParser(self.config)

    def test_exact(self):
        """
        An exact endpoint is matched.
        """
        endpoint = self.parser.match_endpoint("POST", "/v1.16/containers/create")
        self.assertEquals(endpoint, set(["POST /v1.16/containers/create"]))

    def test_matched(self):
        """
        Requests are expanded.
        """
        endpoint = self.parser.match_endpoint("GET", "/v2/images/alpha/json")
        self.assertEquals(endpoint, set(["* /v*/images/*/json"]))

    def test_multiple(self):
        """
        Multiple endpoints can be matched.
        """
        endpoint = self.parser.match_endpoint("GET", "/v1.16/images/*/json")
        self.assertEquals(endpoint,
                set(["GET /v1.16/images/*/json", "* /v*/images/*/json"]))

    def test_config_changed(self):
        """
        The parser responds with new endpoints after the config has changed.
        """
        endpoint = self.parser.match_endpoint("POST", "/v1.16/containers/create")
        self.assertEquals(endpoint, set(["POST /v1.16/containers/create"]))

        config_yml = """endpoints:
  "GET /info":
    post: [gamma]
plugins:
  alpha: http://alpha/alpha
  beta: http://beta/beta
  gamma: http://gamma/gamma"""
        fp = FilePath(self.config._default_file)
        fp.setContent(config_yml)
        self.config.read_and_parse()

        endpoint = self.parser.match_endpoint("GET", "/info")
        self.assertEquals(endpoint, set(["GET /info"]))

    def test_query_error(self):
        """
        The parser raises ```InvalidRequest`` if the request contains a query part.
        """
        self.assertRaises(InvalidRequest, self.parser.match_endpoint, "GET", "/foo?bar")
