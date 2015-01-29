# Powerstrip: Go port for version 0.1.0

Please see [main readme](https://github.com/ClusterHQ/powerstrip) for information about Powerstrip project. This readme is focusing on development of the Go port until it's merged into master.

## Development

Assuming you have Go set up [with cross-compile for OS X and Linux](http://www.goinggo.net/2013/10/cross-compile-your-go-programs.html), and a Docker environment ready, you can:

	$ make deps         # installs go libraries
	$ make build        # builds binaries for osx, linux
	$ make container    # builds the docker container
	$ make test			# runs integration tests with testbed in docker

While developing Powerstrip in Go, you may want to test it. Since the container is small and compiling is fast, there is a debug task that rebuilds binaries and container, then runs it in a container in the foreground:

	$ make debug


## License

Copyright 2015 ClusterHQ, Inc.

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License.  You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the License for the specific language governing permissions and limitations under the License.
