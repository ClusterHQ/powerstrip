# Copyright ClusterHQ Limited. See LICENSE file for details.

"""
Tests for ``powerstrip._config``.
"""

from twisted.trial.unittest import TestCase
from twisted.python.filepath import FilePath

from .._config import (
        PluginConfiguration, NoConfiguration, InvalidConfiguration,
        EndpointConfiguration)

class PluginConfigurationTests(TestCase):
    """
    Tests for ``PluginConfiguration``.
    """

    def setUp(self):
        self.config = PluginConfiguration()
        self.good_config = {
            "endpoints": {
                "POST /*/containers/create": {
                    "pre": ["flocker", "weave"],
                    "post": ["weave", "flocker"],
                },
                "DELETE /*/containers/*": {
                    "pre": ["flocker", "weave"],
                    "post": ["weave", "flocker"],
                },
            },
            "adapters": {
                "flocker": "http://flocker/flocker-adapter",
                "weave": "http://weave/weave-adapter",
            },
        }

    def test_read_from_yaml_file_success(self):
        """
        ``_read_from_yaml_file`` returns the file's content.
        """
        content = "ducks: cows"
        fp = FilePath(self.mktemp())
        fp.setContent(content)

        result = self.config._read_from_yaml_file(fp)

        self.assertEquals(result, {"ducks": "cows"})

    def test_read_from_yaml_file_missing(self):
        """
        ``_read_from_yaml_file`` raises ``NoConfiguration`` if the file does not exist.
        """
        fp = FilePath("improbable_chickens")

        self.assertRaises(NoConfiguration, self.config._read_from_yaml_file, fp)

    def test_read_from_yaml_file_invalid(self):
        """
        ``_read_from_yaml_file`` raises ``NoConfiguration`` if the file is not valid YAML.
        """
        content = "{' unclosed"
        fp = FilePath(self.mktemp())
        fp.setContent(content)

        self.assertRaises(InvalidConfiguration, self.config._read_from_yaml_file, fp)

    def test_read_from_yaml_file_default_file(self):
        """
        ``_read_from_yaml_file`` reads ``PluginConfiguration._default_file`` if
        the path supplied is ``None``.
        """
        try:
            self.config._read_from_yaml_file(None)
        except NoConfiguration, e:
            self.assertEquals(e.path, PluginConfiguration._default_file)

    def test_parse_good_adapters(self):
        """
        ``_parse_adapters`` reads a valid datastructure and populates relevant
        attirbutes on the class.
        """
        self.config._parse_adapters(self.good_config)

        self.assertEquals((self.config._endpoints, self.config._adapters), ({
                "POST /*/containers/create": {
                    "pre": ["flocker", "weave"],
                    "post": ["weave", "flocker"],
                },
                "DELETE /*/containers/*": {
                    "pre": ["flocker", "weave"],
                    "post": ["weave", "flocker"],
                },
            }, {
                "flocker": "http://flocker/flocker-adapter",
                "weave": "http://weave/weave-adapter",
            }))

    def test_endpoints(self):
        """
        ``endpoints`` returns a ``set`` of configured endpoint expressions.
        """
        self.config._parse_adapters(self.good_config)
        endpoints = self.config.endpoints()
        self.assertEquals(endpoints, set([
            "POST /*/containers/create",
            "DELETE /*/containers/*",
        ]))

    def test_endpoint(self):
        """
        ``endpoint`` returns the desired endpoint configuration.
        """
        self.config._parse_adapters(self.good_config)
        endpoint_config = self.config.endpoint("POST /*/containers/create")
        self.assertEquals(endpoint_config, EndpointConfiguration(
                pre=["flocker", "weave"],
                post=["weave", "flocker"]))

    def test_endpoint_error(self):
        """
        ``endpoint`` raises ``KeyError`` if the endpoint expression does not
        exist.
        """
        self.config._parse_adapters(self.good_config)
        self.assertRaises(KeyError, self.config.endpoint, "POST /*/bogus/expression")

    def test_adapters(self):
        """
        ``adapters`` returns a ``set`` of configured adapters.
        """
        self.config._parse_adapters(self.good_config)
        adapters = self.config.adapters()
        self.assertEquals(adapters, set(["flocker", "weave"]))

    def test_adapter_uri(self):
        """
        ``adapter_uri`` returns the URI for a configured adapter.
        """
        self.config._parse_adapters(self.good_config)
        uri = self.config.adapter_uri("flocker")
        self.assertEquals(uri, "http://flocker/flocker-adapter")

    def test_adapter_uri_error(self):
        """
        ``adapter_uri`` returns the URI for a configured adapter.
        """
        self.config._parse_adapters(self.good_config)
        self.assertRaises(KeyError, self.config.adapter_uri, "bad_adapter")


