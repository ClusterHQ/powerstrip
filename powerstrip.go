package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"strings"

	dockerapi "github.com/fsouza/go-dockerclient"
	"github.com/inconshreveable/go-vhost"
)

type ClientRequest struct {
	Method  string
	Request string
	Body    string
}

type ServerResponse struct {
	ContentType string
	Body        *string
	Code        int
}

type PreHookRequest struct {
	PowerstripProtocolVersion int
	Type                      string
	ClientRequest             ClientRequest
}

type PreHookResponse struct {
	PowerstripProtocolVersion int
	ModifiedClientRequest     ClientRequest
}

type PostHookRequest struct {
	PowerstripProtocolVersion int
	Type                      string
	ClientRequest             ClientRequest
	ServerResponse            ServerResponse
}

type PostHookResponse struct {
	PowerstripProtocolVersion int
	ModifiedServerResponse    ServerResponse
}

func getopt(name, def string) string {
	if env := os.Getenv(name); env != "" {
		return env
	}
	return def
}

func assert(err error) {
	if err != nil {
		log.Fatal(err)
	}
}

func proxyConn(conn *vhost.HTTPConn, backend net.Conn) {
	defer conn.Close()
	defer backend.Close()

	done := make(chan struct{})
	go func() {
		io.Copy(backend, conn)
		backend.(*net.UnixConn).CloseWrite()
		close(done)
	}()
	io.Copy(conn, backend)
	conn.Conn.(*net.TCPConn).CloseWrite()
	<-done
}

func triggerPrehooks(adaptors map[string]string, req *http.Request) {
	body, err := ioutil.ReadAll(req.Body)
	req.Body.Close()
	assert(err)
	prehookRequest := &PostHookRequest{
		Type: "pre-hook",
		PowerstripProtocolVersion: 1,
		ClientRequest: ClientRequest{
			Method:  req.Method,
			Request: req.RequestURI,
			Body:    string(body),
		},
	}
	var prehookResponse PreHookResponse
	for _, addr := range adaptors {
		var buf bytes.Buffer
		enc := json.NewEncoder(&buf)
		enc.Encode(prehookRequest)
		resp, err := http.Post("http://"+addr+req.RequestURI, req.Header.Get("Content-Type"), &buf)
		assert(err)
		dec := json.NewDecoder(resp.Body)

		assert(dec.Decode(&prehookResponse))
		resp.Body.Close()
		prehookRequest.ClientRequest.Body = prehookResponse.ModifiedClientRequest.Body
		prehookRequest.ClientRequest.Request = prehookResponse.ModifiedClientRequest.Request
	}

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

	fmt.Println(adaptors)

	for {
		conn, err := listener.Accept()
		if err != nil {
			log.Fatal(err)
		}

		reqConn, _ := vhost.HTTP(conn)
		fmt.Println(reqConn.Request)

		//triggerPrehooks(adaptors, reqConn.Request)

		// write to resulting request buffer
		// create buffered io.ReadWriteCloser than has input buffer,
		// wraps original conn, and buffers response for posthooks
		// buffered RWC needs explicit flush.

		log.Println("proxy:", conn.RemoteAddr())

		backend, err := net.Dial(dockerUri.Scheme, dockerUri.Path)
		if err != nil {
			log.Println("error:", err.Error())
		}

		go proxyConn(reqConn, backend)

	}
}
