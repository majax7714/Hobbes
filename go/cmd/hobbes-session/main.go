// Command hobbes-session launches an agent session in a rootless Podman
// sandbox (M4, ADR-018): a fresh git worktree, the merged policy mapped to
// mounts, a clean environment, and Claude Code wired to the hobbes-proxy
// MCP server. It creates the worktree, writes the MCP config, runs
// `podman run`, and removes the worktree on exit.
//
// Usage:
//
//	hobbes-session start --repo DIR --role ROLE [--task "..."] [flags]
//	  [--dry-run] [--image IMG] [--network NET] [--claude-cred]
//	  [-- CMD ARGS...]   # override the in-container command (exit check)
//
// Exit codes: the session command's code · 1 setup error · 2 usage.
package main

import (
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/majax7714/Hobbes/go/internal/sandbox"
)

const (
	exitError = 1
	exitUsage = 2
)

const usage = `usage: hobbes-session start --repo DIR --role ROLE [flags] [-- CMD...]

Launch an agent session in a rootless Podman sandbox: a fresh git worktree
mounted rw, the hobbes-proxy MCP server enforcing policy, and a clean
environment. Without a trailing command, runs Claude Code as the session's
implementer.

flags:
  --repo DIR       repo to spawn a session from (required)
  --role ROLE      session role (required)
  --task TEXT      the implementer's prompt (default Claude Code command)
  --model NAME     the model: pins Claude Code's, or names the one the
                   agent runtime asks the endpoint for (ADR-055/056)
  --runtime FILE   run the owned agent loop (ADR-056) instead of Claude
                   Code: FILE is copied into the session dir and run with
                   the image's python3; needs --llm-base-url and --model.
                   $HOBBES_LLM_API_KEY on the host, if set, reaches the
                   session as the endpoint's bearer token (C-41)
  --llm-base-url U OpenAI-compatible API root the runtime talks to
  --escalation-timeout D  how long an escalated command parks before it
                   expires to deny (e.g. 5s); 0 = proxy default (30m). A
                   solo/benchmark run wants this short — no human approves
  --ref REF        commit/branch the session worktree checks out (default HEAD)
  --session ID     session id (default: generated)
  --commit-on-exit commit whatever the session left uncommitted (.hobbes/
                   excluded) before the harvest — the benchmark path's
                   practice (ADR-058); the commit names itself
  --task-file F    the prompt from a file (exclusive with --task; a long
                   brief exceeds the argv limit)
  --image IMG      session image (default hobbes-session:local)
  --path PATH      in-container PATH (default /usr/local/bin:/usr/bin:/bin)
  --env K=V        extra in-container env var (repeatable; printed by --dry-run)
  --pre CMD        host-authored shell command run before the session
                   command in the same container (an environment binding,
                   ADR-058); not the agent's, not policed
  --runtime-python P  interpreter for --runtime (default: the image's python3)
  --max-turns N    turn budget for --runtime (default: the loop's own)
  --max-tokens N   completion cap per turn for --runtime (default: the loop's own)
  --loop-arg A     a flag forwarded verbatim to --runtime's loop (repeatable, e.g.
                   --loop-arg=--temperature=1.0; ADR-074)
  --network NET    podman --network (default none)
  --box FILE       box policy (default ~/.hobbes/box.policy if present)
  --proxy-bin FILE static hobbes-proxy binary to mount (default: next to me)
  --sessions DIR   session-state root (default ~/.hobbes/sessions)
  --claude-cred    mount ~/.claude ro (needed for a live Claude Code run)
  --agent-dir DIR  derived agent dir (ADR-054), mounted ro at /agent: its
                   policy.yaml is the chain's agent level, its context.json
                   the manifest knowledge queries are judged against
  --dry-run        print the podman argv and MCP config, run nothing
  -- CMD...        run CMD in the sandbox instead of Claude Code
`

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

func run(args []string, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		fmt.Fprint(stderr, usage)
		return exitUsage
	}
	switch args[0] {
	case "start":
		return runStart(args[1:], stdout, stderr)
	case "help", "-h", "--help":
		fmt.Fprint(stderr, usage)
		return 0
	default:
		fmt.Fprintf(stderr, "hobbes-session: unknown command %q\n\n%s", args[0], usage)
		return exitUsage
	}
}

// options holds parsed start flags plus the trailing command override.
type options struct {
	repo, role, task, session, ref string
	taskFile                       string
	agentDir, model                string
	runtime, llmBaseURL            string
	escalation                     time.Duration
	image, network, box            string
	path, pre, runtimePython       string
	maxTurns, maxTokens            int
	loopArgs                       multiFlag
	env                            multiFlag
	proxyBin, sessions             string
	claudeCred, dryRun             bool
	commitOnExit                   bool
	command                        []string
}

