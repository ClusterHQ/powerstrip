Powerstrip: A tool for prototyping Docker extensions
====================================================

At ClusterHQ we are participating in the ongoing effort in the Docker community to add an extensions API to Docker.
You can join the effort at ``#docker-extensions`` on Freenode.

.. image:: powerstrip.jpg

Powerstrip is a configurable, pluggable HTTP proxy for the Docker API which lets you plug multiple prototypical Docker extensions ("Powerstrip adapters") into the same Docker daemon.

So for example you can have a storage adapter coexist with a networking adapter, playing nice with your choice of orchestration framework.

This enables **composition** of prototypes of `Docker extensions <https://clusterhq.com/blog/docker-extensions/>`_.

This is intended to allow quick prototyping, in order to figure out which integration points are needed in order to turn such prototypical adapters into `real Docker extensions <https://github.com/docker/docker/issues/9983>`_.

How it works
------------

Powerstrip does this by implementing chained blocking webhooks to arbitrary Docker API calls.

This is inspired by https://github.com/docker/docker/issues/6982.

*A note on nomenclature:* we are calling the things that plug into the powerstrip "adapters" because it works with the metaphor, and may help disambiguate Powerstrip **adapters** from the Docker **extensions** they are prototyping.


Target audience
---------------

The target audience of this project is folks to want to write Docker extensions, not end users.


Goal of project
---------------

It should eventually be possible to run, for example, a Powerstrip-enabled Docker Swarm with Flocker and Weave both loaded as extensions.

.. code:: yaml

    endpoints:
      "POST /*/containers/create":
        # adapters are applied in list order
        pre: [flocker, weave]
        post: [weave, flocker]
      "DELETE /*/containers/*":
        pre: [flocker, weave]
        post: [weave, flocker]
    adapters:
      flocker: http://flocker/flocker-adapter
      weave: http://flocker/weave-adapter

This example might allow an orchestration framework to move (reschedule) stateful containers while their Weave IP and Flocker volumes move around with them.

But Powerstrip can be used to modify any Docker behavior at all.


Demo
----
Portable volumes with powerstrip + flocker:

<video demo>


Try it out
----------

Powerstrip ships as a Docker image, and adapters can be any HTTP endpoint, including other linked Docker containers.

`Slowreq <https://github.com/clusterhq/powerstrip-slowreq>`_ is a trivial Powerstrip adapter (container) which adds a 1 second delay to all create commands.

Try it out like this:

.. code:: sh

    $ mkdir ~/powerstrip-demo
    $ cat > ~/powerstrip-demo/adapters.yml <<EOF
    endpoints:
      "/*/containers/create":
        pre: [slowreq]
    adapters:
      slowreq: http://slowreq/v1/extension
    EOF

    $ docker run -d --name powerstrip-slowreq \
               --expose 80 \
               clusterhq/powerstrip-slowreq
    $ docker run -d --name powerstrip \
               -v /var/run/docker.sock:/var/run/docker.sock \
               -v ~/powerstrip-demo/adapters.yml:/etc/powerstrip/adapters.yml \
               --link powerstrip-slowreq:slowreq \
               -p 2375:2375 \
               clusterhq/powerstrip

    # Note how the following command takes a second longer than normal.
    $ export DOCKER_HOST=localhost:2375
    $ docker run ubuntu echo hello


Writing a adapter
----------------

A adapter is just a REST API with a single endpoint.
Use your favourite framework and language to write it.


Pre-hook adapter endpoints receive POSTs like this
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pre-hooks get called when the client has sent a request to the proxy, but before that request is passed through to the Docker daemon.
This gives the adapter the opportunity to modify or delay the request.

.. code:: http

    POST /adapter HTTP/1.1
    Content-type: application/json
    Content-length: ...

    {
        PowerstripProtocolVersion: 1,
        Type: "pre-hook",
        ClientRequest: {
            Method: "POST",
            Request: "/v1.16/container/create",
            Body: "{ ... }" or null
        }
    }

And they respond with:

.. code:: http

    HTTP 200 OK
    Content-type: application/json

    {
        PowerstripProtocolVersion: 1,
        ModifiedClientRequest: {
            Method: "POST",
            Request: "/v1.16/container/create",
            Body: "{ ... }" or null
        }
    }

