// usage: inspect [path] [hook-type]
//
// listens on 80 as adapter for http connections that match
// optional arguments. first one that matches, request is
// handled where adapter input matches output (passthrough).
// req/resp headers are sent to stderr, bodies sent to stdout
package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"io"
	"io/ioutil"
	"log"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

func assert(err error) {
	if err != nil {
		log.Fatal(err)
	}
}

func marshal(obj interface{}) []byte {
	bytes, err := json.Marshal(obj)
	assert(err)
	return bytes
}

func unmarshal(input io.Reader, obj interface{}) {
	body, err := ioutil.ReadAll(input)
	assert(err)
	assert(json.Unmarshal(body, obj))
	return
}

func main() {
	listener, err := net.Listen("tcp", ":80")
	assert(err)
	for {
		conn, err := listener.Accept()
		assert(err)
		defer conn.Close()
		reqBuf := &bytes.Buffer{}
		req, err := http.ReadRequest(bufio.NewReader(io.TeeReader(conn, reqBuf)))
		assert(err)
		// match request path against arg2
		if len(os.Args) > 1 {
			filter := os.Args[1]
			match, _ := filepath.Match(filter, req.RequestURI)
			if !(strings.HasPrefix(req.RequestURI, filter) || match) {
				conn.Close()
				continue
			}
		}
		// write req headers to stderr, body to stdout while reading
		headers := strings.SplitN(reqBuf.String(), "\r\n\r\n", 2)[0]
		_, err = os.Stderr.WriteString(headers + "\r\n\r\n")
		assert(err)
		var payload map[string]interface{}
		unmarshal(io.TeeReader(req.Body, os.Stdout), &payload)
		// match type against arg1
		if len(os.Args) > 2 {
			if payload["Type"] != os.Args[2] {
				conn.Close()
				continue
			}
		}
		// convert req body to proper resp body
		if payload["Type"] == "pre-hook" {
			payload["ModifiedClientRequest"] = payload["ClientRequest"]
			delete(payload, "ClientRequest")
		} else if payload["Type"] == "post-hook" {
			payload["ModifiedServerResponse"] = payload["ServerResponse"]
			delete(payload, "ServerResponse")
			delete(payload, "ClientRequest")
		}
		delete(payload, "Type")
		// write resp headers to stderr+conn, body to stdout+conn
		body := marshal(payload)
		size := strconv.Itoa(len(body))
		header := "HTTP/1.1 200 OK\r\nContent-Length: " + size + "\r\n\r\n"
		_, err = bytes.NewBufferString(header).WriteTo(io.MultiWriter(conn, os.Stderr))
		assert(err)
		time.Sleep(100 * time.Millisecond)
		_, err = bytes.NewBuffer(body).WriteTo(io.MultiWriter(conn, os.Stdout))
		assert(err)
		return
	}
}
