package main

import (
	"encoding/json"
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// helpers

func ParseAdapterRequest(req *http.Request) (*PreHookRequest, *PostHookRequest, error) {
	defer req.Body.Close()
	data, err := ioutil.ReadAll(req.Body)
	if err != nil {
		return nil, nil, err
	}
	var untyped map[string]interface{}
	if err := json.Unmarshal(data, &untyped); err != nil {
		return nil, nil, err
	}
	if untyped["Type"] == "pre-hook" {
		var prehookReq PreHookRequest
		if err := json.Unmarshal(data, &prehookReq); err != nil {
			return nil, nil, err
		}
		return &prehookReq, nil, nil
	}
	if untyped["Type"] == "post-hook" {
		var posthookReq PostHookRequest
		if err := json.Unmarshal(data, &posthookReq); err != nil {
			return nil, nil, err
		}
		return nil, &posthookReq, nil
	}
	return nil, nil, nil
}

func WriteAdapterResponse(w http.ResponseWriter, resp interface{}) error {
	w.Header().Set("Content-Type", "application/json")
	enc := json.NewEncoder(w)
	err := enc.Encode(resp)
	if err != nil {
		http.Error(w, err.Error(), 500)
		return err
	}
	return nil
}

func NewMockAdapterServer(handler func(http.ResponseWriter, *http.Request)) *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(handler))
}

func NewMockRequest(body string) *http.Request {
	req, _ := http.NewRequest("POST",
		"http://dockertest/fake",
		ioutil.NopCloser(
			strings.NewReader(body)))
	return req
}

func BodyToBytes(body *string) []byte {
	if body == nil {
		return []byte{}
	}
	return []byte(*body)
}

func MarshalRequestBody(req *ClientRequest, obj interface{}) {
	b, _ := json.Marshal(obj)
	str := string(b)
	req.Body = &str
}

// tests

func TestNoPreHooks(t *testing.T) {
	input := "foobar"
	output := applyPrehooks(NewMockRequest(input), []string{})
	if output != input {
		t.Errorf("expected: %v got: %v", input, output)
	}
}

func TestModifyJsonPreHook(t *testing.T) {
	adapter := NewMockAdapterServer(func(w http.ResponseWriter, r *http.Request) {
		pre, _, _ := ParseAdapterRequest(r)

		var obj map[string]int
		json.Unmarshal(BodyToBytes(pre.ClientRequest.Body), &obj)

		obj["Number"] = obj["Number"] + 1
		MarshalRequestBody(&pre.ClientRequest, obj)

		WriteAdapterResponse(w, map[string]interface{}{
			"PowerstripProtocolVersion": ProtocolVersion,
			"ModifiedClientRequest":     pre.ClientRequest,
		})
	})
	defer adapter.Close()

	input := `{"Number": 1}`
	expected := `{"Number":2}`
	output := applyPrehooks(NewMockRequest(input), []string{
		adapter.URL,
	})
	if output != expected {
		t.Errorf("expected: %v got: %v", expected, output)
	}
}
