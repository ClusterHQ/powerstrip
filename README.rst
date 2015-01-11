Powerstrip: The missing Docker extensions API
=============================================

.. image:: powerstrip.jpg

Easily attach chained blocking webhooks to arbitrary Docker API calls.

Enables composition of prototypical `Docker extensions <https://clusterhq.com/blog/docker-extensions/>`_.
Intended to allow quick prototyping of plugins, in order to figure out which integration points are needed to turn such prototypical extensions into `real Docker extensions <https://github.com/docker/docker/issues/9983>`_.

Inspired by https://github.com/docker/docker/issues/6982

Configuration
-------------

For example::

    endpoints:
      # plugins are applied in order
      "/*/containers/create":
        pre: [flocker, weave]
        post: [weave, flocker]
      "/*/containers/*/attach":
        pre: [flocker, weave]
        post: [weave, flocker]
    plugins:
      flocker: http://flocker/flocker-plugin
      weave: http://flocker/weave-plugin


Try it out
----------

The following will start a powerstrip-enabled Docker Swarm with Flocker and Weave pre-loaded::

    git clone git@github.com:clusterhq/powerstrip
    cd powerstrip
    vagrant up

    # XXX this doesn't work yet

Writing a plugin
----------------

Pre-hook plugin endpoints receive POSTs like this::

    POST /flocker-plugin HTTP/1.0
    Content-type: application/json
    Content-length: ...

    {
        method: "POST",
        request: "/v1.16/container/create",
        body: { ... },
    }

And they respond with::

    HTTP 200 OK
    Content-type: application/json

    {
        responsecode: 404,
        body: { ... }
    }


Recommended deployment
----------------------

Powerstrip runs in a container.

For now, it does not support TLS, but given that it should only be used for prototyping in local development environments, that's OK.

It's recommended that plugins run in containers that are linked (with Docker links) to the proxy container.
Plugins should listen on port 80.

Then you can just specify the URL using e.g. http://flocker/ as below, assuming "flocker" is the link alias.


Contributing
------------

Plan to use CI from https://drone.io/ for unit tests.
Integration tests will exist but only get run manually for now.


Configuration in detail
-----------------------

* '*' in the endpoint definition means "any string can exist in this URL path segment".
* Any arguments after a '?' get stripped when comparing endpoints.


How it works
------------

There are a few different paths that an HTTP request can take:

* Client req => Plugin pre-hook returns OK => Docker => Plugin post-hook => Client response
* Client req => Plugin pre-hook returns error code => error response to client (don't pass through request to Docker)
* Client req => Plugin pre-hook => Docker => Error response from Docker to plugin post-hook => Pass through error response to client
* Client req => Plugin pre-hook => Docker => Plugin post-hook => error response to client


Pseudocode::

    def postToPlugin(uri, jsonRequest):
        """
        returns a Deferred which fires with either:
            * the responsecode and responsebody returned by the plugin.
            * a Failure object if the plugin was (a) unreachable or (b) returned an HTTP error code (possibly because it wanted to prevent the request being passed through to the Docker API.
        """

    plugins = [flocker, weave]
    def receive_req_from_client(method, request, body):
        d = defer.succeed(None)
        for plugin in plugins:
            d.addCallback(postToPlugin, flocker.uri, dict(method=method, request=request, body=body))
        def sendErrorToClient():
            pass
        d.addErrback(sendErrorToClient)
        return d


    dockthru
