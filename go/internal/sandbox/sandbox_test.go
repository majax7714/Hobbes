package sandbox

import (
	"encoding/json"
	"regexp"
	"strings"
	"testing"
	"time"
)

func baseConfig() Config {
	return Config{
		SessionID:    "S-20260811T120000Z-abcd",
		Role:         "implementer",
		HostWorktree: "/home/u/.hobbes/sessions/S-x/worktree",
		HostSessions: "/home/u/.hobbes/sessions",
		HostProxyBin: "/home/u/hobbes/go/bin/hobbes-proxy",
	}
}

// planFor builds a plan for one role.
func planFor(t *testing.T, role string) *Plan {
	t.Helper()
	cfg := baseConfig()
	cfg.Role = role
	plan, err := NewPlan(cfg)
	if err != nil {
		t.Fatal(err)
	}
	return plan
}

func TestNewPlanDefaults(t *testing.T) {
	p, err := NewPlan(baseConfig())
	if err != nil {
		t.Fatal(err)
	}
	if p.cfg.Image != "hobbes-session:local" || p.cfg.Network != "none" {
		t.Errorf("defaults wrong: image=%q network=%q", p.cfg.Image, p.cfg.Network)
	}
}

func TestNewPlanRequiresAbsoluteHostPaths(t *testing.T) {
	cfg := baseConfig()
	cfg.HostWorktree = "relative/path"
	if _, err := NewPlan(cfg); err == nil {
		t.Error("relative worktree must be rejected")
	}
	cfg = baseConfig()
	cfg.Role = ""
	if _, err := NewPlan(cfg); err == nil {
		t.Error("missing role must be rejected")
	}
	cfg = baseConfig()
	cfg.SessionID = ""
	if _, err := NewPlan(cfg); err == nil {
		t.Error("missing session id must be rejected")
	}
}

func TestPodmanArgsCleanEnvAndMounts(t *testing.T) {
	p, _ := NewPlan(baseConfig())
	args := p.PodmanArgs()
	joined := strings.Join(args, " ")

	// Clean env: exactly HOME and PATH, nothing host-derived.
	envs := []string{}
	for i, a := range args {
		if a == "--env" && i+1 < len(args) {
			envs = append(envs, args[i+1])
		}
	}
	if len(envs) != 2 {
		t.Fatalf("want exactly 2 env vars (HOME, PATH), got %v", envs)
	}
	if envs[0] != "HOME=/sessions/S-20260811T120000Z-abcd" {
		t.Errorf("HOME = %q", envs[0])
	}
	if !strings.HasPrefix(envs[1], "PATH=") {
		t.Errorf("second env should be PATH, got %q", envs[1])
	}

	for _, want := range []string{
		"--network none",
		"--workdir /work",
		"/home/u/.hobbes/sessions/S-x/worktree:/work:rw",
		"/home/u/.hobbes/sessions:/sessions:rw",
		"/home/u/hobbes/go/bin/hobbes-proxy:/usr/local/bin/hobbes-proxy:ro",
		"hobbes-session:local",
	} {
		if !strings.Contains(joined, want) {
			t.Errorf("podman args missing %q in:\n%s", want, joined)
		}
	}
}

func TestBoxAndClaudeMountsAreOptional(t *testing.T) {
	cfg := baseConfig()
	p, _ := NewPlan(cfg)
	if strings.Contains(strings.Join(p.PodmanArgs(), " "), "/policy/box.policy") {
		t.Error("box mount present without a host box policy")
	}
	if strings.Contains(strings.Join(p.PodmanArgs(), " "), ".claude") {
		t.Error("claude credential mounted by default — must be opt-in")
	}

	cfg.HostBoxPath = "/home/u/.hobbes/box.policy"
	cfg.HostClaude = "/home/u/.claude"
	p, _ = NewPlan(cfg)
	joined := strings.Join(p.PodmanArgs(), " ")
	if !strings.Contains(joined, "/home/u/.hobbes/box.policy:/policy/box.policy:ro") {
		t.Error("box policy not mounted ro when present")
	}
	if !strings.Contains(joined, "/home/u/.claude:/root/.claude:ro") {
		t.Error("claude credential not mounted ro when requested")
	}
}

