NAME=powerstrip
VERSION=0.1.0

all: build container

build:
	mkdir -p build/linux  && GOOS=linux  go build -ldflags "-X main.Version $(VERSION)" -o build/linux/$(NAME)
	mkdir -p build/darwin && GOOS=darwin go build -ldflags "-X main.Version $(VERSION)" -o build/darwin/$(NAME)

container:
	docker build -t powerstrip .

debug: all
	docker rm -f powerstrip > /dev/null || true
	docker run --rm --name powerstrip \
		-v /var/run/docker.sock:/var/run/docker.sock \
		-p 2375:2375 \
		-e "DEBUG=1" \
		powerstrip

.PHONY: build container