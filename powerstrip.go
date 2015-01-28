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

	dockerapi "github.com/fsouza/go-dockerclient"
)

// abused throughout during development
func assert(err error) {
	if err != nil {
		//log.Fatal(err)
		panic(err)
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
	port := getopt("PORT", "2375")
	dockerHost := getopt("DOCKER_HOST", "unix:///var/run/docker.sock")
	dockerUri, err := url.Parse(dockerHost)
	assert(err)

	docker, err := dockerapi.NewClient(dockerHost)
	assert(err)

	listener, err := net.Listen("tcp", ":"+port)
	assert(err)

	log.Println("listening on", port, "using", dockerHost, "...")

	adaptors := make(map[string]string)

	// Look for plugin containers
	containers, err := docker.ListContainers(dockerapi.ListContainersOptions{})
	assert(err)
	for _, listing := range containers {
		container, err := docker.InspectContainer(listing.ID)
		assert(err)
		for _, env := range container.Config.Env {
			kvp := strings.SplitN(env, "=", 2)
			if kvp[0] == "POWERSTRIP_ADAPTOR" {
				for ep, _ := range container.Config.ExposedPorts {
					port := strings.SplitN(string(ep), "/", 2)
					adaptors[kvp[1]] = net.JoinHostPort(container.NetworkSettings.IPAddress, port[0])
					break
				}
				break
			}
		}
	}

	log.Println(adaptors)

	for {
		conn, err := listener.Accept()
		assert(err)
		go func() {
			defer conn.Close()

			log.Println("reading request")
			reqBuf := &bytes.Buffer{}
			reqTee := bufio.NewReader(io.TeeReader(conn, reqBuf))
			req, err := http.ReadRequest(reqTee)
			assert(err)

			log.Println("applying prehooks", adaptors)
			body := applyPrehooks(req, adaptors)
			reqBuf.Reset()
			assert(req.Write(reqBuf))

			server, err := net.Dial(dockerUri.Scheme, dockerUri.Path)
			assert(err)
			defer server.Close()
			io.Copy(server, reqBuf)

			log.Println("reading response")
			headerBuf := &bytes.Buffer{}
			respTee := bufio.NewReader(io.TeeReader(server, headerBuf))
			resp, err := http.ReadResponse(respTee, req)
			assert(err)
			resp.Close = true

			if resp.Header.Get("Content-Type") == "application/vnd.docker.raw-stream" {
				log.Println("proxying raw stream")
				_, err := headerBuf.WriteTo(conn)
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
				log.Println("proxying chunked stream")
				assert(resp.Write(conn))
				conn.(*net.TCPConn).CloseWrite()
			} else {
				log.Println("applying posthooks", adaptors)
				applyPosthooks(resp, req, adaptors, body)
				log.Println("flushing response")
				assert(resp.Write(conn))
			}
		}()

	}
}