func TestMCPConfigWiresProxyToWorktree(t *testing.T) {
	cfg := baseConfig()
	cfg.HostBoxPath = "/home/u/.hobbes/box.policy"
	p, _ := NewPlan(cfg)

	var parsed struct {
		MCPServers map[string]struct {
			Command string   `json:"command"`
			Args    []string `json:"args"`
		} `json:"mcpServers"`
	}
	if err := json.Unmarshal([]byte(p.MCPConfig()), &parsed); err != nil {
		t.Fatal(err)
	}
	h, ok := parsed.MCPServers["hobbes"]
	if !ok {
		t.Fatal("no hobbes server in MCP config")
	}
	if h.Command != "/usr/local/bin/hobbes-proxy" {
		t.Errorf("command = %q", h.Command)
	}
	a := strings.Join(h.Args, " ")
	for _, want := range []string{
		"serve", "--repo /work", "--role implementer",
		"--session S-20260811T120000Z-abcd", "--log-dir /sessions",
		"--box /policy/box.policy",
	} {
		if !strings.Contains(a, want) {
			t.Errorf("proxy args missing %q in %q", want, a)
		}
	}
}

func TestDefaultCommandForbidsRawShell(t *testing.T) {
	p, _ := NewPlan(baseConfig())
	cmd := strings.Join(p.DefaultCommand(), " ")
	if !strings.Contains(cmd, "--disallowedTools Bash") {
		t.Error("native layer must forbid Bash so exec routes through the proxy")
	}
	if !strings.Contains(cmd, "mcp__hobbes__exec") {
		t.Error("the hobbes exec tool must be allowed")
	}
	if !strings.Contains(cmd, "-p") {
		t.Error("implementer runs non-interactively (-p)")
	}
}

func TestCommandOverrideUsedForExitCheck(t *testing.T) {
	cfg := baseConfig()
	cfg.Command = []string{"python3", "/sessions/driver.py"}
	p, _ := NewPlan(cfg)
	args := p.PodmanArgs()
	if args[len(args)-2] != "python3" || args[len(args)-1] != "/sessions/driver.py" {
		t.Errorf("override command not used: %v", args[len(args)-3:])
	}
}

func TestNewIDShape(t *testing.T) {
	id, err := NewID(time.Date(2026, 8, 11, 12, 0, 0, 0, time.UTC))
	if err != nil {
		t.Fatal(err)
	}
	if !regexp.MustCompile(`^S-20260811T120000Z-[0-9a-f]{4}$`).MatchString(id) {
		t.Errorf("id = %q", id)
	}
}

func TestDryRunShowsPlanAndConfig(t *testing.T) {
	p, _ := NewPlan(baseConfig())
	out := p.DryRun()
	if !strings.Contains(out, "podman run") || !strings.Contains(out, "mcpServers") {
		t.Errorf("dry run should show podman argv and MCP config:\n%s", out)
	}
}

func TestReviewerWorktreeIsReadOnly(t *testing.T) {
	// §6: a reviewer gets read-only mounts. §5.2 puts the OS sandbox
	// first among the enforcement tiers, so this is a mount flag rather
	// than a policy rule an agent could argue with.
	plan := planFor(t, "reviewer")
	if plan.WorktreeMode() != "O" {
		t.Fatalf("worktree mode = %q, want O (overlay, ADR-060)", plan.WorktreeMode())
	}
	args := strings.Join(plan.PodmanArgs(), " ")
	// An overlay: the container may write, the host worktree never
	// changes. Podman rejects "O,z", so the spec carries no relabel.
	if !strings.Contains(args, ":"+WorkDir+":O ") {
		t.Errorf("reviewer worktree is not an overlay mount:\n%s", args)
	}
	if strings.Contains(args, WorkDir+":rw") || strings.Contains(args, WorkDir+":O,z") {
		t.Errorf("reviewer worktree mount is wrong:\n%s", args)
	}
	// The flight recorder and escalation queue still have to be
	// writable, or a read-only session could not be audited.
	if !strings.Contains(args, SessionsRoot+":rw,z") {
		t.Errorf("session state must stay writable:\n%s", args)
	}
}

func TestImplementerWorktreeStaysWritable(t *testing.T) {
	plan := planFor(t, "implementer")
	if plan.WorktreeMode() != "rw" {
		t.Fatalf("worktree mode = %q, want rw", plan.WorktreeMode())
	}
	if !strings.Contains(strings.Join(plan.PodmanArgs(), " "), WorkDir+":rw,z") {
		t.Error("implementer worktree must be writable")
	}
}

func TestAnUnknownRoleIsWritableNotSilentlyReadOnly(t *testing.T) {
	// Failing closed here would look like a broken session rather than a
	// refused one; roles gain read-only status deliberately.
	if planFor(t, "cartographer").WorktreeMode() != "rw" {
		t.Error("only listed roles are read-only")
	}
}

