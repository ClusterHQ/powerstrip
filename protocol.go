package main

import (
	"bytes"
	"encoding/json"
	"io/ioutil"
	"net/http"
	"strconv"
)

const (
	ProtocolVersion = 1
)

type ClientRequest struct {
	Method  string
	Request string
	Body    *string
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

func applyPrehooks(req *http.Request, adaptors map[string]string) string {
	body, err := ioutil.ReadAll(req.Body)
	assert(err)
	assert(req.Body.Close())
	bodyStr := string(body)
	prehookRequest := &PreHookRequest{
		Type: "pre-hook",
		PowerstripProtocolVersion: ProtocolVersion,
		ClientRequest: ClientRequest{
			Method:  req.Method,
			Request: req.RequestURI,
			Body:    &bodyStr,
		},
	}
	var prehookResponse PreHookResponse
	for name, addr := range adaptors {
		var buf bytes.Buffer
		enc := json.NewEncoder(&buf)
		err := enc.Encode(prehookRequest)
		if err != nil {
			debug("prehook skipped:", name, err)
			continue
		}
		url := "http://" + addr + req.RequestURI
		hookResp, err := http.Post(url, req.Header.Get("Content-Type"), &buf)
		if err != nil {
			debug("prehook skipped:", name, err)
			continue
		}
		dec := json.NewDecoder(hookResp.Body)
		err = dec.Decode(&prehookResponse)
		if err != nil {
			debug("prehook skipped:", name, err)
			continue
		}
		err = hookResp.Body.Close()
		if err != nil {
			debug("prehook skipped:", name, err)
			continue
		}
		prehookRequest.ClientRequest.Body = prehookResponse.ModifiedClientRequest.Body
		prehookRequest.ClientRequest.Request = prehookResponse.ModifiedClientRequest.Request
	}
	if prehookRequest.ClientRequest.Body == nil {
		bodyStr = ""
	} else {
		bodyStr = *prehookRequest.ClientRequest.Body
	}
	length := strconv.Itoa(len(bodyStr))
	req.Header.Set("Content-Length", length)
	req.Body = ioutil.NopCloser(bytes.NewBufferString(bodyStr))
	return bodyStr
}

func applyPosthooks(resp *http.Response, req *http.Request, adaptors map[string]string, reqBody string) {
	respBody, err := ioutil.ReadAll(resp.Body)
	assert(err)
	assert(resp.Body.Close())
	bodyStr := string(respBody)
	posthookRequest := &PostHookRequest{
		Type: "post-hook",
		PowerstripProtocolVersion: ProtocolVersion,
		ClientRequest: ClientRequest{
			Method:  req.Method,
			Request: req.RequestURI,
			Body:    &reqBody,
		},
		ServerResponse: ServerResponse{
			ContentType: resp.Header.Get("Content-Type"),
			Code:        resp.StatusCode,
			Body:        &bodyStr,
		},
	}
	var posthookResponse PostHookResponse
	for name, addr := range adaptors {
		var buf bytes.Buffer
		enc := json.NewEncoder(&buf)
		err := enc.Encode(posthookRequest)
		if err != nil {
			debug("posthook skipped:", name, err)
			continue
		}
		url := "http://" + addr + req.RequestURI
		hookResp, err := http.Post(url, req.Header.Get("Content-Type"), &buf)
		if err != nil {
			debug("posthook skipped:", name, err)
			continue
		}
		dec := json.NewDecoder(hookResp.Body)
		err = dec.Decode(&posthookResponse)
		if err != nil {
			debug("posthook skipped:", name, err)
			continue
		}
		err = hookResp.Body.Close()
		if err != nil {
			debug("posthook skipped:", name, err)
			continue
		}
		posthookRequest.ServerResponse = posthookResponse.ModifiedServerResponse
	}
	resp.Header.Set("Content-Type", posthookRequest.ServerResponse.ContentType)
	resp.StatusCode = posthookRequest.ServerResponse.Code
	resp.Status = http.StatusText(resp.StatusCode)
	if posthookRequest.ServerResponse.Body == nil {
		bodyStr = ""
	} else {
		bodyStr = *posthookRequest.ServerResponse.Body
	}
	length := strconv.Itoa(len(bodyStr))
	resp.Header.Set("Content-Length", length)
	resp.Body = ioutil.NopCloser(bytes.NewBufferString(bodyStr))
}
