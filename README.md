# Powerstrip: Go port for version 0.1.0

Please see [main readme](https://github.com/ClusterHQ/powerstrip) for information about Powerstrip project. This readme is focusing on development of the Go port until it's merged into master.

## Development

Assuming you have Go set up [with cross-compile for OS X and Linux](http://www.goinggo.net/2013/10/cross-compile-your-go-programs.html), and a Docker environment ready, you can:

	$ make deps         # installs go libraries
	$ make build        # builds binaries for osx, linux
	$ make container    # builds the docker container
	$ make test			# runs integration tests with testbed in docker

While developing Powerstrip in Go, you may want to test it manually. Since the container is small and compiling is fast, there is a debug task that rebuilds binaries and container, then runs it in a container in the foreground in one command:

	$ make debug

## Adapters

Currently, the configuration file from the Twisted version is not implemented. Instead, for now, it auto-discovers adapters running on the same host in Docker at start, and hits them all for all requests, skipping on connection or EOF errors. It does not yet even handle 404 or 405 responses, so adapters should just hang up if they don't implement an endpoint. 

Presently, auto-discovery is done by looking up containers with `POWERSTRIP_ADAPTER` environment variable set. This means you can leave adapters running and just restart Powerstrip (likely with `make debug`) while developing on Powerstrip.

## Testing

Then there are integration / end-to-end tests that actually test with the Docker binary and running Powerstrip and adapters in containers. These live under tests and are written in Bash using shunit2. 

A little bit of tooling has been added so that the tests each run inside the testbed, which is a Docker container with everything needed for end-to-end testing. This suggests tests are run in isolation, and they do sort of, but for now the tests run against the same shared Docker of the host, so they do have to clean up after themselves.

Go unit tests are on the way and the app will continue to be refactored to be more testable in the process.

## License

Copyright 2015 ClusterHQ, Inc.

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License.  You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the License for the specific language governing permissions and limitations under the License.
