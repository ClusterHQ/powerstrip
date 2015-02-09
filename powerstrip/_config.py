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
            b"The adapter configuration file '%s' was not found." % (self.path))


class InvalidConfiguration(Exception):
    """
    The configuration file content was not valid.
    """


class PluginConfiguration(object):
    """
    Read and parse a adapter configuration from a YAML file.
    """

    _default_file = b"/etc/powerstrip/adapters.yml"

    def __init__(self):
        """
        Initializes ``PluginConfiguration`` attributes.

        self._endpoints: A dict of Docker API endpoint expressions mapping to
            dicts ``pre`` and ``post`` adapter lists. Each adapter in the adapters
            references the ``_adapters`` attribute.

        self._adapters: A dict mapping adapter names to URIs.
        """
        self._endpoints = {}
        self._adapters = {}

    def read_and_parse(self):
        """
        Read and parse the adapter configuration.

        :raises: ``NoConfiguration`` if the configuration file was not found.

        :raises: ``InvalidConfiguration`` if the file was not valid configuration.
        """
        self.__init__() # reset all attributes
        config_struct = self._read_from_yaml_file(None)
        self._parse_adapters(config_struct)

    def _read_from_yaml_file(self, path):
        """
        Read the adapter config YAML file and return the YAML datastructure.

        :param path: A ``FilePath`` representing the path to the YAML file, or
            self._default_file if None.

        :raises: ``NoConfiguration`` if the adapter file was not found.

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

    def _parse_adapters(self, datastructure):
        """
        Take the decoded YAML configuration and store it as usable
        datastructures. See ``self.__init__``.

        :raises: ``InvalidConfiguration`` if the configuration is invalid.
        """
        try:
            self._endpoints = datastructure["endpoints"]
        except KeyError:
            raise InvalidConfiguration("Required key 'endpoints' is missing.")
        except TypeError:
            raise InvalidConfiguration("Could not parse adapters file.")
        try:
            self._adapters = datastructure["adapters"]
        except KeyError:
            raise InvalidConfiguration("Required key 'adapters' is missing.")

        # Sanity check that all referenced adapters exist and that optional pre
        # and post keys are added, with no unknown keys
        known_adapters = self.adapters()
        referenced_adapters = set()
        for endpoint, config in self._endpoints.iteritems():
            config_keys = set(config.keys())
            if not config_keys:
                raise InvalidConfiguration(
                    "No configuration found for endpoint '%s'" % (endpoint,))

            unknown_keys = config_keys - set(["pre", "post"])
            if unknown_keys:
                raise InvalidConfiguration(
                    "Unkonwn keys found in endpoint configuration: %s" %
                        (", ".join(unknown_keys)))

            if "pre" not in config:
                config['pre'] = []
            if "post" not in config:
                config['post'] = []

            referenced_adapters.update(config['pre'])
            referenced_adapters.update(config['post'])

        unkown_adapters = referenced_adapters - known_adapters
        if unkown_adapters:
            raise InvalidConfiguration(
                "Plugins were referenced in endpoint configuration but not "
                "defined: %s" % (", ".join(unkown_adapters)))

    def endpoints(self):
        """
        Return a ``set`` of endpoint expressions.
        """
        return set(self._endpoints.keys())

    def endpoint(self, endpoint):
        """
        Return the adapter configuration for the endpoint expression returned by
        ``self.endpoints``. This is an ``EndpointConfiguration` object with attrbutes
        ``pre`` and ``post``. These attributes are lists of adapter names.

        :raises: `KeyError` if the endpoint expression was not found.
        """
        return EndpointConfiguration(**self._endpoints[endpoint])

    def adapters(self):
        """
        Return a ``set`` of known adapters.
        """
        return set(self._adapters.keys())

    def adapter_uri(self, adapter):
        """
        Return the URI for a adapter.

        :param ``adapter``: The the desired adapter.

        :raises: `KeyError` if the adapter was not found.
        """
        return self._adapters[adapter]


class EndpointConfiguration(namedtuple("EndpointConfiguration", ["pre", "post"])):
    """
    A representation of the configured adapters for an endpoint.

    :param pre: A adapter ``list`` to call before passing this call to Docker.

    :param post: A adapter ``list`` to call after passing this call to Docker.
    """
