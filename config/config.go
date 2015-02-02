package config

import (
	"errors"
	"fmt"
	"net/url"
	"strings"
)

type Config struct {
	Version   int
	Endpoints map[string]Endpoint
	Adapters  map[string]string
}

type Endpoint struct {
	Method string
	Path   string
	Pre    []string
	Post   []string
}

func (c *Config) Validate() []error {
	errs := []error{}
	if len(c.Endpoints) == 0 {
		errs = append(errs, errors.New("endpoints are required"))
	}
	if len(c.Adapters) == 0 {
		errs = append(errs, errors.New("adapters are required"))
	}

	for key, adapter := range c.Adapters {
		if len(adapter) == 0 {
			errs = append(errs, fmt.Errorf("url requred for adapter: %s", key))
		}

		if _, err := url.Parse(adapter); err != nil {
			errs = append(errs, fmt.Errorf("invalid url for adapter: %s", key))
		}

	}

	for key, endpoint := range c.Endpoints {
		if len(endpoint.Pre) == 0 && len(endpoint.Post) == 0 {
			errs = append(errs, fmt.Errorf("pre or post adapters required for endpoint: %s", key))
		}

		splitkey := strings.SplitN(key, " ", 2)
		endpoint.Method = splitkey[0]
		endpoint.Path = splitkey[1]

		c.Endpoints[key] = endpoint

	}

	return errs
}

// version: 1
// endpoints:
//   "POST /*/containers/create":
//     pre: [flocker, weave]
//   "POST /*/containers/*/start":
//     post: [weave]
// adapters:
//   weave: http://weave/extension
//   flocker: http://flocker/flocker-adapter