func TestReviewerGetsNoWriteTools(t *testing.T) {
	tools := strings.Join(planFor(t, "reviewer").allowedTools(), ",")
	for _, banned := range []string{"Edit", "Write", "mcp__hobbes__exec"} {
		if strings.Contains(tools, banned) {
			t.Errorf("reviewer must not be offered %s: %s", banned, tools)
		}
	}
	for _, want := range []string{"Read", "mcp__hobbes__list_invariants"} {
		if !strings.Contains(tools, want) {
			t.Errorf("reviewer needs %s: %s", want, tools)
		}
	}
}

func TestImplementerKeepsExecAndEdit(t *testing.T) {
	tools := strings.Join(planFor(t, "implementer").allowedTools(), ",")
	for _, want := range []string{"mcp__hobbes__exec", "Edit", "Write"} {
		if !strings.Contains(tools, want) {
			t.Errorf("implementer needs %s: %s", want, tools)
		}
	}
}

func TestEveryRoleGetsTheKnowledgeTools(t *testing.T) {
	// §6: sessions start oriented via MCP, not cold grep.
	for _, role := range []string{"implementer", "reviewer"} {
		tools := strings.Join(planFor(t, role).allowedTools(), ",")
		for _, want := range knowledgeTools {
			if !strings.Contains(tools, want) {
				t.Errorf("%s missing %s", role, want)
			}
		}
	}
}

func TestReviewerNeedsNoEditPermissionMode(t *testing.T) {
	cmd := strings.Join(planFor(t, "reviewer").DefaultCommand(), " ")
	if strings.Contains(cmd, "acceptEdits") {
		t.Errorf("a read-only role should not be accepting edits: %s", cmd)
	}
}

func TestDerivedIsMountedReadOnlyWhenPresent(t *testing.T) {
	// A fresh worktree has no derived/ (it is gitignored), so without
	// this mount the knowledge tools answer nothing and a session starts
	// blind — the opposite of §6's "oriented via MCP, not cold grep".
	cfg := baseConfig()
	cfg.HostDerived = "/home/u/hobbes/.hobbes/derived"
	plan, err := NewPlan(cfg)
	if err != nil {
		t.Fatal(err)
	}
	args := strings.Join(plan.PodmanArgs(), " ")
	if !strings.Contains(args, cfg.HostDerived+":"+DerivedDir+":ro,z") {
		t.Errorf("derived not mounted ro:\n%s", args)
	}
}

func TestDerivedIsReadOnlyEvenForAnImplementer(t *testing.T) {
	// A session that could edit the derived layer could edit the map it
	// is judged against.
	for _, role := range []string{"implementer", "reviewer"} {
		cfg := baseConfig()
		cfg.Role = role
		cfg.HostDerived = "/home/u/hobbes/.hobbes/derived"
		plan, _ := NewPlan(cfg)
		if !strings.Contains(strings.Join(plan.PodmanArgs(), " "), DerivedDir+":ro,z") {
			t.Errorf("%s must not get a writable derived layer", role)
		}
	}
}

func TestNoDerivedMountWhenTheRepoHasNone(t *testing.T) {
	plan, _ := NewPlan(baseConfig())
	if strings.Contains(strings.Join(plan.PodmanArgs(), " "), DerivedDir) {
		t.Error("an un-ingested repo should mount no derived dir")
	}
}

func TestAgentDirIsMountedReadOnlyAndHandedToTheProxy(t *testing.T) {
	cfg := baseConfig()
	cfg.HostAgentDir = "/home/u/repo/.hobbes/plans/abc/agents/U1"
	p, err := NewPlan(cfg)
	if err != nil {
		t.Fatal(err)
	}
	argv := strings.Join(p.PodmanArgs(), " ")
	if !strings.Contains(argv, cfg.HostAgentDir+":"+AgentDir+":ro,z") {
		t.Errorf("agent dir not mounted ro: %s", argv)
	}
	if !strings.Contains(p.MCPConfig(), `"--agent-dir"`) || !strings.Contains(p.MCPConfig(), `"`+AgentDir+`"`) {
		t.Errorf("proxy not told about the agent dir: %s", p.MCPConfig())
	}
	if !strings.Contains(p.DryRun(), "agent:    "+cfg.HostAgentDir) {
		t.Errorf("dry run omits the agent dir")
	}
}

