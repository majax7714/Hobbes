package main

import (
	"bytes"
	"encoding/json"
	"github.com/majax7714/Hobbes/go/internal/version"
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

// TestCalvinBoxFormatsReadOnly resolves against the real dispatch box
// (pipeline/src/hobbes/derive/calvin.box.policy). `gofmt -l` and `-d` run,
// alone or after a `cd`, the way a doer issues them. Anything that writes
// stays a question: `-w` under the allow rule, and `go fmt`, which no rule
// names. Four `gofmt -l` escalations expired in S-20260912T174351Z-404f.
func TestCalvinBoxFormatsReadOnly(t *testing.T) {
	repo := t.TempDir()
	box, err := filepath.Abs(filepath.Join("..", "..", "..", "pipeline", "src", "hobbes", "derive", "calvin.box.policy"))
	if err != nil {
		t.Fatal(err)
	}
	for _, tt := range []struct {
		command string
		want    int
	}{
		{"gofmt -l internal/knowledge", 0},
		{"gofmt -d internal/knowledge/knowledge.go", 0},
		{"cd /work/go && gofmt -l internal/knowledge", 0},
		{"gofmt -l -w internal/knowledge", 20},
		{"gofmt -w internal/knowledge/knowledge.go", 20},
		{"go fmt ./...", 20},
	} {
		code, stdout, stderr := resolve(t, repo, "--repo", repo, "--dir", repo, "--box", box, tt.command)
		if code != tt.want {
			t.Errorf("%q: exit = %d, want %d\n%s%s", tt.command, code, tt.want, stdout, stderr)
		}
	}
}

// TestCalvinBoxRemovesAndProbes resolves the box policy Max approved on
// 2026-09-12 against the real dispatch box. A plain `rm` runs; a recursive
// one stays a question, in each spelling the glob can see (`-r`, `-R`, the
// `-fr`/`-fR` clusters, `--recursive`), alone or after a `cd`. `clang`,
// `cmake` and `bear` answer `--version`, the probes whose escalations
// expired in S-20260912T204447Z-9396; anything else they do takes the
// default. The box's header says why an escalation here is not a boundary.
func TestCalvinBoxRemovesAndProbes(t *testing.T) {
	repo := t.TempDir()
	box, err := filepath.Abs(filepath.Join("..", "..", "..", "pipeline", "src", "hobbes", "derive", "calvin.box.policy"))
	if err != nil {
		t.Fatal(err)
	}
	for _, tt := range []struct {
		command string
		want    int
	}{
		{"rm scratch.py", 0},
		{"rm -f a.txt b.txt", 0},
		{"cd /work && rm -f notes.tmp", 0},
		{"rm -r build", 20},
		{"rm -R build", 20},
		{"rm -rf build", 20},
		{"rm -Rf build", 20},
		{"rm -fr build", 20},
		{"rm -fR build", 20},
		{"rm --recursive build", 20},
		{"cd /work && rm -rf build", 20},
		{"clang --version", 0},
		{"cmake --version", 0},
		{"bear --version", 0},
		{"which clang cmake bear make gcc 2>&1; clang --version 2>&1 | head -3", 0},
		{"clang -c x.c", 20},
	} {
		code, stdout, stderr := resolve(t, repo, "--repo", repo, "--dir", repo, "--box", box, tt.command)
		if code != tt.want {
			t.Errorf("%q: exit = %d, want %d\n%s%s", tt.command, code, tt.want, stdout, stderr)
		}
	}
}

// TestFindsExecutingFormsAndXargsEscalateInBothBoxes resolves ADR-107's
// 2026-09-13 amendment against both real boxes: a plain, read-only `find`
// still runs, but its deleting and executing forms (-delete, -exec,
// -execdir via -exec, -ok, -okdir via -ok) and xargs escalate, alone, after
// a `cd`, and as a pipe segment.
func TestFindsExecutingFormsAndXargsEscalateInBothBoxes(t *testing.T) {
	repo := t.TempDir()
	for _, boxRel := range []string{
		filepath.Join("..", "..", "..", "pipeline", "src", "hobbes", "derive", "calvin.box.policy"),
		filepath.Join("..", "..", "..", "pipeline", "src", "hobbes", "bench", "bench.box.policy"),
	} {
		box, err := filepath.Abs(boxRel)
		if err != nil {
			t.Fatal(err)
		}
		for _, tt := range []struct {
			command string
			want    int
		}{
			{"find . -name '*.go'", 0},
			{"find pipeline -type f | head", 0},
			{"cd /work && find . -maxdepth 2 -type d", 0},
			{"find . -delete", 20},
			{"find . -name '*.tmp' -delete", 20},
			{"find . -exec rm -rf {} +", 20},
			{`find . -execdir rm {} \;`, 20},
			{`find . -ok rm {} \;`, 20},
			{"ls | xargs rm -rf", 20},
			{"find . -name x -print0 | xargs -0 rm", 20},
			{"xargs rm -rf < list.txt", 20},
			{"cd /work && find . -delete", 20},
		} {
			code, stdout, stderr := resolve(t, repo, "--repo", repo, "--dir", repo, "--box", box, tt.command)
			if code != tt.want {
				t.Errorf("%s: %q: exit = %d, want %d\n%s%s", box, tt.command, code, tt.want, stdout, stderr)
			}
		}
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

// ADR-103: every binary states the Hobbes version it was built from.
func TestVersionPrintsTheHobbesVersion(t *testing.T) {
	var out, errb bytes.Buffer
	if code := run([]string{"version"}, &out, &errb); code != 0 {
		t.Fatalf("exit %d: %s", code, errb.String())
	}
	if got := out.String(); got != "hobbes-policy "+version.Version+"\n" {
		t.Fatalf("got %q", got)
	}
}
