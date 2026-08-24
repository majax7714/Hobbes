package main

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// fixtureRepo builds a fake repo: a .git marker, a repo policy escalating
// git push and denying tfstate access, and a folder policy under src/
// allowing go test.
func fixtureRepo(t *testing.T) string {
	t.Helper()
	repo := t.TempDir()
	files := map[string]string{
		".git/HEAD": "ref: refs/heads/main\n",
		".hobbes/policies/repo.policy": `version: 1
scope: repo
default: escalate
rules:
  - pattern: "*.tfstate*"
    decision: deny
    reason: "tfstate carries secrets"
  - pattern: "git push*"
    decision: escalate
  - pattern: "git status*"
    decision: allow
`,
		"src/.hobbes/folder.policy": `version: 1
scope: folder
rules:
  - pattern: "go test*"
    decision: allow
`,
	}
	for rel, content := range files {
		path := filepath.Join(repo, filepath.FromSlash(rel))
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return repo
}

// resolve runs the CLI against the fixture repo with --box suppressed via
// --repo/--dir pointing into the fixture (no --box flag means the real
// ~/.hobbes/box.policy could leak in, so tests always pass an empty HOME).
func resolve(t *testing.T, repo string, args ...string) (int, string, string) {
	t.Helper()
	t.Setenv("HOME", filepath.Join(repo, "no-such-home"))
	var stdout, stderr bytes.Buffer
	code := run(append([]string{"resolve"}, args...), &stdout, &stderr)
	return code, stdout.String(), stderr.String()
}

func TestResolveExitCodesAndJSON(t *testing.T) {
	repo := fixtureRepo(t)
	tests := []struct {
		name     string
		dir      string // relative to repo
		command  string
		wantCode int
		wantDec  string
	}{
		{"allow exits 0", ".", "git status", 0, "allow"},
		{"deny exits 10", ".", "cat terraform.tfstate", 10, "deny"},
		{"escalate exits 20", ".", "git push origin main", 20, "escalate"},
		{"default escalate for unknown command", ".", "curl https://example.com", 20, "escalate"},
		{"folder policy applies in its dir", "src", "go test ./...", 0, "allow"},
		{"folder policy does not apply at root", ".", "go test ./...", 20, "escalate"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			code, stdout, stderr := resolve(t, repo,
				"--repo", repo, "--dir", filepath.Join(repo, tt.dir), tt.command)
			if code != tt.wantCode {
				t.Fatalf("exit = %d, want %d (stderr: %s)", code, tt.wantCode, stderr)
			}
			var result struct {
				Decision string `json:"decision"`
				Command  string `json:"command"`
			}
			if err := json.Unmarshal([]byte(stdout), &result); err != nil {
				t.Fatalf("stdout is not JSON: %v\n%s", err, stdout)
			}
			if result.Decision != tt.wantDec {
				t.Errorf("decision = %q, want %q", result.Decision, tt.wantDec)
			}
		})
	}
}

func TestResolveAutoDetectsRepoRoot(t *testing.T) {
	repo := fixtureRepo(t)
	code, stdout, stderr := resolve(t, repo, "--dir", filepath.Join(repo, "src"), "git status")
	if code != 0 {
		t.Fatalf("exit = %d, want 0 (stderr: %s)", code, stderr)
	}
	if !strings.Contains(stdout, `"decision": "allow"`) {
		t.Errorf("unexpected output: %s", stdout)
	}
}

func TestResolveExplicitBoxApplies(t *testing.T) {
	repo := fixtureRepo(t)
	box := filepath.Join(repo, "box.policy")
	if err := os.WriteFile(box, []byte(`version: 1
scope: box
rules:
  - pattern: "git status*"
    decision: deny
    reason: "box floor beats repo allow"
`), 0o644); err != nil {
		t.Fatal(err)
	}
	code, stdout, _ := resolve(t, repo, "--repo", repo, "--dir", repo, "--box", box, "git status")
	if code != 10 {
		t.Fatalf("exit = %d, want 10 (deny from box floor)\n%s", code, stdout)
	}
}

func TestResolveUsageErrors(t *testing.T) {
	repo := fixtureRepo(t)
	var stdout, stderr bytes.Buffer

	if code := run(nil, &stdout, &stderr); code != 2 {
		t.Errorf("no args: exit = %d, want 2", code)
	}
	if code := run([]string{"frobnicate"}, &stdout, &stderr); code != 2 {
		t.Errorf("unknown subcommand: exit = %d, want 2", code)
	}
	if code := run([]string{"resolve", "--repo", repo, "--dir", repo}, &stdout, &stderr); code != 2 {
		t.Errorf("missing command: exit = %d, want 2", code)
	}
}

func TestResolveMissingExplicitBoxIsError(t *testing.T) {
	repo := fixtureRepo(t)
	code, _, stderr := resolve(t, repo, "--repo", repo, "--dir", repo,
		"--box", filepath.Join(repo, "nope.policy"), "git status")
	if code != 1 {
		t.Fatalf("exit = %d, want 1 (stderr: %s)", code, stderr)
	}
}