func TestNoAgentDirMeansNoMountAndNoFlag(t *testing.T) {
	p := planFor(t, "implementer")
	if strings.Contains(strings.Join(p.PodmanArgs(), " "), AgentDir) || strings.Contains(p.MCPConfig(), "--agent-dir") {
		t.Errorf("agent dir plumbing present without one configured")
	}
}

func TestVerifierIsReadOnlyLikeAReviewer(t *testing.T) {
	p := planFor(t, "verifier")
	if p.WorktreeMode() != "O" {
		t.Errorf("verifier worktree mode = %s, want O", p.WorktreeMode())
	}
	tools := strings.Join(p.allowedTools(), ",")
	if strings.Contains(tools, "Edit") || strings.Contains(tools, "mcp__hobbes__exec") {
		t.Errorf("verifier got write tools: %s", tools)
	}
}

// Harness restructure, phase 1: a planner is a read-only role whose job
// is a handoff, and every read-only role runs python without bytecode
// writes so its tests can run on the ro mount.
func TestPlannerIsReadOnlyAndReadOnlyRolesSkipBytecode(t *testing.T) {
	p := planFor(t, "planner")
	if p.WorktreeMode() != "O" {
		t.Errorf("planner worktree mode = %s, want O", p.WorktreeMode())
	}
	tools := strings.Join(p.allowedTools(), ",")
	if strings.Contains(tools, "Edit") || strings.Contains(tools, "mcp__hobbes__exec") || !strings.Contains(tools, "mcp__hobbes__reflect") {
		t.Errorf("planner tools = %s", tools)
	}
	for _, role := range []string{"planner", "verifier", "reviewer"} {
		if args := strings.Join(planFor(t, role).PodmanArgs(), " "); !strings.Contains(args, "--env PYTHONDONTWRITEBYTECODE=1") {
			t.Errorf("%s: no PYTHONDONTWRITEBYTECODE in %s", role, args)
		}
	}
	if args := strings.Join(planFor(t, "implementer").PodmanArgs(), " "); strings.Contains(args, "PYTHONDONTWRITEBYTECODE") {
		t.Errorf("implementer got the read-only env: %s", args)
	}
}

// ADR-055: the harness arm runs a model ladder and meters its sessions,
// so the default command pins the model when asked and always asks for
// the JSON result envelope (usage, cost, turns, wall time).
func TestDefaultCommandPinsModelAndEmitsJSONEnvelope(t *testing.T) {
	cfg := baseConfig()
	cfg.Model = "claude-sonnet-5"
	p, err := NewPlan(cfg)
	if err != nil {
		t.Fatal(err)
	}
	cmd := strings.Join(p.DefaultCommand(), " ")
	if !strings.Contains(cmd, "--model claude-sonnet-5") {
		t.Errorf("model not pinned in %q", cmd)
	}
	if !strings.Contains(cmd, "--output-format json") {
		t.Errorf("JSON envelope not requested in %q", cmd)
	}
	p, _ = NewPlan(baseConfig())
	if strings.Contains(strings.Join(p.DefaultCommand(), " "), "--model") {
		t.Error("no model configured must leave the choice to Claude Code")
	}
}

// ADR-056: the owned agent loop replaces Claude Code as the loop. It gets
// the brief as a file, the same MCP config, the role, and no bash; the
// credential rides as env and never appears in the dry run.
func TestRuntimeCommandReplacesClaudeAndRedactsTheKey(t *testing.T) {
	cfg := baseConfig()
	cfg.Runtime = "/sessions/S-x/agent.py"
	cfg.LLMBaseURL = "https://llm.example/v1"
	cfg.Model = "qwen2.5-coder-7b"
	cfg.LLMKey = "sk-secret-123"
	p, err := NewPlan(cfg)
	if err != nil {
		t.Fatal(err)
	}
	cmd := strings.Join(p.command(), " ")
	for _, want := range []string{"python3 /sessions/S-x/agent.py", "--base-url https://llm.example/v1",
		"--model qwen2.5-coder-7b", "--prompt-file", "/brief.md", "--mcp-config", "--role implementer", "--workdir /work", "--transcript", "/transcript.jsonl"} {
		if !strings.Contains(cmd, want) {
			t.Errorf("runtime command missing %q in %q", want, cmd)
		}
	}
	if strings.Contains(cmd, "claude") {
		t.Error("runtime must replace Claude Code")
	}
	args := strings.Join(p.PodmanArgs(), " ")
	if !strings.Contains(args, "--env HOBBES_LLM_API_KEY=sk-secret-123") {
		t.Error("the credential must reach the session as env")
	}
	if dry := p.DryRun(); strings.Contains(dry, "sk-secret-123") || !strings.Contains(dry, "<redacted>") {
		t.Error("the dry run must redact the credential")
	}
	cfg.LLMBaseURL = ""
	if _, err := NewPlan(cfg); err == nil {
		t.Error("a runtime without an endpoint must be refused")
	}
}

