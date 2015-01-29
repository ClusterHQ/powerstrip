package main

import (
	"bufio"
	"bytes"
	"io"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"strings"

	"code.google.com/p/go-uuid/uuid"
	dockerapi "github.com/fsouza/go-dockerclient"
)

var Version string
var DebugMode bool

// abused throughout during development
func assert(err error) {
	if err != nil {
		if DebugMode {
			panic(err)
		}
		log.Fatal(err)
	}
}

func debug(v ...interface{}) {
	if DebugMode {
		log.Println(v...)
	}
}

func getopt(name, def string) string {
	if env := os.Getenv(name); env != "" {
		return env
	}
	return def
}

func chunked(encodings []string) bool {
	if encodings == nil {
		return false
	}
	for _, value := range encodings {
		if value == "chunked" {
			return true
		}
	}
	return false
}

func main() {
	DebugMode = (getopt("DEBUG", "1") != "") // always debug mode for now
	port := getopt("PORT", "2375")
	dockerHost := getopt("DOCKER_HOST", "unix:///var/run/docker.sock")
	dockerUri, err := url.Parse(dockerHost)
	assert(err)

	docker, err := dockerapi.NewClient(dockerHost)
	assert(err)

	listener, err := net.Listen("tcp", ":"+port)
	assert(err)

	log.Println("powerstrip", Version, "listening on", port, "using", dockerHost, "...")
	if DebugMode {
		log.Println("debug mode enabled")
	}

	adapters := make(map[string]string)

	// Look for adapter containers
	containers, err := docker.ListContainers(dockerapi.ListContainersOptions{})
	if err != nil {
		log.Println("unable to connect to docker")
		assert(err)
	}
	for _, listing := range containers {
		container, err := docker.InspectContainer(listing.ID)
		assert(err)
		name := container.Name[1:]
		for _, env := range container.Config.Env {
			kvp := strings.SplitN(env, "=", 2)
			if kvp[0] == "POWERSTRIP_ADAPTER" {
				for ep, _ := range container.Config.ExposedPorts {
					port := strings.SplitN(string(ep), "/", 2)
					adapters[kvp[1]+":"+name] = net.JoinHostPort(container.NetworkSettings.IPAddress, port[0])
					break
				}
				break
			}
		}
	}

	log.Println(adapters)

	for {
		conn, err := listener.Accept()
		assert(err)
		go func() {
			defer conn.Close()
			reqId := strings.SplitN(uuid.New(), "-", 2)[0]

			debug(reqId, "reading request")
			req, err := http.ReadRequest(bufio.NewReader(conn))
			assert(err)

			debug(reqId, "applying prehooks", adapters)
			body := applyPrehooks(req, adapters)

			debug(reqId, "connecting and writing request")
			server, err := net.Dial(dockerUri.Scheme, dockerUri.Path)
			assert(err)
			defer server.Close()
			req.Write(server)

			debug(reqId, "reading response")
			headers := &bytes.Buffer{}
			respTee := bufio.NewReader(io.TeeReader(server, headers))
			resp, err := http.ReadResponse(respTee, req)
			assert(err)
			resp.Close = true // we only service one request per conn

			if resp.Header.Get("Content-Type") == "application/vnd.docker.raw-stream" {
				debug(reqId, "proxying raw stream")
				_, err := headers.WriteTo(conn)
				assert(err)
				done := make(chan struct{})
				go func() {
					io.Copy(conn, server)
					conn.(*net.TCPConn).CloseWrite()
					close(done)
				}()
				io.Copy(server, conn)
				server.(*net.UnixConn).CloseWrite()
				<-done
			} else if chunked(resp.TransferEncoding) {
				debug(reqId, "proxying chunked stream")
				assert(resp.Write(conn))
				conn.(*net.TCPConn).CloseWrite()
			} else {
				debug(reqId, "applying posthooks", adapters)
				applyPosthooks(resp, req, adapters, body)
				debug(reqId, "flushing response")
				assert(resp.Write(conn))
			}
		}()

	}
}
