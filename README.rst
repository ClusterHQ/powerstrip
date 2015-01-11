Powerstrip: The missing Docker extensions API
=============================================

.. image:: powerstrip.jpg

Easily attach chained blocking webhooks to arbitrary Docker API calls.

Enables composition of prototypical `Docker extensions <https://clusterhq.com/blog/docker-extensions/>`_.
Intended to allow quick prototyping of plugins, in order to figure out which integration points are needed in order to turn such prototypical plugins into `real Docker extensions <https://github.com/docker/docker/issues/9983>`_.

Inspired by https://github.com/docker/docker/issues/6982

*A note on nomenclature:* we are calling Powerstrip plugins "plugins" because it works with the powerstrip metaphor, and may help disambiguate Powerstrip **plugins** from the Docker **extensions** they are prototyping.


Goal of project
---------------

It should eventually be possible to run a powerstrip-enabled Docker Swarm with Flocker and Weave both loaded as extensions.

.. code:: yaml

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

This will allow moving (rescheduling) stateful containers while they keep their Weave IP and their volumes intact.


Try it out
----------

Powerstrip ships as a Docker image.

`Slowreq <https://github.com/clusterhq/powerstrip-slowreq>`_ is a trivial powerstrip plugin which adds a 1 second delay to all create commands.

Try it out like this:

.. code:: sh

    $ mkdir ~/powerstrip-demo
    $ cat > ~/powerstrip-demo/plugins.yml <<EOF
    endpoints:
      "/*/containers/create":
        pre: [slowreq]
    plugins:
      slowreq: http://slowreq/v1/extension
    EOF

    $ docker run -d --name powerstrip-slowreq \
               --expose 80 \
               clusterhq/powerstrip-slowreq
    $ docker run -d --name powerstrip \
               -v /var/run/docker.sock:/var/run/docker.sock \
               -v ~/powerstrip-demo/plugins.yml:/etc/powerstrip/plugins.yml \
               --link powerstrip-slowreq:slowreq
               -p 2375:2375 \
               clusterhq/powerstrip

    # Note how the following command takes a second longer than normal.
    $ export DOCKER_HOST=localhost:2375
    $ docker run ubuntu echo hello


Writing a plugin
----------------

Pre-hook plugin endpoints receive POSTs like this:

.. code:: http

    POST /flocker-plugin HTTP/1.0
    Content-type: application/json
    Content-length: ...

    {
        method: "POST",
        request: "/v1.16/container/create",
        body: { ... },
    }

And they respond with:

.. code:: http

    HTTP 200 OK
    Content-type: application/json

    {
        responsecode: 404,
        body: { ... }
    }

Or they respond with an HTTP error code, in which case the call is never passed through to the Docker daemon, and instead returned straight back to the user.


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


Pseudocode:

.. code:: python

    def postToPlugin(uri, jsonRequest):
        """
        returns a Deferred which fires with either:
            * the responsecode and responsebody returned by the plugin.
            * a Failure object if the plugin was (a) unreachable or (b) returned an HTTP error code (possibly because it wanted to prevent the request being passed through to the Docker API).
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
