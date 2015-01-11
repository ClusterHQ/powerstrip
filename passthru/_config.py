# Copyright ClusterHQ Limited. See LICENSE file for details.
# -*- test-case-name: powerstrip.test.test_config -*-

from collections import namedtuple

from twisted.python.filepath import FilePath
from yaml import safe_load
from yaml.error import YAMLError

class NoConfiguration(Exception):
    """
    The configuration file was not found.
    """

    def __init__(self, path):
        self.path = path
        super(NoConfiguration, self).__init__(
            b"The plugin configuration file '%s' was not found." % (self.path))


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

        :raises: ``InvalidConfiguration`` if the file was not valid configuration.
        """
        self.__init__() # reset all attributes

    def _read_from_yaml_file(self, path):
        """
        Read the plugin config YAML file and return the YAML datastructure.

        :param path: A ``FilePath`` representing the path to the YAML file, or
            self._default_file if None.

        :raises: ``NoConfiguration`` if the plugin file was not found.

        :raises: ``InvalidConfiguration`` if if the file was not valid YAML.
        """
        if path is None:
            path = FilePath(self._default_file)
        try:
            content = path.getContent()
        except IOError:
            raise NoConfiguration(path.path)

        try:
            yaml = safe_load(content)
            return yaml
        except YAMLError:
            raise InvalidConfiguration()

    def _parse_plugins(self, datastructure):
        """
        Take the decoded YAML configuration and store it as usable
        datastructures. See ``self.__init__``.

        :raises: ``InvalidConfiguration`` if the configuration is invalid.
        """
        try:
            self._endpoints = datastructure["endpoints"]
        except KeyError:
            raise InvalidConfiguration("Required key 'endpoints' is missing.")
        try:
            self._plugins = datastructure["plugins"]
        except KeyError:
            raise InvalidConfiguration("Required key 'plugins' is missing.")

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
