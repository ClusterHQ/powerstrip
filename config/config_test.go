package config

import (
	"fmt"
	"log"
	"net/http"
	"testing"

	"gopkg.in/yaml.v2"
)

//
var sampleValidConfig = `
version: 1
endpoints:
  "POST /*/containers/create":
    pre: [flocker, weave]
    post: [flocker, weave]
  "POST /*/containers/*/start":
    post: [weave]
adapters:
  weave: http://weave/extension
  flocker: http://flocker/flocker-adapter
`
var invalidConfig = `
version: 1
endpoints:
  "POST /*/containers/create":
adapters:
  weave:
  flocker: http://flocker/flocker-adapter
`

func TestNewConfig(t *testing.T) {
	cfg, err := NewConfig("sample.yml")

	if err != nil {
		t.Error(err)
	}

	if cfg == nil {
		t.Error("config is nil")
	}
}

func TestConfigParsing(t *testing.T) {
	cfg := Config{}
	err := yaml.Unmarshal([]byte(invalidConfig), &cfg)
	if err != nil {
		log.Fatalf("error: %v", err)
	}

	if err := cfg.Parse(); err == nil {
		log.Fatalf("expected err got: %+v", cfg)
	}
}

func TestConfigMatch(t *testing.T) {
	cfg, err := NewConfig("sample.yml")
	if err != nil {
		t.Error(err)
	}

	req, _ := http.NewRequest("GET", "http://docker_host/v1.16/containers/json", nil)
	pre, post := cfg.Match(req)
	if pre == nil || post == nil {
		t.Error("expected urls to not be nil")
	}
	fmt.Println(pre, post)

}
