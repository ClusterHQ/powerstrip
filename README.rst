Powerstrip: The missing Docker extensions API
=============================================

.. image:: powerstrip.jpg

Powerstrip is a configurable, pluggable HTTP proxy for the Docker API which lets you plug multiple prototypical Docker extensions ("Powerstrip plugins") into the same Docker daemon.

So for example you can have a storage plugin coexist with a networking plugin, playing nice with your choice of orchestration framework.

This enables **composition** of prototypes of `Docker extensions <https://clusterhq.com/blog/docker-extensions/>`_.

This is intended to allow quick prototyping, in order to figure out which integration points are needed in order to turn such prototypical plugins into `real Docker extensions <https://github.com/docker/docker/issues/9983>`_.

How it works
------------

Powerstrip does this by implementing chained blocking webhooks to arbitrary Docker API calls.

This is inspired by https://github.com/docker/docker/issues/6982.

*A note on nomenclature:* we are calling the things that plug into the powerstrip "plugins" because it works with the metaphor, and may help disambiguate Powerstrip **plugins** from the Docker **extensions** they are prototyping.


Target audience
---------------

The target audience of this project is folks to want to write Docker extensions, not end users.


Goal of project
---------------

It should eventually be possible to run a Powerstrip-enabled Docker Swarm with Flocker and Weave both loaded as extensions.

.. code:: yaml

    endpoints:
      "POST /*/containers/create":
        # plugins are applied in list order
        pre: [flocker, weave]
        post: [weave, flocker]
      "DELETE /*/containers/*":
        pre: [flocker, weave]
        post: [weave, flocker]
    plugins:
      flocker: http://flocker/flocker-plugin
      weave: http://flocker/weave-plugin

This example might allow an orchestration framework to move (reschedule) stateful containers while their Weave IP and Flocker volumes move around with them.

But Powerstrip can be used to modify any Docker behavior at all.


Try it out
----------

Powerstrip ships as a Docker image, and plugins can be any HTTP endpoint, including other linked Docker containers.

`Slowreq <https://github.com/clusterhq/powerstrip-slowreq>`_ is a trivial Powerstrip plugin (container) which adds a 1 second delay to all create commands.

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


Writing a plugin
----------------

A plugin is just a REST API with a single endpoint.
Use your favourite framework and language to write it.


Pre-hook plugin endpoints receive POSTs like this
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pre-hooks get called when the client has sent a request to the proxy, but before that request is passed through to the Docker daemon.
This gives the plugin the opportunity to modify or delay the request.

.. code:: http

    POST /plugin HTTP/1.1
    Content-type: application/json
    Content-length: ...

    {
        Type: "pre-hook",
        Method: "POST",
        Request: "/v1.16/container/create",
        Body: { ... } or null
    }

And they respond with:

.. code:: http

    HTTP 200 OK
    Content-type: application/json

    {
        Method: "POST",
        Request: "/v1.16/container/create",
        Body: { ... } or null
    }

So that, for example, they can rewrite a GET request string, or modify the JSON in a POST body.

Alternatively, pre-hooks can respond with an HTTP error code, in which case the call is never passed through to the Docker daemon, and instead the error is returned straight back to the client.

Pre-hooks must not change the scope of which endpoint is being matched - rewriting the Request should only be used for modifying GET arguments (e.g. after a '?' in the URL).


Post-hook plugin endpoints receive POSTs like this
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Post-hooks get called after the response from Docker is complete but before it has been sent back to the client.
Both the initial request and the Docker response are included in the POST body.

Plugins thus get a chance to modify or delay the response from Docker to the client.

.. code::

    POST /plugin HTTP/1.1

    {
        Type: "post-hook",
        OriginalClientMethod: "POST",
        OriginalClientRequest: "/v1.16/containers/create",
        OriginalClientBody: { ... },
        DockerResponseContentType: "text/plain",
        DockerResponseBody: { ... } (if application/json)
                            or "not found" (if text/plain)
                            or null (if it was a GET request),
        DockerResponseCode: 404
    }

