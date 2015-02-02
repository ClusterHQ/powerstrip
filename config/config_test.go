package config

import (
	"log"
	"testing"

	"gopkg.in/yaml.v2"
)

//
var sampleValidConfig = `
version: 1
endpoints:
  "POST /*/containers/create":
    pre: [flocker, weave]
  "POST /*/containers/*/start":
    post: [weave]
adapters:
  weave: http://weave/extension
  flocker: http://flocker/flocker-adapter
`
var conf = `
version: 1
endpoints:
  "POST /*/containers/create":
    pre: [flocker, weave]
adapters:
  weave:
  flocker: http://flocker/flocker-adapter
`

func TestConfig(test *testing.T) {
	t := Config{}
	err := yaml.Unmarshal([]byte(conf), &t)
	if err != nil {
		log.Fatalf("error: %v", err)
	}

	if err := t.Validate(); err != nil {
		test.Log(t)
		test.Error(err)
	}
}
