package main

import (
	"bytes"
	"github.com/majax7714/Hobbes/go/internal/version"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"testing"
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
}

func TestStartRequiresRepoAndRole(t *testing.T) {
	if code, _, _ := cli("start", "--role", "implementer"); code != exitUsage {
		t.Errorf("missing --repo: exit = %d", code)
	}
	if code, _, _ := cli("start", "--repo", t.TempDir()); code != exitUsage {
		t.Errorf("missing --role: exit = %d", code)
	}
}

func TestStartRejectsNonGitRepo(t *testing.T) {
	fakeProxy := filepath.Join(t.TempDir(), "hobbes-proxy")
	os.WriteFile(fakeProxy, []byte("#!/bin/true\n"), 0o755)
	code, _, stderr := cli("start", "--repo", t.TempDir(), "--role", "implementer",
		"--proxy-bin", fakeProxy, "--sessions", t.TempDir(), "--dry-run")
	if code != exitError || !strings.Contains(stderr, "not a git repo") {
		t.Errorf("code=%d stderr=%q", code, stderr)
	}
}

// gitRepo makes a one-commit repo for worktree operations.
func gitRepo(t *testing.T) string {
	t.Helper()
	repo := t.TempDir()
	run := func(args ...string) {
		full := append([]string{"-C", repo, "-c", "user.name=t", "-c", "user.email=t@t"}, args...)
		if out, err := exec.Command("git", full...).CombinedOutput(); err != nil {
			t.Fatalf("git %v: %v: %s", args, err, out)
		}
	}
	run("init", "-q")
	os.WriteFile(filepath.Join(repo, "README.md"), []byte("hi\n"), 0o644)
	run("add", ".")
	run("commit", "-qm", "base")
	return repo
}

func TestDryRunCreatesWorktreeShowsPlanAndCleansUp(t *testing.T) {
	repo := gitRepo(t)
	sessions := t.TempDir()
	fakeProxy := filepath.Join(t.TempDir(), "hobbes-proxy")
	os.WriteFile(fakeProxy, []byte("static\n"), 0o755)

	code, stdout, stderr := cli("start", "--repo", repo, "--role", "implementer",
		"--task", "add a helper", "--session", "S-test",
		"--proxy-bin", fakeProxy, "--sessions", sessions, "--dry-run")
	if code != 0 {
		t.Fatalf("code=%d stderr=%q", code, stderr)
	}
	// Plan is shown, with clean env and the worktree mount. The default
	// world is the sidecar (ADR-112): its own internal network, not
	// --network none.
	for _, want := range []string{
		"podman run", "--network hobbes-int-s-test",
		filepath.Join(sessions, "S-test", "worktree") + ":/work:rw",
		"HOME=/sessions/S-test", "mcpServers", "--disallowedTools Bash",
	} {
		if !strings.Contains(stdout, want) {
			t.Errorf("dry-run missing %q", want)
		}
	}
	// The MCP config was written host-side, under in/.
	cfg := filepath.Join(sessions, "S-test", "in", "mcp.json")
	if _, err := os.Stat(cfg); err != nil {
		t.Errorf("MCP config not written: %v", err)
	}
	// The disposable clone was removed on teardown...
	if _, err := os.Stat(filepath.Join(sessions, "S-test", "worktree")); !os.IsNotExist(err) {
		t.Errorf("session clone not removed: %v", err)
	}
	// ...the canonical repo has no leftover session branch (a clone never
	// creates one there)...
	out, _ := exec.Command("git", "-C", repo, "branch", "--list", "hobbes/S-test").CombinedOutput()
	if strings.TrimSpace(string(out)) != "" {
		t.Errorf("canonical repo grew a session branch: %s", out)
	}
	// ...and the session dir itself (audit trail) is kept.
	if _, err := os.Stat(filepath.Join(sessions, "S-test")); err != nil {
		t.Errorf("session dir should survive teardown: %v", err)
	}
}

func TestSettingsFileWrittenForClaudeRunNotForCommandOverride(t *testing.T) {
	repo := gitRepo(t)
	sessions := t.TempDir()
	fakeProxy := filepath.Join(t.TempDir(), "hobbes-proxy")
	os.WriteFile(fakeProxy, []byte("static\n"), 0o755)

	// The default (sidecar) world: the settings file lands under in/, the
	// one host dir the doer's container reads (ADR-112).
	opt := options{repo: repo, role: "implementer", session: "S-settings",
		sessions: sessions, proxyBin: fakeProxy}
	_, _, cleanup, err := setup(opt)
	if err != nil {
		t.Fatal(err)
	}
	cleanup()
	settings := filepath.Join(sessions, "S-settings", "in", "claude-settings.json")
	if _, err := os.Stat(settings); err != nil {
		t.Errorf("settings file not written under in/ for a Claude run: %v", err)
	}
	if _, err := os.Stat(filepath.Join(sessions, "S-settings", "claude-settings.json")); !os.IsNotExist(err) {
		t.Errorf("the sidecar world must not write the settings file at the session dir's root: %v", err)
	}

	opt2 := options{repo: repo, role: "implementer", session: "S-cmd",
		sessions: sessions, proxyBin: fakeProxy, command: []string{"python3", "/sessions/driver.py"}}
	_, _, cleanup2, err := setup(opt2)
	if err != nil {
		t.Fatal(err)
	}
	cleanup2()
	if _, err := os.Stat(filepath.Join(sessions, "S-cmd", "in", "claude-settings.json")); !os.IsNotExist(err) {
		t.Errorf("a command override should get no settings file: %v", err)
	}

	// The file world (an explicit --network): the settings file lands at
	// the session dir's root, as before ADR-112.
	opt3 := options{repo: repo, role: "implementer", session: "S-file",
		sessions: sessions, proxyBin: fakeProxy, network: "pasta"}
	_, _, cleanup3, err := setup(opt3)
	if err != nil {
		t.Fatal(err)
	}
	cleanup3()
	if _, err := os.Stat(filepath.Join(sessions, "S-file", "claude-settings.json")); err != nil {
		t.Errorf("the file world's settings file must land at the session dir's root: %v", err)
	}
}

