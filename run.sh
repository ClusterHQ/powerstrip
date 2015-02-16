#!/bin/bash

# usage is `sudo ./run.sh <n>` for run `<n>`. it needs docker bound to
# localhost:2375 without TLS (add `-H localhost:2375` to `DOCKER_OPTS` in
# `/etc/default/docker` on ubuntu)

echo starting good...

tcpdump -i lo -w outputs/good-${1}.pcap
pid=$!
sleep 1

DOCKER_HOST=localhost:2375 docker run ubuntu echo hello

sleep 1
kill $pid

echo done

echo starting bad...

tcpdump -i lo -w outputs/bad-${1}.pcap
pid=$!
sleep 1

DOCKER_HOST=localhost:2375 docker run ubuntu echo hello

sleep 1
kill $pid

echo done

