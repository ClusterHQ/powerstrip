
# helpers around testbed image for powerstrip.
# avoid names starting with "test" so shunit2 doesnt use them.

# use this if you want to write testbed
# tests in functions instead of strings.
fn-source() {
	declare -f $1 | tail -n +2
}

check-testbed() {
	docker images | grep "powerstrip-testbed" > /dev/null
}

check-inspect() {
	docker images | grep "powerstrip-inspect" > /dev/null
}

use-testbed() {
	declare name="$1" script="${2:-$(fn-source in-testbed)}"
	[[ -x "$PWD/build/linux/powerstrip" ]] || {
		echo "!! Tests need to be run from project root,"
		echo "!! and Linux build needs to exist."
		exit 127
	}
	check-testbed || make testbed
	check-inspect || make inspect
	docker run $([[ "$CI" ]] || echo "--rm") \
		-v "$PWD/build/linux/powerstrip:/bin/powerstrip" \
		-v "$PWD/tests/util/testbed/environment:/environment" \
		-v "/var/run/docker.sock:/var/run/docker.sock" \
		powerstrip-testbed \
		/bin/bash -c "set -e; source /environment; $script" \
			|| fail "$name exited non-zero"
}

# if testbed.sh is called directly
[[ "$0" == "$BASH_SOURCE" ]] && {
	docker run --rm -it \
		-v "$PWD/build/linux/powerstrip:/bin/powerstrip" \
		-v "/var/run/docker.sock:/var/run/docker.sock" \
		-v "$PWD/tests/util/testbed/environment:/environment" \
		powerstrip-testbed \
		/bin/bash
}