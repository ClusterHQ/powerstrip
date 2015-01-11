# Copyright ClusterHQ Limited. See LICENSE file for details.

"""
Tests for ``powerstrip._config``.
"""

from twisted.trial.unittest import TestCase
from twisted.python.filepath import FilePath

from .._config import PluginConfiguration, NoConfiguration, InvalidConfiguration

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
            "plugins": {
                "flocker": "http://flocker/flocker-plugin",
                "weave": "http://weave/weave-plugin",
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

    def test_parse_good_plugins(self):
        """
        ``_parse_plugins`` reads a valid datastructure and populates relevant
        attirbutes on the class.
        """
        self.config._parse_plugins(self.good_config)

        self.assertEquals((self.config._endpoints, self.config._plugins), ({
                "POST /*/containers/create": {
                    "pre": ["flocker", "weave"],
                    "post": ["weave", "flocker"],
                },
                "DELETE /*/containers/*": {
                    "pre": ["flocker", "weave"],
                    "post": ["weave", "flocker"],
                },
            }, {
                "flocker": "http://flocker/flocker-plugin",
                "weave": "http://weave/weave-plugin",
            }))

    def test_parse_plugins_missing_endpoints(self):
        """
        ``_parse_plugins`` raises ``InvalidConfiguration` when the endpoints
        key is missing.
        """
        del self.good_config['endpoints']
        self.assertRaises(InvalidConfiguration, self.config._parse_plugins, self.good_config)

    def test_parse_plugins_missing_plugins(self):
        """
        ``_parse_plugins`` raises ``InvalidConfiguration` when the plugins
        key is missing.
        """
        del self.good_config['plugins']
        self.assertRaises(InvalidConfiguration, self.config._parse_plugins, self.good_config)