func TestSelinuxRelabelOnMounts(t *testing.T) {
	repo := gitRepo(t)
	fakeProxy := filepath.Join(t.TempDir(), "hobbes-proxy")
	os.WriteFile(fakeProxy, []byte("static\n"), 0o755)
	_, stdout, _ := cli("start", "--repo", repo, "--role", "implementer",
		"--session", "S-z", "--proxy-bin", fakeProxy, "--sessions", t.TempDir(), "--dry-run")
	if !strings.Contains(stdout, ":/work:rw,z") {
		t.Error("worktree mount should request an SELinux relabel (z) for rootless podman")
	}
}

func TestSessionCloneIsSelfContained(t *testing.T) {
	// A clone, not a linked worktree: its .git is a directory, so git
	// works inside a container that mounts only the worktree.
	repo := gitRepo(t)
	sessions := t.TempDir()
	fakeProxy := filepath.Join(t.TempDir(), "hobbes-proxy")
	os.WriteFile(fakeProxy, []byte("static\n"), 0o755)

	opt := options{repo: repo, role: "implementer", session: "S-clone",
		sessions: sessions, proxyBin: fakeProxy}
	_, worktree, cleanup, err := setup(opt)
	if err != nil {
		t.Fatal(err)
	}
	defer cleanup()
	info, err := os.Stat(filepath.Join(worktree, ".git"))
	if err != nil || !info.IsDir() {
		t.Errorf(".git should be a self-contained dir in the clone, got %v", err)
	}
	// git status works with no reference to any path outside the clone.
	if out, err := exec.Command("git", "-C", worktree, "status", "--short").CombinedOutput(); err != nil {
		t.Errorf("git in the clone failed: %v: %s", err, out)
	}
}

func TestRefPinsTheSessionTree(t *testing.T) {
	// V2.M6: a soft-verdict reviewer must read the head of the range
	// under review, which is not necessarily the repo's HEAD.
	repo := gitRepo(t)
	first, err := exec.Command("git", "-C", repo, "rev-parse", "HEAD").Output()
	if err != nil {
		t.Fatal(err)
	}
	os.WriteFile(filepath.Join(repo, "later.txt"), []byte("later\n"), 0o644)
	exec.Command("git", "-C", repo, "add", "-A").Run()
	exec.Command("git", "-C", repo, "commit", "-qm", "later").Run()

	sessions := t.TempDir()
	fakeProxy := filepath.Join(t.TempDir(), "hobbes-proxy")
	os.WriteFile(fakeProxy, []byte("static\n"), 0o755)
	opt := options{repo: repo, role: "reviewer", session: "S-ref",
		ref: strings.TrimSpace(string(first)), sessions: sessions, proxyBin: fakeProxy}
	_, worktree, cleanup, err := setup(opt)
	if err != nil {
		t.Fatal(err)
	}
	defer cleanup()
	if _, err := os.Stat(filepath.Join(worktree, "later.txt")); !os.IsNotExist(err) {
		t.Errorf("worktree at --ref should predate later.txt (stat err %v)", err)
	}
}

func TestSessionCloneDoesNotHardlinkObjects(t *testing.T) {
	// A local clone hardlinks objects by default, and a hardlink cannot
	// cross a filesystem — so a repo on a different device than the
	// sessions dir failed to clone at all. Asserting link count rather
	// than staging two filesystems: unlinked objects are the property
	// that makes the cross-device case work, and it holds anywhere.
	repo := gitRepo(t)
	fakeProxy := filepath.Join(t.TempDir(), "hobbes-proxy")
	os.WriteFile(fakeProxy, []byte("static\n"), 0o755)

	opt := options{repo: repo, role: "implementer", session: "S-links",
		sessions: t.TempDir(), proxyBin: fakeProxy}
	_, worktree, cleanup, err := setup(opt)
	if err != nil {
		t.Fatal(err)
	}
	defer cleanup()

	objects := 0
	err = filepath.WalkDir(filepath.Join(worktree, ".git", "objects"),
		func(path string, d fs.DirEntry, err error) error {
			if err != nil || d.IsDir() {
				return err
			}
			info, err := d.Info()
			if err != nil {
				return err
			}
			objects++
			if st, ok := info.Sys().(*syscall.Stat_t); ok && st.Nlink > 1 {
				t.Errorf("%s has %d links; the clone must not hardlink into the "+
					"canonical repo (breaks across filesystems)", path, st.Nlink)
			}
			return nil
		})
	if err != nil {
		t.Fatal(err)
	}
	if objects == 0 {
		t.Fatal("no object files found in the clone; the assertion checked nothing")
	}
}

