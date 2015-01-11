# Copyright ClusterHQ Limited. See LICENSE file for details.
# -*- test-case-name: powerstrip.test.test_parser -*-

import fnmatch

class EndpointParser(object):
    """
    Class to translate incoming requests into chains of plugins.
    """

    def __init__(self, config):
        """
        :param config: A ``PluginConfiguration`` object which has already read the current configuration.
        """
        self.config = config

    def match_endpoint(self, method, request):
        """
        Return a ``set`` of endpoint expressions which match the provided
            ``method`` and ``request``. The items in this list can be provided
            to ``PluginConfiguration.endpoint`` to get the plugin
            configuration.

        :param method: An HTTP method string, e.g. "GET" or "POST".

        :param request: An HTTP request path string, e.g. "/v1/containers/create".

        :return: The set of endpoint expressions to be provided to
            ``PluginConfiguration.endpoint``.

        :raises: If the request containers a query part, an InvalidRequest is raised.
        """

        all_endpoints = self.config.endpoints()
        match_str = "%s %s" % (method, request)
        return set(fnmatch.filter(all_endpoints, match_str))
