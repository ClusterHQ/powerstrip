
source "$(dirname $BASH_SOURCE)/util/testbed.sh"

test-no-adapters-ps() {
	in-testbed() {
		start-powerstrip
		export DOCKER_HOST=unix:///var/run/docker.sock
		before="$(docker ps -q)"
		export DOCKER_HOST=tcp://localhost:2375
		after="$(docker ps -q)"
		[[ "$before" = "$after" ]]
	}
	use-testbed $FUNCNAME
}

test-no-adapters-images() {
	in-testbed() {
		start-powerstrip
		export DOCKER_HOST=unix:///var/run/docker.sock
		before="$(docker images -q)"
		export DOCKER_HOST=tcp://localhost:2375
		after="$(docker images -q)"
		[[ "$before" = "$after" ]]
	}
	use-testbed $FUNCNAME
}

# dns sometimes fails, also this is slow anyway
test-no-adapters-pull() {
	in-testbed() {
		start-powerstrip
		# pull once to make sure we have it
		docker pull gliderlabs/alpine > /dev/null
		export DOCKER_HOST=unix:///var/run/docker.sock
		before="$(docker pull gliderlabs/alpine)"
		export DOCKER_HOST=tcp://localhost:2375
		after="$(docker pull gliderlabs/alpine)"
		[[ "$before" = "$after" ]]
	}
	use-testbed $FUNCNAME
}

test-no-adapters-run() {
	in-testbed() {
		start-powerstrip
		export DOCKER_HOST=unix:///var/run/docker.sock
		before="$(echo "hello" | docker run $RMFLAG -i gliderlabs/alpine /bin/sh -c 'cat')"
		[[ "$before" = "hello" ]]
		export DOCKER_HOST=tcp://localhost:2375
		after="$(echo "hello" | docker run $RMFLAG -i gliderlabs/alpine /bin/sh -c 'cat')"
		[[ "$after" = "hello" ]]
	}
	use-testbed $FUNCNAME
}