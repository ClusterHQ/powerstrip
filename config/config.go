package config

import (
	"errors"
	"fmt"
	"io/ioutil"
	"net/http"
	"net/url"
	"path"
	"strings"

	"gopkg.in/yaml.v1"
)

// Errors is used to return multiple errors from a validation func.
type Errors []error

func (e Errors) Error() string {
	if len(e) == 1 {
		return e[0].Error()
	}

	msg := "multiple errors:"
	for _, err := range e {
		msg += "\n" + err.Error()
	}
	return msg
}

// Config stores the entire config for powerstrip
type Config struct {
	Version   int
	Endpoints map[string]Endpoint
	Adapters  map[string]string
}

// Endpoint is an http endpoint on dockers api adapter.
type Endpoint struct {
	Method  string
	Pattern string
	Pre     []string
	Post    []string
}

// NewConfig reads and parses a yaml config file
func NewConfig(file string) (*Config, error) {
	data, err := ioutil.ReadFile(file)
	if err != nil {
		return nil, err
	}

	conf := &Config{}
	err = yaml.Unmarshal(data, conf)
	if err != nil {
		return nil, err
	}

	errs := conf.Parse()
	if errs != nil {
		return nil, err
	}

	return conf, nil
}

// Parse validates and fills in values on the Config struct.
func (c *Config) Parse() Errors {
	var errs Errors
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
		endpoint.Pattern = splitkey[1]

		c.Endpoints[key] = endpoint

	}

	return errs
}

// Match returns pre and post adapter urls for a request.
func (c *Config) Match(req *http.Request) ([]string, []string) {
	var preURLs, postURLs []string
	for _, endpoint := range c.Endpoints {
		match, _ := path.Match(endpoint.Pattern, req.URL.Path)

		if match {
			for _, name := range endpoint.Pre {
				url, ok := c.Adapters[name]
				if ok {
					url = url + req.URL.Path
					preURLs = append(preURLs, url)
				}
			}

			for _, name := range endpoint.Post {
				url, ok := c.Adapters[name]
				if ok {
					url = url + req.URL.Path
					postURLs = append(postURLs, url)
				}
			}
		}

	}
	return preURLs, postURLs
}
