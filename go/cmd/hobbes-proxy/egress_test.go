package main

import (
	"bytes"
	"strings"
	"testing"
)

func TestEgressRequiresAnAllowlist(t *testing.T) {
	var stderr bytes.Buffer
	if code := runEgress(nil, &stderr); code != exitUsage || !strings.Contains(stderr.String(), "--allow is required") {
		t.Errorf("no --allow: code %d, stderr %q", code, stderr.String())
	}
}

func TestEgressRefusesAnAllowlistThatWouldWidenTheRoute(t *testing.T) {
	for _, bad := range []string{"*.anthropic.com", "https://api.anthropic.com", "api.anthropic.com:0"} {
		var stderr bytes.Buffer
		if code := runEgress([]string{"--allow", bad}, &stderr); code != exitUsage {
			t.Errorf("--allow %s: code %d, want %d (stderr %q)", bad, code, exitUsage, stderr.String())
		}
	}
}

func TestEgressIsASubcommand(t *testing.T) {
	var stdout, stderr bytes.Buffer
	if code := run([]string{"egress"}, &stdout, &stderr); code != exitUsage {
		t.Errorf("hobbes-proxy egress with no flags: code %d, want %d", code, exitUsage)
	}
}
