package main

import (
	"bytes"
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
	// Plan is shown, with clean env and the worktree mount.
	for _, want := range []string{
		"podman run", "--network none",
		filepath.Join(sessions, "S-test", "worktree") + ":/work:rw",
		"HOME=/sessions/S-test", "mcpServers", "--disallowedTools Bash",
	} {
		if !strings.Contains(stdout, want) {
			t.Errorf("dry-run missing %q", want)
		}
	}
	// The MCP config was written host-side.
	cfg := filepath.Join(sessions, "S-test", "mcp.json")
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
		"--session", "S-rt", "--proxy-bin", fakeProxy, "--sessions", sessions,
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
