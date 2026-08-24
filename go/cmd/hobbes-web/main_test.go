package main

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"testing"
	"time"
)

func cli(args ...string) (int, string, string) {
	var stdout, stderr bytes.Buffer
	code := run(args, &stdout, &stderr)
	return code, stdout.String(), stderr.String()
}

func TestNoArgsUsage(t *testing.T) {
	if code, _, _ := cli(); code != exitUsage {
		t.Errorf("exit = %d, want %d", code, exitUsage)
	}
	if code, _, _ := cli("wat"); code != exitUsage {
		t.Errorf("unknown command: exit = %d, want %d", code, exitUsage)
	}
	if code, out, _ := cli("help"); code != exitOK || !strings.Contains(out, "hobbes-web serve") {
		t.Errorf("help: exit=%d out=%q", code, out)
	}
}

func TestServeRefusesNonLoopbackAddr(t *testing.T) {
	// The refusal must land before anything binds — §7 puts remote
	// access out of scope and this surface can approve commands.
	code, _, stderr := cli("serve", "--repo", t.TempDir(), "--addr", "0.0.0.0:7777")
	if code != exitUsage {
		t.Fatalf("exit = %d, want %d", code, exitUsage)
	}
	if !strings.Contains(stderr, "loopback only") {
		t.Errorf("stderr = %q, want the loopback refusal", stderr)
	}
}

func TestServeRejectsMissingRepo(t *testing.T) {
	code, _, stderr := cli("serve", "--repo", filepath.Join(t.TempDir(), "absent"),
		"--addr", "127.0.0.1:0", "--log-dir", t.TempDir())
	if code != exitError {
		t.Fatalf("exit = %d, want %d (stderr %q)", code, exitError, stderr)
	}
}

func TestServeRejectsStrayArgs(t *testing.T) {
	if code, _, _ := cli("serve", "extra"); code != exitUsage {
		t.Errorf("exit = %d, want %d", code, exitUsage)
	}
}

// TestServeAnswersOverTheWire boots the real server on an ephemeral
// loopback port and asks it a question, so the wiring — flags, listener,
// handler, shutdown — is exercised end to end, not just the router.
func TestServeAnswersOverTheWire(t *testing.T) {
	repo := t.TempDir()
	derived := filepath.Join(repo, ".hobbes", "derived")
	if err := os.MkdirAll(derived, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(derived, "graph.json"),
		[]byte(`{"schema_version":3,"sha":"abc","dirty":false,"languages":["python"],`+
			`"nodes":[{"id":"a","kind":"module"}],"module_edges":[],"symbols":[],"symbol_edges":[]}`),
		0o644); err != nil {
		t.Fatal(err)
	}

	// A pipe stands in for stdout so the banner (which carries the bound
	// address) can be read while the server keeps running.
	pr, pw, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	done := make(chan int, 1)
	go func() {
		done <- run([]string{"serve", "--repo", repo, "--addr", "127.0.0.1:0",
			"--log-dir", filepath.Join(t.TempDir(), "sessions")}, pw, io.Discard)
		pw.Close()
	}()

	banner := make([]byte, 512)
	n, err := pr.Read(banner)
	if err != nil {
		t.Fatalf("no startup banner: %v", err)
	}
	line := string(banner[:n])
	_, url, found := strings.Cut(line, "http://")
	if !found {
		t.Fatalf("banner has no address: %q", line)
	}
	base := "http://" + strings.TrimSpace(strings.SplitN(url, "\n", 2)[0])

	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(base + "/api/graph")
	if err != nil {
		t.Fatalf("GET /api/graph: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d", resp.StatusCode)
	}
	var graph struct {
		SchemaVersion int `json:"schema_version"`
		Nodes         []struct {
			ID string `json:"id"`
		} `json:"nodes"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&graph); err != nil {
		t.Fatal(err)
	}
	if graph.SchemaVersion != 3 || len(graph.Nodes) != 1 || graph.Nodes[0].ID != "a" {
		t.Errorf("served graph = %+v", graph)
	}

	// A request from a name that is not this machine is refused even on
	// the loopback socket (the DNS-rebinding guard).
	req, _ := http.NewRequest(http.MethodGet, base+"/api/graph", nil)
	req.Host = "attacker.example.com"
	rebind, err := client.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer rebind.Body.Close()
	if rebind.StatusCode != http.StatusForbidden {
		t.Errorf("rebinding Host = %d, want 403", rebind.StatusCode)
	}

	// Shut it down the way a user does. The handler is registered before
	// the banner, so by now the signal cannot be missed.
	if err := syscall.Kill(syscall.Getpid(), syscall.SIGTERM); err != nil {
		t.Fatal(err)
	}
	select {
	case code := <-done:
		if code != exitOK {
			t.Errorf("shutdown exit = %d, want %d", code, exitOK)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("server did not shut down on SIGTERM")
	}
	pr.Close()
}
