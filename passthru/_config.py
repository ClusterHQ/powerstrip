# Copyright ClusterHQ Limited. See LICENSE file for details.
# -*- test-case-name: powerstrip.test.test_config -*-

from collections import namedtuple

class NoConfiguration(Exception):
    """
    The configuration file was not found.
    """


class InvalidConfiguration(Exception):
    """
    The configuration file content was not valid.
    """


class PluginConfiguration(object):
    """
    Read and parse a plugin configuration from a YAML file.
    """

    _default_file = b"/etc/powerstrip/plugins.yml"

    def __init__(self):
        """
        Initializes ``PluginConfiguration`` attributes.

        self._endpoints: A dict of Docker API endpoint expressions mapping to
            dicts ``pre`` and ``post`` plugin lists. Each plugin in the plugins
            references the ``_plugins`` attribute.

        self._plugins: A dict mapping plugin names to URIs.
        """
        self._endpoints = {}
        self._plugins = {}

    def read_and_parse(self):
        """
        Read and parse the plugin configuration.
        """
        self.__init__() # reset all attributes

    def _read_from_yaml_file(self, path):
       """
       Read the plugin config YAML file and return the YAML datastructure.

       :param path: The path to the YAML file, or self._default_file if None.
       """

    def _parse_plugins(self, datastructure):
        """
        Take the decoded YAML configuration and store it as usable
        datastructures. See ``self.__init__``.
        """

    def endpoints(self):
        """
        Return a ``list`` of endpoint expressions.
        """

    def endpoint(self, endpoint):
        """
        Return the plugin configuration for the endpoint expression returned by
        ``self.endpoints``. This is an ``EndppointConfiguration` object with attrbutes
        ``pre`` and ``post``. These attributes are lists of plugin names.
        """

    def plugins(self):
        """
        Return a ``list`` of known plugins.
        """

    def plugin_uri(self):
        """
        Return the URI for a plugin.
        """

class EndppointConfiguration(namedtuple("pre", "post")):
    """
    A representation of the configured plugins for an endpoint.

    :param pre: A plugin ``list`` to call before passing this call to Docker.

    :param post: A plugin ``list`` to call after passing this call to Docker.
    """
