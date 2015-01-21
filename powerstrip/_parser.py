# Copyright ClusterHQ Limited. See LICENSE file for details.
# -*- test-case-name: powerstrip.test.test_parser -*-

import fnmatch

class InvalidRequest(Exception):
    """
    The request was not valid.
    """


class EndpointParser(object):
    """
    Translate incoming requests into chains of adapters.
    """

    def __init__(self, config):
        """
        :param config: A ``PluginConfiguration`` object which has already read
        the current configuration.
        """
        self.config = config

    def match_endpoint(self, method, request):
        """
        Return a ``set`` of endpoint expressions which match the provided
            ``method`` and ``request``. The items in this set can be provided
            to ``PluginConfiguration.endpoint`` to get the adapter
            configuration.

        :param method: An HTTP method string, e.g. "GET" or "POST".

        :param request: An HTTP request path string, e.g. "/v1/containers/create".

        :return: The set of endpoint expressions to be provided to
            ``PluginConfiguration.endpoint``.

        :raises: If the request containers a query part, an ``InvalidRequest`` is raised.
        """
        if "?" in request:
            raise InvalidRequest()
        all_endpoints = self.config.endpoints()
        match_str = "%s %s" % (method, request)
        matched_endpoints = set()
        # Note: fnmatch.filter seemed to be broken when trying to do exaclty this.
        for endpoint in all_endpoints:
            if fnmatch.fnmatch(match_str, endpoint):
                matched_endpoints.add(endpoint)
        return matched_endpoints