// multiFlag collects a repeatable string flag.
type multiFlag []string

func (m *multiFlag) String() string     { return strings.Join(*m, ",") }
func (m *multiFlag) Set(v string) error { *m = append(*m, v); return nil }

func runStart(args []string, stdout, stderr io.Writer) int {
	opt, code := parseStart(args, stderr)
	if code != 0 {
		return code
	}

	plan, worktree, startRef, cleanup, err := setupWithStart(opt)
	if err != nil {
		fmt.Fprintf(stderr, "hobbes-session: %v\n", err)
		return exitError
	}
	defer cleanup()
	// The clone is disposable; the session's commits are not. Whatever
	// lands on the session branch is fetched into the canonical repo
	// before the clone goes (ADR-054) — a dry run has nothing to harvest
	// and says so.
	defer harvest(opt.repo, worktree, "hobbes/"+opt.session, startRef, stderr)

	if opt.dryRun {
		fmt.Fprint(stdout, plan.DryRun())
		return 0
	}

	fmt.Fprintf(stderr, "hobbes-session: %s (role %s)\n  worktree %s\n  flight log %s\n",
		plan.SessionID(), opt.role, worktree,
		filepath.Join(opt.sessions, plan.SessionID(), "flight.jsonl"))

	cmd := exec.Command("podman", plan.PodmanArgs()...)
	cmd.Stdin, cmd.Stdout, cmd.Stderr = os.Stdin, stdout, stderr
	err = cmd.Run()
	if opt.commitOnExit {
		// The benchmark path (ADR-058): a solo session's edits that it
		// never committed would otherwise vanish with the clone. The
		// commit is the wrapper's, named as such, and never includes
		// .hobbes/ (P1: derived is not committed).
		commitLeftovers(worktree, stderr)
	}
	if err != nil {
		if ee, ok := err.(*exec.ExitError); ok {
			return ee.ExitCode()
		}
		fmt.Fprintf(stderr, "hobbes-session: podman: %v\n", err)
		return exitError
	}
	return 0
}

// setup creates the worktree and session dir, writes the MCP config, and
// returns the plan plus a teardown that removes the worktree.
func setup(opt options) (*sandbox.Plan, string, func(), error) {
	plan, worktree, _, cleanup, err := setupWithStart(opt)
	return plan, worktree, cleanup, err
}

