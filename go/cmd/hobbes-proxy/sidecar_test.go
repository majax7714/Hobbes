package main

import (
	"bytes"
	"context"
	"net"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/majax7714/Hobbes/go/internal/egress"
	"github.com/majax7714/Hobbes/go/internal/sink"
)

func TestSidecarRequiresADirSessionAndRole(t *testing.T) {
	var stderr bytes.Buffer
	if code := runSidecar(nil, &stderr); code != exitUsage || !strings.Contains(stderr.String(), "--dir") {
		t.Errorf("no --dir: code %d, stderr %q", code, stderr.String())
	}
}

func TestSidecarRefusesAnAllowlistThatWouldWidenTheRoute(t *testing.T) {
	for _, bad := range []string{"*.anthropic.com", "https://api.anthropic.com", "api.anthropic.com:0"} {
		var stderr bytes.Buffer
		code := runSidecar([]string{"--dir", t.TempDir(), "--session", "S-1", "--role", "implementer", "--allow", bad}, &stderr)
		if code != exitUsage {
			t.Errorf("--allow %s: code %d, want %d (stderr %q)", bad, code, exitUsage, stderr.String())
		}
	}
}

func TestSidecarIsASubcommand(t *testing.T) {
	var stdout, stderr bytes.Buffer
	if code := run([]string{"sidecar"}, &stdout, &stderr); code != exitUsage {
		t.Errorf("hobbes-proxy sidecar with no flags: code %d, want %d", code, exitUsage)
	}
}

func listenLoopback(t *testing.T) net.Listener {
	t.Helper()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	return ln
}

func TestServeSidecarWithNoAllowBringsUpOnlyTheSink(t *testing.T) {
	dir := t.TempDir()
	sinkLn := listenLoopback(t)
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() {
		done <- serveSidecar(ctx, sidecarConfig{
			Dir: dir, Session: "S-1", Role: "implementer", SinkLn: sinkLn,
		})
	}()

	client, err := sink.Dial(sinkLn.Addr().String())
	if err != nil {
		t.Fatalf("sink not reachable: %v", err)
	}
	client.Close()

	if _, err := os.Stat(filepath.Join(dir, "egress.jsonl")); !os.IsNotExist(err) {
		t.Errorf("no --allow should mean no egress.jsonl: %v", err)
	}

	cancel()
	if err := <-done; err != nil {
		t.Errorf("serveSidecar: %v", err)
	}
}

func TestServeSidecarWithAllowRunsEgressToo(t *testing.T) {
	dir := t.TempDir()
	sinkLn := listenLoopback(t)
	egressLn := listenLoopback(t)
	logPath := filepath.Join(dir, "egress.jsonl")
	logFile, err := os.OpenFile(logPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o600)
	if err != nil {
		t.Fatal(err)
	}
	allow, err := egress.ParseAllowlist([]string{"example.com"})
	if err != nil {
		t.Fatal(err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() {
		done <- serveSidecar(ctx, sidecarConfig{
			Dir: dir, Session: "S-1", Role: "implementer", SinkLn: sinkLn,
			EgressLn: egressLn, Allow: allow, EgressLog: logFile,
		})
	}()

	var data []byte
	for i := 0; i < 200; i++ {
		data, _ = os.ReadFile(logPath)
		if strings.Contains(string(data), `"event":"listen"`) {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if !strings.Contains(string(data), `"event":"listen"`) {
		t.Fatalf("egress.jsonl never got a listen record: %q", data)
	}

	cancel()
	if err := <-done; err != nil {
		t.Errorf("serveSidecar: %v", err)
	}
	logFile.Close()
}