func TestEnvironmentBindingIsExplicitAndPrinted(t *testing.T) {
	// ADR-058: a benchmark binds the target's environment — image, PATH,
	// named env vars, a pre-command — and every piece is visible in the
	// argv; nothing from the host environment leaks alongside it.
	cfg := baseConfig()
	cfg.Image = "docker.io/swebench/sweb.eval.x86_64.x_1776_y:latest"
	cfg.Path = "/opt/miniconda3/envs/testbed/bin:/usr/bin:/bin"
	cfg.Env = []string{"PYTHONPATH=/work"}
	cfg.Pre = "cd /testbed && git ls-files -o -z | tar --null -T - -cf - | tar -C /work -xf -"
	cfg.Runtime = "/sessions/S-x/agent.py"
	cfg.RuntimePython = "/opt/miniconda3/bin/python3"
	cfg.LLMBaseURL = "https://llm.example/v1"
	cfg.Model = "m"
	p, err := NewPlan(cfg)
	if err != nil {
		t.Fatal(err)
	}
	args := p.PodmanArgs()
	joined := strings.Join(args, " ")
	for _, want := range []string{
		"--env PATH=/opt/miniconda3/envs/testbed/bin:/usr/bin:/bin",
		"--env PYTHONPATH=/work",
		"sweb.eval.x86_64.x_1776_y:latest",
		"/opt/miniconda3/bin/python3 /sessions/S-x/agent.py",
	} {
		if !strings.Contains(joined, want) {
			t.Errorf("missing %q in:\n%s", want, joined)
		}
	}
	envs := 0
	for _, a := range args {
		if a == "--env" {
			envs++
		}
	}
	if envs != 3 {
		t.Errorf("want HOME, PATH and the one bound var, got %d --env flags", envs)
	}
	// The pre-command wraps the session command and hands its argv through verbatim.
	cmd := p.command()
	if cmd[0] != "/bin/sh" || cmd[1] != "-c" || !strings.HasPrefix(cmd[2], cfg.Pre+" && exec") {
		t.Errorf("pre-command must run first and exec the session command: %v", cmd[:3])
	}
	tail := strings.Join(cmd[4:], " ")
	if !strings.HasPrefix(tail, "/opt/miniconda3/bin/python3 /sessions/S-x/agent.py") {
		t.Errorf("session command not passed through after the pre-command: %q", tail)
	}
	if !strings.Contains(p.DryRun(), "PYTHONPATH=/work") {
		t.Error("the dry run must print the bound environment")
	}
}

func TestNoPreCommandMeansNoWrapper(t *testing.T) {
	p, _ := NewPlan(baseConfig())
	if p.command()[0] == "/bin/sh" {
		t.Error("without --pre the session command runs bare")
	}
}

func TestRuntimeMaxTurnsReachesTheLoop(t *testing.T) {
	cfg := baseConfig()
	cfg.Runtime = "/sessions/S-x/agent.py"
	cfg.LLMBaseURL = "https://llm.example/v1"
	cfg.Model = "m"
	cfg.MaxTurns = 40
	cfg.MaxTokens = 1536
	p, err := NewPlan(cfg)
	if err != nil {
		t.Fatal(err)
	}
	cmd := strings.Join(p.RuntimeCommand(), " ")
	if !strings.Contains(cmd, "--max-turns 40") || !strings.Contains(cmd, "--max-tokens 1536") {
		t.Errorf("max turns/tokens not passed to the loop: %s", cmd)
	}
	cfg.LoopArgs = []string{"--temperature=1.0", "--thinking=on"}
	p, _ = NewPlan(cfg)
	if cmd := strings.Join(p.RuntimeCommand(), " "); !strings.HasSuffix(cmd, "--temperature=1.0 --thinking=on") {
		t.Errorf("loop args must follow the launcher's own flags verbatim (ADR-074): %s", cmd)
	}
	cfg.LoopArgs = nil
	cfg.MaxTurns = 0
	p, _ = NewPlan(cfg)
	if strings.Contains(strings.Join(p.RuntimeCommand(), " "), "--max-turns") {
		t.Errorf("zero max turns must leave the loop's default")
	}
}