// setupWithStart is setup plus the commit the session branch started at,
// which the harvest after the run counts from (ADR-054).
func setupWithStart(opt options) (*sandbox.Plan, string, string, func(), error) {
	var startRef string
	noop := func() {}

	repo, err := filepath.Abs(opt.repo)
	if err != nil {
		return nil, "", "", noop, err
	}
	if info, err := os.Stat(filepath.Join(repo, ".git")); err != nil || !info.IsDir() {
		return nil, "", "", noop, fmt.Errorf("%s is not a git repo (no .git dir)", repo)
	}

	sessionDir := filepath.Join(opt.sessions, opt.session)
	worktree := filepath.Join(sessionDir, "worktree")
	if err := os.MkdirAll(sessionDir, 0o700); err != nil {
		return nil, "", "", noop, err
	}

	// A fresh, self-contained local clone on a session branch (§6:
	// sessions never share a tree). A clone rather than a linked worktree
	// because the container mounts only /work — a worktree's .git points
	// back into the canonical repo's gitdir, which is deliberately not
	// mounted; a `--local` clone copies the object store into the session
	// dir and so needs no path outside /work, which is what lets git work
	// inside the sandbox while the canonical repo stays unreachable from
	// the container (ADR-018).
	//
	// `--no-hardlinks` because a local clone hardlinks objects by default,
	// and a hardlink cannot cross a filesystem: with the repo and the
	// sessions dir (under $HOME) on different devices, the clone died with
	// "Invalid cross-device link", which names the symptom and not the
	// cause. The cost is a real copy of the object store; the benefit is
	// that a repo on a mounted volume or a ramdisk checkout works at all.
	if out, err := gitOut(repo, "clone", "--local", "--no-hardlinks", "--quiet", repo, worktree); err != nil {
		return nil, "", "", noop, fmt.Errorf("git clone: %v: %s", err, out)
	}
	// --ref pins the session's tree to a specific commit — a soft-verdict
	// reviewer (V2.M6) must read the *head of the range under review*,
	// which is not necessarily the repo's HEAD.
	checkout := []string{"checkout", "-q", "-b", "hobbes/" + opt.session}
	if opt.ref != "" {
		checkout = append(checkout, opt.ref)
	}
	if out, err := gitOut(worktree, checkout...); err != nil {
		os.RemoveAll(worktree)
		return nil, "", "", noop, fmt.Errorf("git checkout: %v: %s", err, out)
	}
	// A clone carries no identity, and the sandbox has no global git
	// config, so a session's `git commit` died with exit 128 — found
	// on the first benchmark run (ADR-058). The canonical repo's
	// identity is copied when it has one; otherwise the session
	// commits as itself.
	seedIdentity(repo, worktree)
	// The branch's start point, for the harvest after the run (ADR-054):
	// commits past it are the session's work and must outlive the clone.
	start, err := gitOut(worktree, "rev-parse", "HEAD")
	if err != nil {
		os.RemoveAll(worktree)
		return nil, "", "", noop, fmt.Errorf("git rev-parse: %v: %s", err, start)
	}
	startRef = strings.TrimSpace(start)
	// Seed the session's knowledge layer: derived artifacts are gitignored
	// (ADR-012), so the clone lacks them; copy the box's current ingest in
	// so the knowledge tools (ADR-017) have data to answer from.
	seedDerived(repo, worktree)
	cleanup := func() {
		// Only the clone is disposable; the flight log and escalation
		// records under sessionDir are the audit trail and stay.
		os.RemoveAll(worktree)
	}

	plan, err := sandbox.NewPlan(sandbox.Config{
		SessionID:     opt.session,
		Role:          opt.role,
		Image:         opt.image,
		Task:          opt.task,
		Model:         opt.model,
		Runtime:       runtimePath(opt.runtime, opt.session),
		LLMBaseURL:    opt.llmBaseURL,
		LLMKey:        os.Getenv("HOBBES_LLM_API_KEY"),
		RuntimePython: opt.runtimePython,
		MaxTurns:      opt.maxTurns,
		MaxTokens:     opt.maxTokens,
		LoopArgs:      []string(opt.loopArgs),
		Path:          opt.path,
		Env:           []string(opt.env),
		Pre:           opt.pre,
		Escalation:    opt.escalation,
		Network:       opt.network,
		HostWorktree:  worktree,
		HostSessions:  opt.sessions,
		HostProxyBin:  opt.proxyBin,
		HostBoxPath:   opt.box,
		HostClaude:    claudeMount(opt.claudeCred),
		HostDerived:   derivedMount(opt.repo),
		HostAgentDir:  opt.agentDir,
		Command:       opt.command,
	})
	if err != nil {
		cleanup()
		return nil, "", "", noop, err
	}

	if err := os.WriteFile(plan.MCPConfigHostPath(), []byte(plan.MCPConfig()), 0o600); err != nil {
		cleanup()
		return nil, "", "", noop, err
	}
	if opt.runtime != "" {
		// The runtime and the brief travel through the session dir
		// (ADR-056): the loop file the host tested is the one the
		// sandbox runs, and the brief is a file rather than an argv
		// so a long one cannot hit the arg limit.
		src, err := os.ReadFile(opt.runtime)
		if err != nil {
			cleanup()
			return nil, "", "", noop, fmt.Errorf("--runtime: %v", err)
		}
		if err := os.WriteFile(filepath.Join(sessionDir, "agent.py"), src, 0o600); err != nil {
			cleanup()
			return nil, "", "", noop, err
		}
		if err := os.WriteFile(filepath.Join(sessionDir, "brief.md"), []byte(opt.task), 0o600); err != nil {
			cleanup()
			return nil, "", "", noop, err
		}
	}
	return plan, worktree, startRef, cleanup, nil
}

// harvest fetches the session branch from the clone into the canonical
// repo when it carries commits past startRef, and reports either way. The
// branch lands under the same name (hobbes/<session>); publishing it
// stays the human's (the repo policy denies push).
func harvest(repo, worktree, branch, startRef string, stderr io.Writer) {
	count, err := gitOut(worktree, "rev-list", "--count", startRef+".."+branch)
	if err != nil {
		fmt.Fprintf(stderr, "hobbes-session: harvest: %v: %s\n", err, count)
		return
	}
	n := strings.TrimSpace(count)
	if n == "0" {
		fmt.Fprintln(stderr, "hobbes-session: no commits to harvest")
		return
	}
	if out, err := gitOut(repo, "fetch", "--quiet", worktree, branch+":"+branch); err != nil {
		fmt.Fprintf(stderr, "hobbes-session: harvest: git fetch: %v: %s\n", err, out)
		return
	}
	fmt.Fprintf(stderr, "hobbes-session: branch %s harvested (%s commits)\n", branch, n)
}

