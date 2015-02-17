
source "$(dirname $BASH_SOURCE)/util/testbed.sh"

test-passthrough-prehook() {
	in-testbed() {
		start-inspect-adapter / pre-hook /tmp/output /dev/null
		ip="$(docker inspect ${_inspects[0]} | jq -r ".[0].NetworkSettings.IPAddress")"
		echo "${_inspects[@]}"
		echo "$ip"

		cat > /etc/powerstrip/adapters.yml <<EOF
version: 1
endpoints:
  "POST /*/containers/*":
    pre: [inspect]
adapters:
  inspect: http://$ip
EOF

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
		ip="$(docker inspect ${_inspects[0]} | jq -r ".[0].NetworkSettings.IPAddress")"

		echo "${_inspects[@]}"
		echo "$ip"

		cat > /etc/powerstrip/adapters.yml <<EOF
version: 1
endpoints:
  "POST /*/containers/*":
    post: [inspect]
adapters:
  inspect: http://$ip
EOF

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
		ip="$(docker inspect ${_inspects[0]} | jq -r ".[0].NetworkSettings.IPAddress")"
		echo "${_inspects[@]}"
		echo "$ip"

		cat > /etc/powerstrip/adapters.yml <<EOF
version: 1
endpoints:
  "POST /*/containers/*":
    pre: [inspect]
    post: [inspect]
adapters:
  inspect: http://$ip
EOF

		start-powerstrip
		trap 'cleanup' EXIT
		export DOCKER_HOST=tcp://localhost:2375
		[[ "$(cat /tmp/prehook)" == "" && "$(cat /tmp/posthook)" == "" ]]
		docker ps > /dev/null
		[[ "$(cat /tmp/prehook)" != "" && "$(cat /tmp/posthook)" != "" ]]
	}
	use-testbed $FUNCNAME
}
