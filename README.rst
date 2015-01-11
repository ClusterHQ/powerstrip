Powerstrip: The missing Docker extensions API
=============================================

.. image:: powerstrip.jpg

Powerstrip is a pluggable HTTP proxy for Docker which lets you easily attach chained blocking webhooks to arbitrary Docker API calls.

This enables **composition** of prototypical `Docker extensions <https://clusterhq.com/blog/docker-extensions/>`_.
Intended to allow quick prototyping of plugins, in order to figure out which integration points are needed in order to turn such prototypical plugins into `real Docker extensions <https://github.com/docker/docker/issues/9983>`_.

Inspired by https://github.com/docker/docker/issues/6982

*A note on nomenclature:* we are calling the things that plug into the powerstrip "plugins" because it works with the metaphor, and may help disambiguate Powerstrip **plugins** from the Docker **extensions** they are prototyping.


Target audience
---------------

The target audience of this project is folks to want to write Docker extensions, not end users.


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
               --link powerstrip-slowreq:slowreq \
               -p 2375:2375 \
               clusterhq/powerstrip

    # Note how the following command takes a second longer than normal.
    $ export DOCKER_HOST=localhost:2375
    $ docker run ubuntu echo hello

<video demo>


Writing a plugin
----------------

A plugin is just a REST API with a single endpoint.
Use your favourite framework and language to write it.


Pre-hook plugin endpoints receive POSTs like this
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pre-hooks get called when the client has sent a request to the proxy, but before that request is passed through to the Docker daemon.
This gives the plugin the opportunity to delay or modify the contents of the request.

.. code:: http

    POST /plugin HTTP/1.1
    Content-type: application/json
    Content-length: ...

    {
        Type: "pre-hook",
        Method: "POST",
        Request: "/v1.16/container/create",
        Body: { ... },
    }

And they respond with:

.. code:: http

    HTTP 200 OK
    Content-type: application/json

    {
        Request: "/v1.16/container/create",
        Body: { ... }
    }

So that, for example, they can rewrite a GET request string, or modify the JSON in a POST body.

Or they respond with an HTTP error code, in which case the call is never passed through to the Docker daemon, and instead returned straight back to the user.


Post-hook plugin endpoints receive POSTs like this
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Post-hooks get called after the response from Docker is complete but before it has been sent back to the user.
Both the initial request and the Docker response are included in the POST body.

Plugins thus get a chance to modify the response from Docker to the client.

.. code::

    POST /plugin HTTP/1.1

    {
        Type: "post-hook",
        ClientMethod: "POST",
        OriginalRequest: "/v1.16/containers/create",
        OriginalBody: { ... },
        DockerResponseContentType: "text/plain",
        DockerResponseBody: "not found",
        DockerResponseCode: 404,
    }

Or, if it's a JSON response from Docker:

.. code::

    {
        # ...
        DockerResponseContentType: "application/json",
        DockerResponseBody: { ... },
        DockerResponseCode: 200,
    }

Limitations
-----------

* Powerstrip does not support adding hooks for:

  * Content-encoding: chunked
  * Content-type: application/vnd.docker.raw-stream

  Such streams will be passed through unmodified to the Docker API.
  This means that e.g. ``docker attach`` and ``docker pull`` (or ``push``) will *work*, but it will not be possible to extend their functionality at this time.


Recommended deployment
----------------------

Powerstrip runs in a container.

For now, it does not support TLS, but given that it should only be used for prototyping in local development environments, that's OK.

It's recommended that plugins run in containers that are linked (with Docker links) to the proxy container.
Plugins should listen on port 80.

Then you can just specify the URL using e.g. http://plugin/, assuming "plugin" is the link alias.
(See example under "Try it out").


Contributing
------------

We plan to do CI with from https://drone.io/ for unit tests.
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

    def sendErrorToClient():
        pass

    preHooks = [flocker, weave]
    preHooks = [weave, flocker]
    def receive_req_from_client(method, request, body):
        d = defer.succeed(None)
        for plugin in preHooks:
            d.addCallback(postToPlugin, plugin.uri, dict(method=method, request=request, body=body))
        d.addCallback(passthruToDocker, ...)
        d.addErrback(sendErrorToClient)
        def dockerErrorHandler(reason):
            # post-hooks get to learn about errors from docker, these do not bail out the pipeline
            return DockerErrorResponse(...)
        d.addErrback(dockerErrorHandler)
        for plugin in postHooks:
            d.addCallback(postToPlugin, plugin.uri, dict(method=method, request=request, body=body))

        d.addErrback(sendErrorToClient)
        return d