func gitOut(repo string, args ...string) (string, error) {
	out, err := exec.Command("git", append([]string{"-C", repo}, args...)...).CombinedOutput()
	return string(out), err
}

// seedDerived copies the source repo's derived artifacts into the fresh
// clone, which lacks them (they are gitignored, ADR-012), so the session's
// knowledge tools have data. Best effort: a session with no ingest simply
// gets "run hobbes ingest" answers.
func seedDerived(repo, worktree string) {
	src := filepath.Join(repo, ".hobbes", "derived")
	if info, err := os.Stat(src); err != nil || !info.IsDir() {
		return
	}
	dst := filepath.Join(worktree, ".hobbes", "derived")
	_ = os.MkdirAll(dst, 0o755)
	entries, err := os.ReadDir(src)
	if err != nil {
		return
	}
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		data, err := os.ReadFile(filepath.Join(src, e.Name()))
		if err != nil {
			continue
		}
		_ = os.WriteFile(filepath.Join(dst, e.Name()), data, 0o644)
	}
}

// runtimePath is the in-container path of the copied agent loop
// (ADR-056) — the session dir is mounted at SessionsRoot, so the copy
// the wrapper writes host-side is visible there — or "" when Claude
// Code runs.
func runtimePath(runtime, session string) string {
	if runtime == "" {
		return ""
	}
	return sandbox.SessionsRoot + "/" + session + "/agent.py"
}

// commitLeftovers commits whatever the session left uncommitted in the
// worktree, .hobbes/ excluded, and says how many files. A no-op on a
// clean tree. The line it prints is what the orchestrator reads.
func commitLeftovers(worktree string, stderr io.Writer) {
	if out, err := gitOut(worktree, "add", "-A", "--", ".", ":!.hobbes"); err != nil {
		fmt.Fprintf(stderr, "hobbes-session: commit-on-exit: git add: %v: %s\n", err, out)
		return
	}
	staged, err := gitOut(worktree, "diff", "--cached", "--name-only")
	if err != nil || strings.TrimSpace(staged) == "" {
		return
	}
	n := len(strings.Split(strings.TrimSpace(staged), "\n"))
	msg := fmt.Sprintf("hobbes-session: uncommitted work at session end (%d files)", n)
	if out, err := gitOut(worktree, "commit", "-q", "-m", msg); err != nil {
		fmt.Fprintf(stderr, "hobbes-session: commit-on-exit: git commit: %v: %s\n", err, out)
		return
	}
	fmt.Fprintf(stderr, "hobbes-session: committed %d uncommitted file(s) at exit\n", n)
}

// seedIdentity gives the session clone a commit identity: the canonical
// repo's local one when set, else a named session default. Without it
// every `git commit` inside the sandbox fails (no global config there).
func seedIdentity(repo, worktree string) {
	for key, def := range map[string]string{
		"user.name":  "hobbes-session",
		"user.email": "session@hobbes.local",
	} {
		val := def
		if out, err := gitOut(repo, "config", "--get", key); err == nil && strings.TrimSpace(out) != "" {
			val = strings.TrimSpace(out)
		}
		_, _ = gitOut(worktree, "config", key, val)
	}
}

// derivedMount is the host repo's .hobbes/derived when it exists. A
// session's worktree is a fresh checkout and derived/ is gitignored, so
// without this the knowledge tools have nothing to read and a reviewer
// starts blind — the opposite of §6's "oriented via MCP, not cold grep".
// Absent artifacts are not an error: the tools already answer "run
// hobbes ingest".
func derivedMount(repo string) string {
	path := filepath.Join(repo, ".hobbes", "derived")
	if info, err := os.Stat(path); err != nil || !info.IsDir() {
		return ""
	}
	abs, err := filepath.Abs(path)
	if err != nil {
		return ""
	}
	return abs
}

func claudeMount(want bool) string {
	if !want {
		return ""
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}
	return filepath.Join(home, ".claude")
}

