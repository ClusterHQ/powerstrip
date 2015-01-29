set -e
if [[ ! -d go ]]; then
	wget https://storage.googleapis.com/golang/go1.4.1.src.tar.gz
	tar -zxvf go1.4.1.src.tar.gz
	cd go/src
	unset GOROOT # CircleCI shouldn't be setting this
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 ./make.bash --no-clean
	CGO_ENABLED=0 GOOS=darwin GOARCH=amd64 ./make.bash --no-clean
fi