func TestMissingProxyBinIsAClearError(t *testing.T) {
	repo := gitRepo(t)
	code, _, stderr := cli("start", "--repo", repo, "--role", "implementer",
		"--proxy-bin", "/nonexistent/hobbes-proxy", "--sessions", t.TempDir(), "--dry-run")
	if code != exitError || !strings.Contains(stderr, "proxy binary") {
		t.Errorf("code=%d stderr=%q", code, stderr)
	}
}

func TestCommandOverrideParsedAfterDoubleDash(t *testing.T) {
	repo := gitRepo(t)
	fakeProxy := filepath.Join(t.TempDir(), "hobbes-proxy")
	os.WriteFile(fakeProxy, []byte("static\n"), 0o755)
	code, stdout, stderr := cli("start", "--repo", repo, "--role", "implementer",
		"--session", "S-ov", "--proxy-bin", fakeProxy, "--sessions", t.TempDir(),
		"--dry-run", "--", "python3", "/sessions/driver.py")
	if code != 0 {
		t.Fatalf("code=%d stderr=%q", code, stderr)
	}
	if !strings.Contains(stdout, "python3 /sessions/driver.py") {
		t.Errorf("override command not in plan:\n%s", stdout)
	}
	if strings.Contains(stdout, "claude") {
		t.Error("override should replace the default claude command")
	}
}