The plugin responds with:

.. code::

    {
        ContentType: "application/json",
        Body: { ... },
        Code: 200
    }

This gives the post-hook a chance to convert a Docker error into a success if it thinks it can.


Chaining
~~~~~~~~

Both pre- and post-hooks can be chained: the response from the N'th hook is passed in as the request to the N+1'th in list order according to the YAML configuration.

If any hook returns an HTTP error response, the rest of the chain is cancelled, and the error returned to the client.
You can think of this like `Twisted Deferred chains <http://twistedmatrix.com/documents/13.0.0/core/howto/defer.html#auto3>`_ where hooks are like callbacks. The exception to this is when the Docker API returns an error: the post-hooks are still run in that case, because we thought plugin authors would like to know about Docker error messages.


Defining Endpoints
------------------

Endpoints are defined using UNIX shell-like globbing.
The request ``POST /v1.16/container/create`` would be matched by all of the following endpoint definitions:

* ``POST /v1.16/containers/create``
* ``POST /v1*/containers/create``
* ``POST /*/containers/create``
* ``POST /*/*/create``
* ``* /*/containers/create``
* ``POST /v[12]/containers/create``

Note: Query arguments are stripped for matching purposes.

Limitations
-----------

Powerstrip does not support adding hooks for:

* Content-encoding: chunked
* Content-type: application/vnd.docker.raw-stream

Such streams will be passed through unmodified to the Docker API.
This means that e.g. ``docker attach`` and ``docker pull`` (or ``push``) will *work*, but it will not be possible to extend their functionality at this time.


Recommended deployment
----------------------

For now, Powerstrip does not support TLS, but given that it should only be used for prototyping in local development environments, that's OK.

It's recommended that plugins run in containers that are linked (with Docker links) to the proxy container.
Plugins should listen on port 80.

Then you can just specify the URL using e.g. http://plugin/, assuming "plugin" is the link alias.
(See example under "Try it out").


Contributing
------------

We plan to do CI with from https://drone.io/ for unit tests.
Integration tests will exist but only get run manually for now.


Possible fates for a request
----------------------------

There are a few different paths that an HTTP request can take.

Here are some of them:

* Client req => Plugin pre-hook returns OK => Docker => Plugin post-hook => Client response
* Client req => Plugin pre-hook returns error code => error response to client (don't pass through request to Docker)
* Client req => Plugin pre-hook => Docker => Error response from Docker to plugin post-hook => Pass through error response to client
* Client req => Plugin pre-hook => Docker => Plugin post-hook => error response to client


Pseudocode
----------

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
            # TODO probably actually implement this as a PreHookResponse object.
            d.addCallback(postToPlugin, plugin.uri, dict(
                Type="pre-hook",
                Method=method,
                Request=request,
                Body=body))
        d.addCallback(passthruToDocker, ...)
        d.addErrback(sendErrorToClient)
        def dockerErrorHandler(reason):
            # post-hooks get to learn about errors from docker, these do not bail out the pipeline
            return DockerErrorResponse(...)
        d.addErrback(dockerErrorHandler)
        for plugin in postHooks:
            # TODO probably actually implement this as a PostHookResponse object.
            d.addCallback(postToPlugin, plugin.uri, dict(
                Type="post-hook",
                OriginalClientMethod=method,
                OriginalClientRequest=request,
                OriginalClientBody=body,
                DockerResponseContentType=...,
                DockerResponseBody=...,
                DockerResponseCode=...))
        d.addErrback(sendErrorToClient)
        return d


Possible improvements
=====================

* A Continue response argument could be added to allow chain cancellation with a non-error response.

License
=======

Copyright 2015 ClusterHQ, Inc.

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License.  You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the License for the specific language governing permissions and limitations under the License.