So that, for example, they can rewrite a GET request string, or modify the JSON in a POST body.

Alternatively, pre-hooks can respond with an HTTP error code, in which case the call is never passed through to the Docker daemon, and instead the error is returned straight back to the client.

Pre-hooks must not change the scope of which endpoint is being matched - rewriting the Request should only be used for modifying GET arguments (e.g. after a '?' in the URL).


Post-hook adapter endpoints receive POSTs like this
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Post-hooks get called after the response from Docker is complete but before it has been sent back to the client.
Both the initial request and the Docker response are included in the POST body.

Plugins thus get a chance to modify or delay the response from Docker to the client.

.. code::

    POST /adapter HTTP/1.1

    {
        PowerstripProtocolVersion: 1,
        Type: "post-hook",
        ClientRequest: {
            Method: "POST",
            Request: "/v1.16/containers/create",
            Body: "{ ... }"
        }
        ServerResponse: {
            ContentType: "text/plain",
            Body: "{ ... }" (if application/json)
                            or "not found" (if text/plain)
                            or null (if it was a GET request),
            ResponseCode: 404
        }
    }

The adapter responds with:

.. code::

    {
        PowerstripProtocolVersion: 1,
        ModifiedServerResponse: {
            ContentType: "application/json",
            Body: "{ ... }",
            Code: 200
        }
    }

This gives the post-hook a chance to convert a Docker error into a success if it thinks it can.


Chaining
~~~~~~~~

Both pre- and post-hooks can be chained: the response from the N'th hook is passed in as the request to the N+1'th in list order according to the YAML configuration.

If any hook returns an HTTP error response, the rest of the chain is cancelled, and the error returned to the client.
You can think of this like `Twisted Deferred chains <http://twistedmatrix.com/documents/13.0.0/core/howto/defer.html#auto3>`_ where hooks are like callbacks. The exception to this is when the Docker API returns an error: the post-hooks are still run in that case, because we thought adapter authors would like to know about Docker error messages.


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

Powerstrip does not support adding post-hooks for:

* Content-encoding: chunked
* Content-type: application/vnd.docker.raw-stream

Such response streams will be passed through unmodified from the Docker API.
This means that e.g. ``docker attach`` and ``docker pull`` (or ``push``) will *work*, but it is not possible to modify these responses.

Pre-hooks operate on the *request* content (which is always assumed to be a single JSON part) rather than the *responses*, so these will work with these kinds of responses.


Recommended deployment
----------------------

For now, Powerstrip does not support TLS, but given that it should only be used for prototyping in local development environments, that's OK.

It's recommended that adapters run in containers that are linked (with Docker links) to the proxy container.
Plugins should listen on port 80.

Then you can just specify the URL using e.g. http://adapter/, assuming "adapter" is the link alias.
(See example under "Try it out").


Contributing
------------

We plan to do CI with from https://drone.io/ for unit tests.
Or maybe Travis-CI.
Integration tests will exist but only get run manually for now.


Possible fates for a request
----------------------------

There are a few different paths that an HTTP request can take.

Here are some of them:

* Client req => Plugin pre-hook returns OK => Docker => Plugin post-hook => Client response
* Client req => Plugin pre-hook returns error code => error response to client (don't pass through request to Docker)
* Client req => Plugin pre-hook => Docker => Error response from Docker to adapter post-hook => Pass through error response to client
* Client req => Plugin pre-hook => Docker => Plugin post-hook => error response to client

Possible improvements
=====================

* A Continue response argument could be added to allow chain cancellation with a non-error response.
* Verbose logging (to stdout) as an optional argument/yaml configuration flag, to help adapter authors debugging adapters.

  * Define the logging/traceability story (plugins and powerstrip log to stdout?).

* A public list of all known Powerstrip hooks (GitHub links + Docker Hub names).
* Version the webhooks and the configuration.
* Publish standard testing framework for adapters.
* Expose headers as well as (instead of) just content-type.
  For both pre and post-hooks.
* Run all the hooks in case of an error condition, do give them a chance to unwind things.
* Have an explicit "unwinder" hook-type for pre-hooks, to differentiate error-handling post-hooks from regular post-hooks.

License
=======

Copyright 2015 ClusterHQ, Inc.

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License.  You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the License for the specific language governing permissions and limitations under the License.