func TestHarvestFetchesSessionCommitsIntoTheRepo(t *testing.T) {
	repo := gitRepo(t)
	proxy := filepath.Join(t.TempDir(), "hobbes-proxy")
	os.WriteFile(proxy, []byte("#!/bin/true\n"), 0o755)
	opt := options{repo: repo, role: "implementer", session: "S-harvest",
		sessions: t.TempDir(), proxyBin: proxy}
	_, worktree, startRef, cleanup, err := setupWithStart(opt)
	if err != nil {
		t.Fatal(err)
	}
	defer cleanup()

	var stderr bytes.Buffer
	harvest(repo, worktree, "hobbes/S-harvest", startRef, &stderr)
	if !strings.Contains(stderr.String(), "no commits to harvest") {
		t.Errorf("empty harvest message missing: %s", stderr.String())
	}

	// The session commits twice on its branch.
	if err := os.WriteFile(filepath.Join(worktree, "new.txt"), []byte("x\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	for _, args := range [][]string{
		{"add", "new.txt"},
		{"-c", "user.name=s", "-c", "user.email=s@s", "commit", "-qm", "one"},
		{"-c", "user.name=s", "-c", "user.email=s@s", "commit", "-qm", "two", "--allow-empty"},
	} {
		if out, err := gitOut(worktree, args...); err != nil {
			t.Fatalf("git %v: %v: %s", args, err, out)
		}
	}

	stderr.Reset()
	harvest(repo, worktree, "hobbes/S-harvest", startRef, &stderr)
	if !strings.Contains(stderr.String(), "branch hobbes/S-harvest harvested (2 commits)") {
		t.Errorf("harvest message = %q", stderr.String())
	}
	out, err := gitOut(repo, "rev-list", "--count", "HEAD..hobbes/S-harvest")
	if err != nil || strings.TrimSpace(out) != "2" {
		t.Errorf("canonical repo branch has %q commits past HEAD (err %v), want 2", out, err)
	}
}

// ADR-055: --model reaches the default Claude Code command.
func TestModelFlagPinsTheSessionModel(t *testing.T) {
	repo := gitRepo(t)
	fakeProxy := filepath.Join(t.TempDir(), "hobbes-proxy")
	os.WriteFile(fakeProxy, []byte("static\n"), 0o755)
	code, stdout, stderr := cli("start", "--repo", repo, "--role", "implementer",
		"--session", "S-model", "--proxy-bin", fakeProxy, "--sessions", t.TempDir(),
		"--model", "claude-haiku-4-5-20251001", "--dry-run")
	if code != 0 {
		t.Fatalf("code=%d stderr=%q", code, stderr)
	}
	if !strings.Contains(stdout, "--model claude-haiku-4-5-20251001") {
		t.Errorf("model not in plan:\n%s", stdout)
	}
}

// ADR-056: --runtime copies the loop and the brief into the session dir
// and the plan runs them in place of Claude Code.
func TestRuntimeFlagCopiesLoopAndBriefIntoTheSessionDir(t *testing.T) {
	repo := gitRepo(t)
	fakeProxy := filepath.Join(t.TempDir(), "hobbes-proxy")
	os.WriteFile(fakeProxy, []byte("static\n"), 0o755)
	loop := filepath.Join(t.TempDir(), "loop.py")
	os.WriteFile(loop, []byte("print('loop')\n"), 0o644)
	sessions := t.TempDir()
	code, stdout, stderr := cli("start", "--repo", repo, "--role", "implementer",
		"--session", "S-rt", "--proxy-bin", fakeProxy, "--sessions", sessions, "--network", "pasta",
		"--runtime", loop, "--llm-base-url", "http://llm/v1", "--model", "m", "--task", "the brief", "--dry-run")
	if code != 0 {
		t.Fatalf("code=%d stderr=%q", code, stderr)
	}
	if !strings.Contains(stdout, "python3 /sessions/S-rt/agent.py") {
		t.Errorf("runtime not in plan:\n%s", stdout)
	}
	if b, err := os.ReadFile(filepath.Join(sessions, "S-rt", "agent.py")); err != nil || string(b) != "print('loop')\n" {
		t.Errorf("loop not copied: %v %q", err, b)
	}
	if b, err := os.ReadFile(filepath.Join(sessions, "S-rt", "brief.md")); err != nil || string(b) != "the brief" {
		t.Errorf("brief not written: %v %q", err, b)
	}
}

// TestRuntimeWithoutNetworkIsRefused is ADR-112: the owned runtime's
// transcript lands in the session dir for the harness to read, which the
// sidecar world's tmpfs would lose, so the CLI needs --network too.
func TestRuntimeWithoutNetworkIsRefused(t *testing.T) {
	repo := gitRepo(t)
	fakeProxy := filepath.Join(t.TempDir(), "hobbes-proxy")
	os.WriteFile(fakeProxy, []byte("static\n"), 0o755)
	loop := filepath.Join(t.TempDir(), "loop.py")
	os.WriteFile(loop, []byte("print('loop')\n"), 0o644)
	code, _, stderr := cli("start", "--repo", repo, "--role", "implementer",
		"--session", "S-rt-no-net", "--proxy-bin", fakeProxy, "--sessions", t.TempDir(),
		"--runtime", loop, "--llm-base-url", "http://llm/v1", "--model", "m", "--task", "the brief", "--dry-run")
	if code != exitError || !strings.Contains(stderr, "--network") {
		t.Errorf("a runtime with no --network must be refused naming --network: code=%d stderr=%q", code, stderr)
	}
}

func TestSessionCloneHasACommitIdentity(t *testing.T) {
	// ADR-058: a clone carries no identity and the sandbox has no global
	// git config, so without seeding every in-session commit fails 128.
	repo := gitRepo(t)
	gitOut(repo, "config", "user.name", "Repo Owner")
	gitOut(repo, "config", "user.email", "owner@example.test")
	sessions := t.TempDir()
	proxy := filepath.Join(t.TempDir(), "hobbes-proxy")
	os.WriteFile(proxy, []byte("#!/bin/sh\n"), 0o755)
	opt := options{repo: repo, role: "implementer", session: "S-id", sessions: sessions, proxyBin: proxy}
	_, worktree, cleanup, err := setup(opt)
	if err != nil {
		t.Fatal(err)
	}
	defer cleanup()
	name, _ := gitOut(worktree, "config", "--get", "user.name")
	email, _ := gitOut(worktree, "config", "--get", "user.email")
	if strings.TrimSpace(name) != "Repo Owner" || strings.TrimSpace(email) != "owner@example.test" {
		t.Errorf("identity not copied: %q %q", name, email)
	}
	// and a repo without one — nor a global one — gets the session default
	t.Setenv("GIT_CONFIG_GLOBAL", "/dev/null")
	t.Setenv("GIT_CONFIG_NOSYSTEM", "1")
	bare := gitRepo(t)
	gitOut(bare, "config", "--unset", "user.name")
	gitOut(bare, "config", "--unset", "user.email")
	_, wt2, cleanup2, err := setup(options{repo: bare, role: "implementer", session: "S-id2", sessions: sessions, proxyBin: proxy})
	if err != nil {
		t.Fatal(err)
	}
	defer cleanup2()
	name, _ = gitOut(wt2, "config", "--get", "user.name")
	if strings.TrimSpace(name) != "hobbes-session" {
		t.Errorf("default identity missing: %q", name)
	}
}

func TestTaskFileCarriesTheBrief(t *testing.T) {
	// ADR-058: a unit brief can exceed the argv limit, so it travels as a file.
	dir := t.TempDir()
	brief := filepath.Join(dir, "brief.md")
	os.WriteFile(brief, []byte("do the thing\nover two lines\n"), 0o600)
	proxy := filepath.Join(dir, "hobbes-proxy")
	os.WriteFile(proxy, []byte("static\n"), 0o755)
	var errb bytes.Buffer
	opt, code := parseStart([]string{"--repo", "r", "--role", "implementer", "--proxy-bin", proxy, "--task-file", brief}, &errb)
	if code != 0 || opt.task != "do the thing\nover two lines\n" {
		t.Fatalf("code %d task %q err %s", code, opt.task, errb.String())
	}
	_, code = parseStart([]string{"--repo", "r", "--role", "implementer", "--proxy-bin", proxy, "--task", "x", "--task-file", brief}, &errb)
	if code == 0 {
		t.Error("--task and --task-file together must be refused")
	}
	_, code = parseStart([]string{"--repo", "r", "--role", "implementer", "--proxy-bin", proxy, "--task-file", dir + "/missing"}, &errb)
	if code == 0 {
		t.Error("a missing task file must be an error")
	}
}

func TestCommitOnExitCommitsLeftoversButNeverHobbesDir(t *testing.T) {
	// ADR-058: a solo session's uncommitted edits are committed by the
	// wrapper, named as its own, with .hobbes/ excluded (P1).
	repo := gitRepo(t)
	// In a session the worktree carries the identity seedIdentity gave it;
	// this fixture stands in for that worktree, so seed it the same way —
	// on a box with no global git config (a CI runner) the commit below
	// otherwise dies with "Author identity unknown" (2026-09-06).
	seedIdentity(repo, repo)
	os.WriteFile(filepath.Join(repo, "edited.txt"), []byte("changed\n"), 0o644)
	os.WriteFile(filepath.Join(repo, "new.txt"), []byte("new\n"), 0o644)
	os.MkdirAll(filepath.Join(repo, ".hobbes", "derived"), 0o755)
	os.WriteFile(filepath.Join(repo, ".hobbes", "derived", "graph.json"), []byte("{}"), 0o644)
	var errb bytes.Buffer
	commitLeftovers(repo, &errb)
	if !strings.Contains(errb.String(), "committed 2 uncommitted file(s) at exit") {
		t.Fatalf("report line missing: %q", errb.String())
	}
	shown, _ := gitOut(repo, "show", "--stat", "--format=%s", "HEAD")
	if !strings.Contains(shown, "hobbes-session: uncommitted work at session end (2 files)") {
		t.Errorf("commit message: %s", shown)
	}
	if strings.Contains(shown, ".hobbes") {
		t.Errorf(".hobbes must never be committed: %s", shown)
	}
	// a clean tree is a no-op
	errb.Reset()
	commitLeftovers(repo, &errb)
	if errb.Len() != 0 {
		t.Errorf("clean tree should print nothing, got %q", errb.String())
	}
}

func TestMountFlagBindsAHostTreeReadOnly(t *testing.T) {
	repo := gitRepo(t)
	fakeProxy := filepath.Join(t.TempDir(), "hobbes-proxy")
	os.WriteFile(fakeProxy, []byte("static\n"), 0o755)
	venv := t.TempDir()
	code, stdout, stderr := cli("start", "--repo", repo, "--role", "implementer",
		"--session", "S-m", "--proxy-bin", fakeProxy, "--sessions", t.TempDir(),
		"--mount", venv, "--mount", venv+":/deps", "--dry-run")
	if code != 0 {
		t.Fatalf("code=%d stderr=%q", code, stderr)
	}
	for _, want := range []string{venv + ":" + venv + ":ro", venv + ":/deps:ro", "--security-opt label=disable"} {
		if !strings.Contains(stdout, want) {
			t.Errorf("dry-run missing %q in %s", want, stdout)
		}
	}
	if code, _, stderr := cli("start", "--repo", repo, "--role", "implementer", "--proxy-bin", fakeProxy,
		"--sessions", t.TempDir(), "--mount", "relative/path", "--dry-run"); code == 0 || !strings.Contains(stderr, "absolute") {
		t.Errorf("a relative mount must be refused: code=%d stderr=%q", code, stderr)
	}
}

// ADR-103: every binary states the Hobbes version it was built from.
func TestVersionPrintsTheHobbesVersion(t *testing.T) {
	var out, errb bytes.Buffer
	if code := run([]string{"version"}, &out, &errb); code != 0 {
		t.Fatalf("exit %d: %s", code, errb.String())
	}
	if got := out.String(); got != "hobbes-session "+version.Version+"\n" {
		t.Fatalf("got %q", got)
	}
}

// fakeProxyBin is a stand-in proxy binary for dry runs.
// staticProxyBin builds the real hobbes-proxy, static, for a live test:
// the session mounts it and the sidecar container runs it (ADR-112), so a
// live session cannot be made of the fake one.
func staticProxyBin(t *testing.T) string {
	t.Helper()
	proxyBin := filepath.Join(t.TempDir(), "hobbes-proxy")
	build := exec.Command("go", "build", "-o", proxyBin, "github.com/majax7714/Hobbes/go/cmd/hobbes-proxy")
	build.Env = append(os.Environ(), "CGO_ENABLED=0")
	if out, err := build.CombinedOutput(); err != nil {
		t.Fatalf("static proxy build: %v: %s", err, out)
	}
	return proxyBin
}

func fakeProxyBin(t *testing.T) string {
	t.Helper()
	p := filepath.Join(t.TempDir(), "hobbes-proxy")
	os.WriteFile(p, []byte("#!/bin/true\n"), 0o755)
	return p
}

func TestEgressDryRunShowsTheRouteAndPutsTheSessionOnTheInternalNetwork(t *testing.T) {
	code, stdout, stderr := cli("start", "--repo", gitRepo(t), "--role", "implementer", "--proxy-bin", fakeProxyBin(t),
		"--sessions", t.TempDir(), "--session", "S-dry-egress", "--egress", "api.anthropic.com", "--dry-run", "--", "true")
	if code != 0 {
		t.Fatalf("code=%d stderr=%s", code, stderr)
	}
	for _, want := range []string{"--network hobbes-int-s-dry-egress", "HTTPS_PROXY=http://hobbes-side-s-dry-egress:3128",
		"setup:    podman network create --internal hobbes-int-s-dry-egress", "sidecar --dir /log --session S-dry-egress",
		"--sink-listen 0.0.0.0:3129 --listen 0.0.0.0:3128", "--allow api.anthropic.com:443",
		"teardown: podman network rm -f hobbes-int-s-dry-egress"} {
		if !strings.Contains(stdout, want) {
			t.Errorf("dry run lacks %q:\n%s", want, stdout)
		}
	}
	if strings.Contains(stdout, "--network none") {
		t.Error("a session behind the sidecar is not on --network none; it is on its own internal network")
	}
}

func TestEgressBesideANetworkIsRefused(t *testing.T) {
	code, _, stderr := cli("start", "--repo", gitRepo(t), "--role", "implementer", "--proxy-bin", fakeProxyBin(t),
		"--sessions", t.TempDir(), "--egress", "api.anthropic.com", "--network", "pasta", "--dry-run", "--", "true")
	if code != exitError || !strings.Contains(stderr, "exclusive") {
		t.Errorf("code=%d stderr=%q", code, stderr)
	}
}

func TestClaudeCredIsWithdrawn(t *testing.T) {
	code, _, stderr := cli("start", "--repo", gitRepo(t), "--role", "implementer", "--proxy-bin", fakeProxyBin(t),
		"--sessions", t.TempDir(), "--claude-cred", "--dry-run")
	if code != exitUsage || !strings.Contains(stderr, "withdrawn") || !strings.Contains(stderr, "CLAUDE_CODE_OAUTH_TOKEN") {
		t.Errorf("code=%d stderr=%q", code, stderr)
	}
}

func TestClaudeTokenNeverReachesTheDryRun(t *testing.T) {
	t.Setenv("CLAUDE_CODE_OAUTH_TOKEN", "sekrit-token")
	bin := filepath.Join(t.TempDir(), "claude")
	os.WriteFile(bin, []byte("#!/bin/true\n"), 0o755)
	code, stdout, stderr := cli("start", "--repo", gitRepo(t), "--role", "implementer", "--proxy-bin", fakeProxyBin(t),
		"--sessions", t.TempDir(), "--claude-bin", bin, "--egress", "api.anthropic.com", "--dry-run")
	if code != 0 {
		t.Fatalf("code=%d stderr=%s", code, stderr)
	}
	if strings.Contains(stdout, "sekrit") {
		t.Fatalf("the token reached the dry run:\n%s", stdout)
	}
	for _, want := range []string{"--env CLAUDE_CODE_OAUTH_TOKEN ", "set, passed by name", bin + ":/usr/local/bin/claude:ro", "--strict-mcp-config"} {
		if !strings.Contains(stdout, want) {
			t.Errorf("dry run lacks %q:\n%s", want, stdout)
		}
	}
}

func TestALiveClaudeSessionRefusesWhatWouldFailInsideTheContainer(t *testing.T) {
	bin := filepath.Join(t.TempDir(), "claude")
	os.WriteFile(bin, []byte("#!/bin/true\n"), 0o755)
	base := []string{"start", "--repo", gitRepo(t), "--role", "implementer", "--proxy-bin", fakeProxyBin(t), "--sessions", t.TempDir(), "--claude-bin", bin}

	t.Setenv("CLAUDE_CODE_OAUTH_TOKEN", "")
	if code, _, stderr := cli(append(base, "--egress", "api.anthropic.com")...); code != exitError || !strings.Contains(stderr, "CLAUDE_CODE_OAUTH_TOKEN") {
		t.Errorf("no token: code=%d stderr=%q", code, stderr)
	}
	t.Setenv("CLAUDE_CODE_OAUTH_TOKEN", "tok")
	if code, _, stderr := cli(base...); code != exitError || !strings.Contains(stderr, "--egress") {
		t.Errorf("no route: code=%d stderr=%q", code, stderr)
	}
}

// TestEgressRouteLiveAllowsTheListAndNothingElse is ADR-107's guarantee at
// the level a user meets it (P10): a real session behind the real proxy,
// on a real internal network. A host on the list answers through the
// tunnel; another port of it, and any address without the proxy, do not.
// The upstream sits on the egress bridge only, so the session can reach it
// through the proxy and no other way. Skips without podman or the image.
func TestEgressRouteLiveAllowsTheListAndNothingElse(t *testing.T) {
	if testing.Short() {
		t.Skip("live podman test")
	}
	if _, err := exec.LookPath("podman"); err != nil {
		t.Skip("podman not installed")
	}
	image := "hobbes-session:local"
	if exec.Command("podman", "image", "exists", image).Run() != nil {
		t.Skip("the sandbox image is not built")
	}
	proxyBin := staticProxyBin(t)
	if exec.Command("podman", "network", "exists", "hobbes-egress").Run() != nil {
		if out, err := exec.Command("podman", "network", "create", "hobbes-egress").CombinedOutput(); err != nil {
			t.Fatalf("bridge: %v: %s", err, out)
		}
	}
	up := "hobbes-test-up-" + strings.ToLower(filepath.Base(t.TempDir()))
	if out, err := exec.Command("podman", "run", "-d", "--rm", "--name", up, "--network", "hobbes-egress", "--pull=never", image,
		"python3", "-m", "http.server", "8080").CombinedOutput(); err != nil {
		t.Fatalf("upstream: %v: %s", err, out)
	}
	t.Cleanup(func() { exec.Command("podman", "rm", "-f", "-t", "0", up).Run() })

	script := `mkdir -p "$HOME/.claude/projects/-work" && echo '{"type":"thinking"}' > "$HOME/.claude/projects/-work/t.jsonl" && echo '{}' > "$HOME/.claude.json"
a=$(curl -s -o /dev/null -w '%{http_code}' -p -x "$HTTPS_PROXY" --max-time 10 http://` + up + `:8080/)
b=$(curl -s -o /dev/null -w '%{http_connect}' -p -x "$HTTPS_PROXY" --max-time 10 http://` + up + `:8081/)
c=$(curl -s -o /dev/null -w '%{http_code}' --noproxy '*' --max-time 5 http://` + up + `:8080/)
d=$(curl -s -o /dev/null -w '%{http_code}' --noproxy '*' --max-time 5 http://1.1.1.1/)
echo "ALLOWED=$a REFUSED=$b DIRECT=$c PUBLIC=$d"`
	sessions := t.TempDir()
	code, stdout, stderr := cli("start", "--repo", gitRepo(t), "--role", "implementer", "--proxy-bin", proxyBin,
		"--sessions", sessions, "--session", "S-live-egress", "--egress", up+":8080", "--", "sh", "-c", script)
	if code != 0 {
		t.Fatalf("session: code=%d\nstdout=%s\nstderr=%s", code, stdout, stderr)
	}
	for _, want := range []string{"ALLOWED=200", "REFUSED=403", "DIRECT=000", "PUBLIC=000"} {
		if !strings.Contains(stdout, want) {
			t.Errorf("route: want %s in %q\nstderr=%s", want, stdout, stderr)
		}
	}
	logData, err := os.ReadFile(filepath.Join(sessions, "S-live-egress", "egress.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	log := string(logData)
	if !strings.Contains(log, `"event":"connect","method":"CONNECT","target":"`+up+`:8080"`) ||
		!strings.Contains(log, `"event":"refuse","method":"CONNECT","target":"`+up+`:8081"`) {
		t.Errorf("egress log should record the tunnel and the refusal:\n%s", log)
	}
	if out, _ := exec.Command("podman", "network", "exists", "hobbes-int-s-live-egress").CombinedOutput(); exec.Command("podman", "network", "exists", "hobbes-int-s-live-egress").Run() == nil {
		t.Errorf("the session's internal network outlived it: %s", out)
	}
	if exec.Command("podman", "container", "exists", "hobbes-side-s-live-egress").Run() == nil {
		t.Error("the session's sidecar outlived it")
	}
	if !strings.Contains(stderr, "egress: allow") {
		t.Errorf("the launcher should print the log's summary:\n%s", stderr)
	}
	// ADR-112: the doer's HOME is a tmpfs in the sidecar world, so
	// whatever it wrote there (a transcript, a memory file) dies with the
	// container — never mounted, so never on the host in the first
	// place, and never reported as a purge (that message is the file
	// world's now).
	for _, gone := range []string{".claude", ".claude.json"} {
		if _, err := os.Stat(filepath.Join(sessions, "S-live-egress", gone)); err == nil {
			t.Errorf("%s reached the host", gone)
		}
	}
	if strings.Contains(stderr, "retention:") {
		t.Errorf("the sidecar world purges nothing on the host, so it reports nothing:\n%s", stderr)
	}
}

// TestALiveSessionMountsOnlyItsOwnSessionDir is ADR-107's 2026-09-13
// amendment, narrowed by ADR-112, the guarantee where a user meets it
// (P10): in the sidecar world (the default) the session's own dir is
// mounted nowhere but its in/ subdir, so `/sessions/<id>` holds only `in`
// — and a sibling session's clone and records are not reachable, however
// a command inside spells it. Skips without podman or the image, like the
// live egress test.
func TestALiveSessionMountsOnlyItsOwnSessionDir(t *testing.T) {
	if testing.Short() {
		t.Skip("live podman test")
	}
	if _, err := exec.LookPath("podman"); err != nil {
		t.Skip("podman not installed")
	}
	image := "hobbes-session:local"
	if exec.Command("podman", "image", "exists", image).Run() != nil {
		t.Skip("the sandbox image is not built")
	}
	sessions := t.TempDir()
	sibling := filepath.Join(sessions, "S-sibling")
	if err := os.MkdirAll(sibling, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(sibling, "secret.txt"), []byte("do not read me\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	// The listing is tagged and read line by line: the `cat` error below
	// echoes the sibling's path, so a search of the whole output would
	// find that path even when nothing of the sibling is mounted. In the
	// sidecar world only this session's in/ subdir is mounted, so
	// /sessions itself no longer names anything to list.
	script := `ls -1 /sessions/S-live-mount | sed 's/^/LS /'
cat /sessions/S-sibling/secret.txt 2>&1
true`
	// The real static proxy: the sidecar is made of it, and a sidecar made
	// of the fake never listens, so the session never starts.
	code, stdout, stderr := cli("start", "--repo", gitRepo(t), "--role", "implementer", "--proxy-bin", staticProxyBin(t),
		"--sessions", sessions, "--session", "S-live-mount", "--", "sh", "-c", script)
	if code != 0 {
		t.Fatalf("session: code=%d\nstdout=%s\nstderr=%s", code, stdout, stderr)
	}
	var listed []string
	for _, line := range strings.Split(stdout, "\n") {
		if name, ok := strings.CutPrefix(line, "LS "); ok {
			listed = append(listed, strings.TrimSpace(name))
		}
	}
	if len(listed) != 1 || listed[0] != "in" {
		t.Errorf("/sessions/<id> should hold in/ and nothing else, got %q:\n%s", listed, stdout)
	}
	if strings.Contains(stdout, "do not read me") {
		t.Errorf("the session read a sibling session's file:\n%s", stdout)
	}
}

// TestALiveSessionCannotReachItsOwnRecords is ADR-112 item 7: a doer's
// container cannot delete its own flight log (it is not mounted there at
// all) and cannot forge a flight line by hand — the sink stamps its own
// session and role, and it takes exactly one stream, ever, refusing and
// recording any later open. Skips without podman or the image, like the
// other live tests.
func TestALiveSessionCannotReachItsOwnRecords(t *testing.T) {
	if testing.Short() {
		t.Skip("live podman test")
	}
	if _, err := exec.LookPath("podman"); err != nil {
		t.Skip("podman not installed")
	}
	image := "hobbes-session:local"
	if exec.Command("podman", "image", "exists", image).Run() != nil {
		t.Skip("the sandbox image is not built")
	}
	proxyBin := staticProxyBin(t)

	const sid = "s-live-sink"
	script := `import json, os, socket

sid = "` + sid + `"
for name in sorted(os.listdir("/sessions/" + sid)):
    print("LS " + name)
try:
    os.remove("/sessions/" + sid + "/flight.jsonl")
except Exception as e:
    print(type(e).__name__)

def rpc(sock, obj):
    sock.sendall((json.dumps(obj) + "\n").encode())
    buf = b""
    while not buf.endswith(b"\n"):
        buf += sock.recv(4096)
    return buf.decode().strip()

s1 = socket.create_connection(("hobbes-side-" + sid, 3129), timeout=10)
print(rpc(s1, {"kind": "open"}))
print(rpc(s1, {"kind": "event", "event": {"tool": "exec", "argv": ["/bin/sh", "-c", "true"],
                                           "decision": "allow", "policy_rule": "test",
                                           "session": "forged", "role": "forged"}}))

# s1 stays open while the second attempt is refused, so the sink records
# the refusal before the eventual close (process exit) closes s1 and the
# sink notices — the order the flight log is checked against.
s2 = socket.create_connection(("hobbes-side-" + sid, 3129), timeout=10)
print(rpc(s2, {"kind": "open"}))
s2.close()
`
	sessions := t.TempDir()
	code, stdout, stderr := cli("start", "--repo", gitRepo(t), "--role", "implementer", "--proxy-bin", proxyBin,
		"--sessions", sessions, "--session", sid, "--", "python3", "-c", script)
	if code != 0 {
		t.Fatalf("session: code=%d\nstdout=%s\nstderr=%s", code, stdout, stderr)
	}
	if !strings.Contains(stdout, "LS in") || strings.Count(stdout, "LS ") != 1 {
		t.Errorf("/sessions/%s should list in/ alone:\n%s", sid, stdout)
	}
	if !strings.Contains(stdout, "FileNotFoundError") {
		t.Errorf("removing the flight log by its old path should fail (it is not mounted there):\n%s", stdout)
	}
	if !strings.Contains(stdout, "taken") {
		t.Errorf("a second open must be refused as taken:\n%s", stdout)
	}

	logData, err := os.ReadFile(filepath.Join(sessions, sid, "flight.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	var decisions []string
	for _, line := range strings.Split(strings.TrimSpace(string(logData)), "\n") {
		if strings.Contains(line, `"tool":"sink"`) {
			decisions = append(decisions, mustField(t, line, "decision"))
		} else if strings.Contains(line, `"tool":"exec"`) {
			decisions = append(decisions, "event")
			if !strings.Contains(line, `"session":"`+sid+`"`) || strings.Contains(line, "forged") {
				t.Errorf("the event line must carry the sink's own session and role, not the forged ones: %s", line)
			}
		}
	}
	want := []string{"listening", "stream_opened", "event", "stream_refused", "stream_closed"}
	if strings.Join(decisions, ",") != strings.Join(want, ",") {
		t.Errorf("flight log order = %v, want %v:\n%s", decisions, want, logData)
	}
}

// mustField extracts a top-level string field's value from a JSON line by
// a cheap scan — the flight log's own shape (recorder.Event), not a
// general JSON reader, for a test that wants only one field.
func mustField(t *testing.T, line, field string) string {
	t.Helper()
	key := `"` + field + `":"`
	i := strings.Index(line, key)
	if i < 0 {
		t.Fatalf("no %q field in %s", field, line)
	}
	rest := line[i+len(key):]
	j := strings.Index(rest, `"`)
	if j < 0 {
		t.Fatalf("unterminated %q field in %s", field, line)
	}
	return rest[:j]
}
