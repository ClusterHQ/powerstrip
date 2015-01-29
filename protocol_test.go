package main

import (
	"encoding/json"
	"io/ioutil"
	"log"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
)

var AddingPreHookAdaptor = func(w http.ResponseWriter, r *http.Request) {
	defer r.Body.Close()
	d := json.NewDecoder(r.Body)

	request := map[string]interface{}{}
	if err := d.Decode(&request); err != nil {
		log.Fatal(err)
		return
	}

	clientRequest := request["ClientRequest"].(map[string]interface{})

	// Body is a string? It should be a map[string]interface{}

	body := map[string]interface{}{}
	err := json.Unmarshal([]byte(clientRequest["Body"].(string)), &body)
	if err != nil {
		log.Fatal(err)
	}
	// body := clientRequest["Body"].(map[string]interface{})
	number := body["Number"]

	log.Println(body)

	response := map[string]interface{}{
		"PowerstripProtocolVersion": 1,
		"ModifiedClientRequest":     request["ClientRequest"],
	}

	w.Header().Set("Content-Type", "application/json")
	encoder := json.NewEncoder(w)
	err = encoder.Encode(response)
	if err != nil {
		http.Error(w, "failed marshal", 500)
		log.Println("error:", err)
		return
	}

}

func NewMockAdderAdapter() *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(AddingPreHookAdaptor))
}

var mockBody = `{"Number": 1}`

// var mockBody = `
// 		{"Name": "Ed", "Text": "Knock knock."}
// 		{"Name": "Sam", "Text": "Who's there?"}
// 		{"Name": "Ed", "Text": "Go fmt."}
// 		{"Name": "Sam", "Text": "Go fmt who?"}
// 		{"Name": "Ed", "Text": "Go fmt yourself!"}
// 	`

// TestNoPreHookAdaptors applysPrehooks with no adaptors.
// we should get an identical response as our request.
func TestNoPreHookAdaptors(t *testing.T) {
	adaptors := make(map[string]string)

	req, _ := http.NewRequest("POST", "http://dockertest/create", ioutil.NopCloser(strings.NewReader(mockBody)))

	res := applyPrehooks(req, adaptors)

	if res != mockBody {
		t.Error("expected", mockBody, "got", res)
	}
}

// // TestApplyModifyPreHookAdaptor modify response by incrementing a number by 1
// func TestApplyModifyPreHookAdaptor(t *testing.T) {
//
// }

func TestApplyPrehooks(t *testing.T) {
	ts := NewMockAdderAdapter()
	defer ts.Close()

	req, _ := http.NewRequest("POST", "http://dockertest/create", ioutil.NopCloser(strings.NewReader(mockBody)))

	mockURL, _ := url.Parse(ts.URL)
	_ = applyPrehooks(req, map[string]string{"mock": mockURL.Host})

}
