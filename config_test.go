package main

import (
	"log"
	"net/http"
	"strings"
	"testing"
)

// newValidConfig will return a new config that will be valid. Panic if invalid.
func newValidConfig() *Config {
	cfg := &Config{
		Version: 1,
		Endpoints: map[string]Endpoint{
			"POST /*/containers/*": Endpoint{
				Pre:  []string{"slowreq", "slowreq-trailing"},
				Post: []string{"slowreq"},
			},
		},
		Adapters: map[string]string{
			"slowreq":          "http://slowreq/slowreq-adapter",
			"slowreq-trailing": "http://slowreq/slowreq-adapter/",
		},
	}

	errs := cfg.Parse()
	if errs != nil {
		log.Fatal(errs)
	}

	return cfg
}

func hasError(err error, substr string) bool {
	return strings.Contains(err.Error(), substr)
}

func TestNewConfigFile(t *testing.T) {
	cfg, err := ReadConfig("sample.yml")
	if err != nil {
		t.Error(err)
	}
	if cfg == nil {
		t.Error("config is nil")
	}

	_, err = ReadConfig("nonexistant")
	if err == nil {
		t.Error("expected error for non existant file")
	}
}

func TestInvalidConfig(t *testing.T) {
	_, err := unmarshalConfig([]byte(`version: 1
		adapters:
		  flocker: http://flocker/flocker-adapter
`))
	if err == nil {
		t.Error("expected error for invalid config file")
	}
	_, err = unmarshalConfig([]byte(``))
	if err == nil {
		t.Error("expected error for invalid config file")
	}
}

func TestConfigParsing(t *testing.T) {
	cfg := Config{
		Version: 1,
		Endpoints: map[string]Endpoint{
			"POST /*/containers/create": Endpoint{},
		},
		Adapters: map[string]string{
			"weave":   "",
			"flocker": "http://flocker/flocker-adapter",
		},
	}

	if err := cfg.Parse(); err == nil {
		t.Error("got nil error for invalid config")
	}
}

func TestEndpointMethodPatternParse(t *testing.T) {
	cfg := newValidConfig()

	for key, endpoint := range cfg.Endpoints {
		splitkey := strings.SplitN(key, " ", 2)
		method := splitkey[0]
		pattern := splitkey[1]

		if endpoint.Method != method {
			t.Errorf("expeted method: %s got method: %s", method, endpoint.Method)
		}

		if endpoint.Pattern != pattern {
			t.Errorf("expeted pattern: %s got pattern: %s", pattern, endpoint.Pattern)
		}
	}
}

func TestEndpointsRequired(t *testing.T) {
	cfg := newValidConfig()

	cfg.Endpoints = nil

	if !hasError(cfg.Parse(), "endpoints are required") {
		t.Error("expected error for missing endpoints")
	}

}

func TestEndpointNoHooks(t *testing.T) {
	cfg := newValidConfig()

	for key, endpoint := range cfg.Endpoints {
		endpoint.Pre = nil
		endpoint.Post = nil
		cfg.Endpoints[key] = endpoint
	}
	if !hasError(cfg.Parse(), "pre or post adapters required") {
		t.Error("expected error for missing pre and post hook adapters")
	}
}

func TestEndpointOptionalPre(t *testing.T) {
	cfg := newValidConfig()

	for key, endpoint := range cfg.Endpoints {
		endpoint.Pre = nil
		cfg.Endpoints[key] = endpoint
	}
	if errs := cfg.Parse(); errs != nil {
		t.Error("expected nil error, got:", errs)
	}
}
func TestEndpointOptionalPost(t *testing.T) {
	cfg := newValidConfig()

	for key, endpoint := range cfg.Endpoints {
		endpoint.Post = nil
		cfg.Endpoints[key] = endpoint
	}
	if errs := cfg.Parse(); errs != nil {
		t.Error("expected nil error, got:", errs)
	}
}

func TestAdaptersRequired(t *testing.T) {
	cfg := newValidConfig()
	cfg.Adapters = map[string]string{}

	if !hasError(cfg.Parse(), "adapters are required") {
		t.Error("got nil error for invalid config")
	}
}

func TestAdapterURLRequired(t *testing.T) {
	cfg := newValidConfig()

	cfg.Adapters = map[string]string{
		"slowreq": "",
	}

	if !hasError(cfg.Parse(), "url requred") {
		t.Error("expected error for missing adapter url")
	}
}

func TestConfigMatch(t *testing.T) {
	cfg := newValidConfig()

	req, _ := http.NewRequest("GET", "http://docker_host/v1.16/containers/json", nil)
	pre, post := cfg.Match(req)
	if pre == nil || post == nil {
		t.Error("expected urls to not be nil")
	}

}