// parseStart handles flags and the "--" command override. Returns a
// non-zero code (and prints) on any flag trouble.
func parseStart(args []string, stderr io.Writer) (options, int) {
	var opt options
	// Split off a trailing "-- CMD..." before flag parsing.
	flags := args
	for i, a := range args {
		if a == "--" {
			flags = args[:i]
			opt.command = args[i+1:]
			break
		}
	}

	home, _ := os.UserHomeDir()
	fs := newFlagSet(stderr)
	fs.StringVar(&opt.repo, "repo", "", "")
	fs.StringVar(&opt.role, "role", "", "")
	fs.StringVar(&opt.task, "task", "", "")
	fs.StringVar(&opt.taskFile, "task-file", "", "")
	fs.StringVar(&opt.agentDir, "agent-dir", "", "")
	fs.StringVar(&opt.model, "model", "", "")
	fs.StringVar(&opt.runtime, "runtime", "", "")
	fs.StringVar(&opt.llmBaseURL, "llm-base-url", "", "")
	fs.DurationVar(&opt.escalation, "escalation-timeout", 0, "")
	fs.StringVar(&opt.ref, "ref", "", "")
	fs.StringVar(&opt.session, "session", "", "")
	fs.StringVar(&opt.image, "image", "", "")
	fs.StringVar(&opt.path, "path", "", "")
	fs.StringVar(&opt.pre, "pre", "", "")
	fs.StringVar(&opt.runtimePython, "runtime-python", "", "")
	fs.IntVar(&opt.maxTurns, "max-turns", 0, "")
	fs.IntVar(&opt.maxTokens, "max-tokens", 0, "")
	fs.Var(&opt.env, "env", "")
	fs.Var(&opt.loopArgs, "loop-arg", "")
	fs.StringVar(&opt.network, "network", "", "")
	fs.StringVar(&opt.box, "box", "", "")
	fs.StringVar(&opt.proxyBin, "proxy-bin", "", "")
	fs.StringVar(&opt.sessions, "sessions", "", "")
	fs.BoolVar(&opt.claudeCred, "claude-cred", false, "")
	fs.BoolVar(&opt.dryRun, "dry-run", false, "")
	fs.BoolVar(&opt.commitOnExit, "commit-on-exit", false, "")
	if err := fs.Parse(flags); err != nil {
		return opt, exitUsage
	}
	if opt.repo == "" || opt.role == "" {
		fmt.Fprintf(stderr, "hobbes-session start: --repo and --role are required\n\n%s", usage)
		return opt, exitUsage
	}
	if opt.taskFile != "" {
		// A brief travels as a file (ADR-058): a unit's standing context
		// can exceed the kernel's single-argument limit, and did.
		if opt.task != "" {
			fmt.Fprintln(stderr, "hobbes-session start: --task and --task-file are exclusive")
			return opt, exitUsage
		}
		body, err := os.ReadFile(opt.taskFile)
		if err != nil {
			fmt.Fprintf(stderr, "hobbes-session start: --task-file: %v\n", err)
			return opt, exitError
		}
		opt.task = string(body)
	}

	if opt.sessions == "" {
		if home == "" {
			fmt.Fprintln(stderr, "hobbes-session start: no home dir; pass --sessions")
			return opt, exitError
		}
		opt.sessions = filepath.Join(home, ".hobbes", "sessions")
	}
	if opt.session == "" {
		id, err := sandbox.NewID(time.Now())
		if err != nil {
			fmt.Fprintf(stderr, "hobbes-session start: %v\n", err)
			return opt, exitError
		}
		opt.session = id
	}
	if opt.box == "" && home != "" {
		if def := filepath.Join(home, ".hobbes", "box.policy"); fileExists(def) {
			opt.box = def
		}
	}
	if opt.agentDir != "" {
		abs, err := filepath.Abs(opt.agentDir)
		if err != nil {
			fmt.Fprintf(stderr, "hobbes-session start: %v\n", err)
			return opt, exitError
		}
		if info, err := os.Stat(abs); err != nil || !info.IsDir() {
			fmt.Fprintf(stderr, "hobbes-session start: agent dir %q is not a directory\n", opt.agentDir)
			return opt, exitError
		}
		opt.agentDir = abs
	}
	if opt.proxyBin == "" {
		opt.proxyBin = defaultProxyBin()
	}
	if opt.proxyBin == "" || !fileExists(opt.proxyBin) {
		fmt.Fprintf(stderr, "hobbes-session start: proxy binary %q not found; pass --proxy-bin\n", opt.proxyBin)
		return opt, exitError
	}
	return opt, 0
}

// defaultProxyBin looks for hobbes-proxy next to this binary.
func defaultProxyBin() string {
	self, err := os.Executable()
	if err != nil {
		return ""
	}
	cand := filepath.Join(filepath.Dir(self), "hobbes-proxy")
	if fileExists(cand) {
		return cand
	}
	return ""
}

func fileExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && !info.IsDir()
}

// newFlagSet builds the start flag set (help text lives in the usage
// string, so the flags themselves stay terse).
func newFlagSet(stderr io.Writer) *flag.FlagSet {
	fs := flag.NewFlagSet("start", flag.ContinueOnError)
	fs.SetOutput(stderr)
	return fs
}
