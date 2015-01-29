
source "$(dirname $BASH_SOURCE)/util/testbed.sh"

test-passthrough-prehook() {
	in-testbed() {
		start-inspect-adapter / pre-hook /tmp/output /dev/null
		start-powerstrip
		trap 'cleanup' EXIT
		export DOCKER_HOST=tcp://localhost:2375
		docker ps > /dev/null
		path="$(cat /tmp/output \
			| jq -r 'select(.Type == "pre-hook") | .ClientRequest.Request')"
		[[ "$path" = "/v1.16/containers/json" ]]
	}
	use-testbed $FUNCNAME
}

test-passthrough-posthook() {
	in-testbed() {
		start-inspect-adapter / post-hook /tmp/output /dev/null
		start-powerstrip
		trap 'cleanup' EXIT
		export DOCKER_HOST=tcp://localhost:2375
		docker ps > /dev/null
		path="$(cat /tmp/output \
			| jq -r 'select(.Type == "post-hook") | .ClientRequest.Request')"
		[[ "$path" = "/v1.16/containers/json" ]]
	}
	use-testbed $FUNCNAME
}

test-passthrough-pre-and-post() {
	in-testbed() {
		start-inspect-adapter / pre-hook /tmp/prehook /dev/null
		start-inspect-adapter / post-hook /tmp/posthook /dev/null
		start-powerstrip
		trap 'cleanup' EXIT
		export DOCKER_HOST=tcp://localhost:2375
		[[ "$(cat /tmp/prehook)" == "" && "$(cat /tmp/posthook)" == "" ]]
		docker ps > /dev/null
		[[ "$(cat /tmp/prehook)" != "" && "$(cat /tmp/posthook)" != "" ]]
	}
	use-testbed $FUNCNAME
}