class ReadAndParseTests(TestCase):
    """
    Tests for ``PluginConfiguration.read_and_parse``.
    """

    def setUp(self):
        self.config = PluginConfiguration()

    def test_single_run(self):
        """
        Running for the first time successfully reads and parses the configuration.
        """
        yml = """endpoints:
  # adapters are applied in order
  "POST /*/containers/create":
    pre: [flocker, weave]
    post: [weave, flocker]
  "DELETE /*/containers/*":
    pre: [flocker, weave]
    post: [weave, flocker]
adapters:
  flocker: http://flocker/flocker-adapter
  weave: http://weave/weave-adapter"""
        tmp = self.mktemp()
        self.config._default_file = tmp
        fp = FilePath(tmp)
        fp.setContent(yml)
        
        self.config.read_and_parse()

        self.assertEquals((self.config._endpoints, self.config._adapters), ({
                "POST /*/containers/create": {
                    "pre": ["flocker", "weave"],
                    "post": ["weave", "flocker"],
                },
                "DELETE /*/containers/*": {
                    "pre": ["flocker", "weave"],
                    "post": ["weave", "flocker"],
                },
            }, {
                "flocker": "http://flocker/flocker-adapter",
                "weave": "http://weave/weave-adapter",
            }))

    def test_no_config(self):
        """
        If the configuration file does not exist, ``NoConfiguration`` is raised.
        """
        self.config._default_file = "improbable_chickens"

        self.assertRaises(NoConfiguration, self.config.read_and_parse)

    def test_bad_config(self):
        """
        If the configuration file is bad, an ``InvalidConfiguration`` is raised.
        """
        yml = "this is garbage"
        tmp = self.mktemp()
        self.config._default_file = tmp
        fp = FilePath(tmp)
        fp.setContent(yml)
        
        self.assertRaises(InvalidConfiguration, self.config.read_and_parse)

    def test_config_change(self):
        """
        If the config is changed, the new config is reflected.
        """
        yml = """endpoints:
  # adapters are applied in order
  "POST /*/containers/create":
    pre: [flocker, weave]
    post: [weave, flocker]
  "DELETE /*/containers/*":
    pre: [flocker, weave]
    post: [weave, flocker]
adapters:
  flocker: http://flocker/flocker-adapter
  weave: http://weave/weave-adapter"""
        tmp = self.mktemp()
        self.config._default_file = tmp
        fp = FilePath(tmp)
        fp.setContent(yml)
        
        self.config.read_and_parse()

        self.assertEquals((self.config._endpoints, self.config._adapters), ({
                "POST /*/containers/create": {
                    "pre": ["flocker", "weave"],
                    "post": ["weave", "flocker"],
                },
                "DELETE /*/containers/*": {
                    "pre": ["flocker", "weave"],
                    "post": ["weave", "flocker"],
                },
            }, {
                "flocker": "http://flocker/flocker-adapter",
                "weave": "http://weave/weave-adapter",
            }))

        yml = """endpoints:
  # adapters are applied in order
  "POST /*/containers/stop":
    pre: [flocker]
adapters:
  flocker: http://flocker/flocker-adapter"""
        tmp = self.mktemp()
        self.config._default_file = tmp
        fp = FilePath(tmp)
        fp.setContent(yml)
        
        self.config.read_and_parse()

        self.assertEquals((self.config._endpoints, self.config._adapters), ({
                "POST /*/containers/stop": {
                    "pre": ["flocker"],
                    "post": [],
                },
            }, {
                "flocker": "http://flocker/flocker-adapter",
            }))


class ConfigurationValidationTests(TestCase):
    """
    Tests for validation in ``PluginConfiguration._parse_adapters``.
    """

    def setUp(self):
        self.config = PluginConfiguration()
        self.good_config = {
            "endpoints": {
                "POST /*/containers/create": {
                    "pre": ["flocker", "weave"],
                    "post": ["weave", "flocker"],
                },
                "DELETE /*/containers/*": {
                    "pre": ["flocker", "weave"],
                    "post": ["weave", "flocker"],
                },
            },
            "adapters": {
                "flocker": "http://flocker/flocker-adapter",
                "weave": "http://weave/weave-adapter",
            },
        }

    def test_missing_endpoints(self):
        """
        ``_parse_adapters`` raises ``InvalidConfiguration` when the endpoints
        key is missing.
        """
        del self.good_config['endpoints']
        self.assertRaises(InvalidConfiguration, self.config._parse_adapters, self.good_config)

    def test_missing_adapters(self):
        """
        ``_parse_adapters`` raises ``InvalidConfiguration` when the adapters
        key is missing.
        """
        del self.good_config['adapters']
        self.assertRaises(InvalidConfiguration, self.config._parse_adapters, self.good_config)

    def test_unkown_endpoint_keys(self):
        """
        Keys except "pre" and "post" are invalid in endpoints.
        """
        self.good_config['endpoints']['POST /*/containers/create']['bad_key'] = "value"
        self.assertRaises(InvalidConfiguration, self.config._parse_adapters, self.good_config)

    def test_no_endpoint_keys(self):
        """
        One of "pre" or "post" is required in an endpoint configuration.
        """
        self.good_config['endpoints']['POST /*/containers/create'] = {}
        self.assertRaises(InvalidConfiguration, self.config._parse_adapters, self.good_config)

    def test_optional_pre(self):
        """
        ``pre`` is an optional configuration key.
        """
        del self.good_config['endpoints']['POST /*/containers/create']['pre']
        self.config._parse_adapters(self.good_config)
        endpoint_config = self.config.endpoint("POST /*/containers/create")
        self.assertEquals(endpoint_config.pre, [])
        
    def test_optional_post(self):
        """
        ``post`` is an optional configuration key.
        """
        del self.good_config['endpoints']['POST /*/containers/create']['post']
        self.config._parse_adapters(self.good_config)
        endpoint_config = self.config.endpoint("POST /*/containers/create")
        self.assertEquals(endpoint_config.post, [])
        
    def test_missing_defined_adapters(self):
        """
        If a adapter is referenced in an endpoint which does not exist, an ``InvalidConfiguration`` is raised.
        """
        del self.good_config['adapters']['flocker']
        self.assertRaises(InvalidConfiguration, self.config._parse_adapters, self.good_config)


class EndpointConfigurationTests(TestCase):
    """
    Tests for ``EndpointConfiguration``.
    """

    def test_attributes(self):
        """
        The ``pre`` and ``post`` attributes are set correctly.
        """

        endpoint_config = EndpointConfiguration(pre="foo", post="bar")
        self.assertEquals((endpoint_config.pre, endpoint_config.post),
            ("foo", "bar"))
