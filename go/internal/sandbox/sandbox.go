// Package sandbox builds the rootless-podman invocation that launches an
// agent session (M4, ADR-018): a fresh git worktree mounted rw, the
// session-state dir mounted rw for the flight recorder and escalation
// queue, the box policy mounted ro, a clean environment, and Claude Code
// wired to the hobbes-proxy MCP server — reaching off the box, when it must,
// only through the egress proxy (ADR-107). The Plan is pure data — it builds
// the podman argv and MCP config without running anything, so the whole
// design is inspectable via `hobbes-session --dry-run` and unit-testable.
package sandbox

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/majax7714/Hobbes/go/internal/egress"
)

// In-container mount points. Fixed so the MCP config and podman args agree.
const (
	WorkDir      = "/work"     // the session worktree, rw
	SessionsRoot = "/sessions" // ~/.hobbes/sessions, rw (logs + escalations)
	ProxyPath    = "/usr/local/bin/hobbes-proxy"
	BoxPath      = "/policy/box.policy"         // ro, only when a host box policy exists
	DerivedDir   = WorkDir + "/.hobbes/derived" // ro, the knowledge layer
	AgentDir     = "/agent"                     // ro, the derived agent dir (ADR-054)
	// ClaudeBinPath is where the host's Claude Code binary is mounted, ro,
	// when the default command runs it (ADR-107): the image carries none.
	ClaudeBinPath = "/usr/local/bin/claude"
)

// The egress plan (ADR-107): one shared custom bridge that reaches off the
// box, one --internal network per session, and one proxy container on both.
const (
	EgressBridge  = "hobbes-egress"
	EgressPort    = "3128"
	EgressLogName = "egress.jsonl"
	egressLogDir  = "/log"
)

// ClaudeTokenEnv is the variable Claude Code reads a long-lived token from
// (`claude setup-token`); it is the doer's one secret, like the owned
// runtime's HOBBES_LLM_API_KEY (C-41).
const ClaudeTokenEnv = "CLAUDE_CODE_OAUTH_TOKEN"

// Config is the wrapper's validated input.
type Config struct {
	SessionID string // generated when empty
	Role      string // required
	Image     string // session image (default hobbes-session:local)
	Task      string // the implementer's prompt (for the default cmd)
	// Model pins the Claude Code model for the default command (ADR-055:
	// the benchmark harness runs a model ladder, so the harness arm must
	// name its model the way the pure arm does). "" leaves the choice to
	// Claude Code.
	Model string
	// Runtime is the in-container path of the owned agent loop
	// (ADR-056), copied into the session dir by the wrapper; "" runs
	// Claude Code. LLMBaseURL is the OpenAI-compatible endpoint it
	// talks to, and LLMKey the bearer token passed through as the
	// HOBBES_LLM_API_KEY env var — the one secret a live session
	// carries, stated in C-41.
	Runtime    string
	LLMBaseURL string
	LLMKey     string
	// RuntimePython is the in-container interpreter that runs the owned
	// loop; "" means the image's python3. A benchmark environment image
	// (ADR-058) carries the target repo's own, possibly old, python as
	// the first on PATH, and the loop needs a modern one.
	RuntimePython string
	// MaxTurns is the owned loop's turn budget; 0 leaves the loop's
	// default. The benchmark passes the same budget to both arms — the
	// first full-stage probe ran harness sessions at the loop's 60 while
	// the pure arm got the run's 40, a fairness gap the meter cannot see.
	MaxTurns int
	// MaxTokens caps one completion of the owned loop; 0 leaves the
	// loop's default. The first full-stage probe spent 45% of its wall
	// on 2,800-token prose turns at ~27 tok/s (a 7B writing the patch
	// as an essay instead of calling write_file); the cap cuts the
	// essay short so the nudge fires sooner. Same cap on both arms.
	MaxTokens int
	// LoopArgs are forwarded to the owned loop verbatim, after the
	// flags above (ADR-074): the sampling a rung wants (temperature,
	// top-p, reasoning effort, thinking mode) is the loop's business,
	// and the session launcher carries it without knowing the names.
	LoopArgs []string
	// Path overrides the in-container PATH; "" keeps the image-neutral
	// default. Env adds KEY=VALUE pairs on top of HOME and PATH — an
	// environment binding the host authored (ADR-058: PYTHONPATH=/work
	// so the worktree shadows the image's installed copy). Pre is a
	// host-authored shell command run before the session command in
	// the same container; it is not the agent's and is not policed.
	Path    string
	Env     []string
	Pre     string
	Network string // podman --network (default "none"); exclusive with Egress
	// Egress names the only hosts the session may reach ("host" or
	// "host:port", 443 by default; ADR-107). Non-empty puts the session on
	// its own --internal network — no route off the box — beside an egress
	// proxy container that tunnels to exactly these hosts and logs every
	// decision to the session dir. It replaces a whole-network --network
	// for a live session (C-41, C-124).
	Egress []string
	// ClaudeBin is the host path of the Claude Code binary the default
	// command runs, mounted read-only at ClaudeBinPath — the image carries
	// no claude (ADR-107). It is the user's own file, so it is never
	// relabeled and the container runs with labeling off, as HostMounts do.
	ClaudeBin string
	// ClaudeToken is the long-lived Claude Code token passed as
	// CLAUDE_CODE_OAUTH_TOKEN. It replaces mounting the host's ~/.claude,
	// which the session's HOME never read and which would have handed the
	// doer every host transcript and memory file.
	ClaudeToken  string
	HostWorktree string // absolute host path of the session worktree
	HostSessions string // absolute host ~/.hobbes/sessions
	HostProxyBin string // absolute host path of the static proxy binary
	HostBoxPath  string // host box policy, "" when none
	// HostDerived is the host repo's .hobbes/derived, mounted ro into the
	// worktree so the knowledge tools have artifacts to answer from — a
	// fresh worktree has none, because derived/ is gitignored. "" omits it.
	HostDerived string
	// HostAgentDir is the derived agent dir for this unit (ADR-054):
	// policy.yaml + context.json + the standing/short-term context the
	// brief was built from. Mounted ro — the session must not be able
	// to edit the policy it is judged by. "" omits it.
	HostAgentDir string
	// HostMounts are host trees the session may read but not write —
	// an environment binding (ADR-100): the dependency trees a target's
	// tests need (a venv and the interpreter it links to, a
	// node_modules, a module cache) when no image carries them. Each is
	// "HOST" (mounted at the same path, so links into it resolve) or
	// "HOST:CONTAINER", always read-only and never relabeled: these
	// are the user's own directories, and a relabel would change their
	// SELinux context in place (the ADR-060 trade taken the other way,
	// as lane B's containers do). Any HostMounts therefore disable
	// labeling for the container, and the dry run prints that.
	HostMounts []string
	Timeout    time.Duration // proxy per-command wall clock, 0 = proxy default
	Escalation time.Duration // proxy park deadline, 0 = proxy default
	// Command overrides the in-container command (the exit check passes a
	// scripted implementer here); empty means the default Claude Code call.
	Command []string
}

// Plan is a ready-to-run sandbox invocation.
type Plan struct {
	cfg Config
}

// NewID mints a sortable, collision-safe session id (matches ADR-014).
func NewID(now time.Time) (string, error) {
	var b [2]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "", err
	}
	return fmt.Sprintf("S-%s-%s",
		now.UTC().Format("20060102T150405Z"), hex.EncodeToString(b[:])), nil
}

// NewPlan validates cfg and returns a Plan.
func NewPlan(cfg Config) (*Plan, error) {
	if cfg.Role == "" {
		return nil, fmt.Errorf("sandbox: role is required")
	}
	if cfg.SessionID == "" {
		return nil, fmt.Errorf("sandbox: session id is required")
	}
	for name, path := range map[string]string{
		"worktree":     cfg.HostWorktree,
		"sessions dir": cfg.HostSessions,
		"proxy binary": cfg.HostProxyBin,
	} {
		if path == "" || !filepath.IsAbs(path) {
			return nil, fmt.Errorf("sandbox: %s must be an absolute host path, got %q", name, path)
		}
	}
	if cfg.Image == "" {
		cfg.Image = "hobbes-session:local"
	}
	if len(cfg.Egress) > 0 {
		if cfg.Network != "" && cfg.Network != "none" {
			return nil, fmt.Errorf("sandbox: --egress and --network %q are exclusive: the egress plan owns the session's network", cfg.Network)
		}
		allow, err := egress.ParseAllowlist(cfg.Egress)
		if err != nil {
			return nil, fmt.Errorf("sandbox: %v", err)
		}
		cfg.Egress = allow.Entries()
		cfg.Network = egressNetwork(cfg.SessionID)
	}
	if cfg.Network == "" {
		cfg.Network = "none"
	}
	if cfg.ClaudeBin != "" && !filepath.IsAbs(cfg.ClaudeBin) {
		return nil, fmt.Errorf("sandbox: the Claude Code binary must be an absolute host path, got %q", cfg.ClaudeBin)
	}
	if cfg.Runtime != "" && (cfg.LLMBaseURL == "" || cfg.Model == "") {
		return nil, fmt.Errorf("sandbox: the agent runtime needs --llm-base-url and --model")
	}
	for _, hm := range cfg.HostMounts {
		host, cont, ok := strings.Cut(hm, ":")
		if !ok {
			cont = host
		}
		if !filepath.IsAbs(host) || !filepath.IsAbs(cont) || strings.Contains(cont, ":") {
			return nil, fmt.Errorf("sandbox: a host mount is HOST or HOST:CONTAINER with absolute paths, got %q", hm)
		}
		if cont == WorkDir || strings.HasPrefix(cont, SessionsRoot+"/") || cont == SessionsRoot {
			return nil, fmt.Errorf("sandbox: a host mount may not shadow %s or %s, got %q", WorkDir, SessionsRoot, hm)
		}
	}
	return &Plan{cfg: cfg}, nil
}

// sessionHome is the in-container HOME: the session's own dir under the
// mounted sessions root, so anything HOME-relative stays box-side.
func (p *Plan) sessionHome() string {
	return SessionsRoot + "/" + p.cfg.SessionID
}

// mcpConfigContainerPath is where the generated MCP config lands (written
// host-side into the session dir, visible here through the mount).
func (p *Plan) mcpConfigContainerPath() string {
	return p.sessionHome() + "/mcp.json"
}

// MCPConfigHostPath is where the wrapper must write the MCP config on the
// host for the container to read it.
func (p *Plan) MCPConfigHostPath() string {
	return filepath.Join(p.cfg.HostSessions, p.cfg.SessionID, "mcp.json")
}

// MCPConfig is the Claude Code MCP config JSON: one server, hobbes, run as
// the policy proxy over stdio against the mounted worktree.
func (p *Plan) MCPConfig() string {
	args := []string{"serve",
		"--repo", WorkDir,
		"--role", p.cfg.Role,
		"--session", p.cfg.SessionID,
		"--log-dir", SessionsRoot,
	}
	if p.cfg.HostBoxPath != "" {
		args = append(args, "--box", BoxPath)
	}
	if p.cfg.HostAgentDir != "" {
		args = append(args, "--agent-dir", AgentDir)
	}
	if p.cfg.Timeout > 0 {
		args = append(args, "--timeout", p.cfg.Timeout.String())
	}
	if p.cfg.Escalation > 0 {
		args = append(args, "--escalation-timeout", p.cfg.Escalation.String())
	}
	cfg := map[string]any{
		"mcpServers": map[string]any{
			"hobbes": map[string]any{
				"command": ProxyPath,
				"args":    args,
			},
		},
	}
	out, _ := json.MarshalIndent(cfg, "", "  ")
	return string(out)
}

// ReadOnlyRoles are the roles whose worktree cannot be changed by the
// session. Architecture §6: "a reviewer session gets read-only mounts +
// the graph-diff tools". §5.2 puts the OS sandbox first among the
// enforcement tiers — the one that actually guarantees anything — so a
// reviewer's inability to write is a mount flag, not a policy rule an
// agent might talk its way around.
//
// The flag is podman's overlay mount (":O", ADR-060), not ":ro": the
// container sees a writable view whose every write lands in a
// throwaway upper layer and the host worktree is never touched. A plain
// ro mount broke the role's actual job — the benchmark environment's
// binding copies build artifacts into /work (C-43) and pytest writes
// caches — so the planner and verifier died before the model ran. What
// the guarantee promises is that nothing the role does reaches the
// tree, and the overlay keeps exactly that; the role still has no
// Edit/Write/exec and no commit, and the harvest reads host commits only.
//
// verifier is D2's verify phase (ADR-054): it judges a merged result and
// owns no code, so it reads like a reviewer. planner (harness
// restructure) breaks a proposal down and hands off through reflect —
// its deliverable is short memory for the next agent, never an edit.
// Mirrored by READ_ONLY_ROLES in the owned loop.
var ReadOnlyRoles = map[string]bool{"reviewer": true, "verifier": true, "planner": true}

// WorktreeMode is "O" (overlay: writable view, host untouched) for a
// read-only role and "rw" otherwise.
func (p *Plan) WorktreeMode() string {
	if ReadOnlyRoles[p.cfg.Role] {
		return "O"
	}
	return "rw"
}

// worktreeMount is the -v spec for the worktree. The overlay option
// cannot be combined with the SELinux relabel (podman rejects "O,z");
// podman labels the overlay itself.
func (p *Plan) worktreeMount() string {
	mode := p.WorktreeMode()
	if mode == "O" {
		return p.cfg.HostWorktree + ":" + WorkDir + ":O"
	}
	return p.cfg.HostWorktree + ":" + WorkDir + ":" + mode + ",z"
}

// mounts returns the -v specs, in a stable order. The `z` suffix requests
// an SELinux relabel to a shared container label, which rootless podman on
// an enforcing host (Fedora, D2) requires to read or write a bind mount.
func (p *Plan) mounts() []string {
	m := []string{
		// The session dir stays rw for every role: the flight recorder
		// and escalation queue must be writable even when the source is
		// not, or a read-only session could not be audited.
		p.worktreeMount(),
		p.cfg.HostSessions + ":" + SessionsRoot + ":rw,z",
		p.cfg.HostProxyBin + ":" + ProxyPath + ":ro,z",
	}
	if p.cfg.HostBoxPath != "" {
		m = append(m, p.cfg.HostBoxPath+":"+BoxPath+":ro,z")
	}
	if p.cfg.ClaudeBin != "" && p.usesClaude() {
		// The user's own binary, read-only and never relabeled (ClaudeBin).
		m = append(m, p.cfg.ClaudeBin+":"+ClaudeBinPath+":ro")
	}
	if p.cfg.HostDerived != "" {
		// Read-only for every role, including the implementer: derived
		// artifacts are the pipeline's output, and a session that could
		// edit them could edit the map it is being judged against.
		m = append(m, p.cfg.HostDerived+":"+DerivedDir+":ro,z")
	}
	if p.cfg.HostAgentDir != "" {
		m = append(m, p.cfg.HostAgentDir+":"+AgentDir+":ro,z")
	}
	for _, hm := range p.cfg.HostMounts {
		host, cont, ok := strings.Cut(hm, ":")
		if !ok {
			cont = host
		}
		m = append(m, host+":"+cont+":ro")
	}
	return m
}

// knowledgeTools is the §6 tool set every role gets: read-only queries
// over the derived layer, so a session starts oriented instead of
// grepping (ADR-017, completed by list_invariants at M8).
var knowledgeTools = []string{
	"mcp__hobbes__graph_neighborhood",
	"mcp__hobbes__who_calls",
	"mcp__hobbes__tests_guarding",
	"mcp__hobbes__get_module_doc",
	"mcp__hobbes__list_invariants",
	"mcp__hobbes__list_blind_spots",
	// reflect (ADR-054) is not a query but it is every role's: the
	// short-term channel back to the orchestrator must be reachable
	// from a read-only session too — a verifier reports through it.
	"mcp__hobbes__reflect",
}

// allowedTools is the native tool allowlist for a role. A reviewer gets
// no Edit/Write and no exec: §6 makes it a read-only role, and its
// worktree is already mounted ro, so offering write tools would only
// produce confusing failures instead of a clear boundary.
func (p *Plan) allowedTools() []string {
	tools := append([]string{}, knowledgeTools...)
	if ReadOnlyRoles[p.cfg.Role] {
		return append(tools, "Read", "Grep", "Glob")
	}
	return append([]string{"mcp__hobbes__exec"}, append(tools, "Edit", "Write", "Read")...)
}

// DefaultCommand is the Claude Code invocation used when the caller
// doesn't override Command. Bash is disallowed at the native layer
// (§5.2 tier 3) so the agent must reach the shell through the
// policy-gated hobbes exec tool; the rest of the allowlist is the role's.
func (p *Plan) DefaultCommand() []string {
	mode := "acceptEdits"
	if ReadOnlyRoles[p.cfg.Role] {
		// Nothing to accept: a read-only role that is asked to confirm an
		// edit has already gone wrong.
		mode = "default"
	}
	cmd := []string{
		"claude", "-p", p.cfg.Task,
		// The JSON result envelope carries usage, cost, turns and wall
		// time; `hobbes run` keeps the session's stdout per unit, so
		// this is what meters the harness arm (ADR-055) — the plain
		// text result would leave tokens unobserved forever.
		"--output-format", "json",
		"--mcp-config", p.mcpConfigContainerPath(),
		// Only the hobbes server: a repo's own .mcp.json (this one starts
		// a podman container) is not the session's to load (ADR-107).
		"--strict-mcp-config",
		"--permission-mode", mode,
		"--disallowedTools", "Bash",
		"--allowedTools", strings.Join(p.allowedTools(), ","),
	}
	if p.cfg.Model != "" {
		cmd = append(cmd, "--model", p.cfg.Model)
	}
	if p.cfg.MaxTurns > 0 {
		cmd = append(cmd, "--max-turns", strconv.Itoa(p.cfg.MaxTurns))
	}
	return cmd
}

// usesClaude reports whether the session runs the default Claude Code
// command (no override, no owned runtime).
func (p *Plan) usesClaude() bool {
	return len(p.cfg.Command) == 0 && p.cfg.Runtime == ""
}

// RuntimeCommand is the owned agent loop's invocation (ADR-056): the
// image's python3 over the copied loop, the brief from the session dir,
// the same MCP config Claude Code would get, and the role so a
// read-only role gets no write tools. Bash is not offered at all — the
// loop withholds it whenever an MCP config is present, so the shell is
// reachable only through the policy-checked exec tool.
func (p *Plan) RuntimeCommand() []string {
	python := p.cfg.RuntimePython
	if python == "" {
		python = "python3"
	}
	cmd := []string{
		python, p.cfg.Runtime,
		"--base-url", p.cfg.LLMBaseURL,
		"--model", p.cfg.Model,
		"--prompt-file", p.sessionHome() + "/brief.md",
		"--mcp-config", p.mcpConfigContainerPath(),
		"--role", p.cfg.Role,
		"--workdir", WorkDir,
		// The full message list lands in the session dir (ADR-064), so
		// a trace does not stop at the [turn N] tool-call line. The
		// session home persists after the clone is cleaned.
		"--transcript", p.sessionHome() + "/transcript.jsonl",
	}
	if p.cfg.MaxTurns > 0 {
		cmd = append(cmd, "--max-turns", strconv.Itoa(p.cfg.MaxTurns))
	}
	if p.cfg.MaxTokens > 0 {
		cmd = append(cmd, "--max-tokens", strconv.Itoa(p.cfg.MaxTokens))
	}
	cmd = append(cmd, p.cfg.LoopArgs...)
	return cmd
}

// command is the in-container command: the override, the owned runtime,
// or the default Claude Code call — wrapped by the pre-command when the
// host authored one (the session command still receives its argv
// verbatim; the wrapper only runs the setup first and fails the session
// if it fails).
func (p *Plan) command() []string {
	var cmd []string
	switch {
	case len(p.cfg.Command) > 0:
		cmd = p.cfg.Command
	case p.cfg.Runtime != "":
		cmd = p.RuntimeCommand()
	default:
		cmd = p.DefaultCommand()
	}
	if p.cfg.Pre == "" {
		return cmd
	}
	return append([]string{"/bin/sh", "-c", p.cfg.Pre + ` && exec "$@"`, "hobbes-pre"}, cmd...)
}

// containerPath is the in-container PATH: image-neutral unless the
// caller bound an environment.
func (p *Plan) containerPath() string {
	if p.cfg.Path != "" {
		return p.cfg.Path
	}
	return "/usr/local/bin:/usr/bin:/bin"
}

// PodmanArgs is the full argv for `podman`, ready to exec. Env is
// deliberately just HOME and PATH — rootless podman passes no host env, so
// no repo or infra secret can reach the session (ADR-018, §5.2) — plus
// whatever the caller bound explicitly in Config.Env, which is a list
// the dry run prints, never the host's environment.
func (p *Plan) PodmanArgs() []string {
	args := []string{
		"run", "--rm",
		"--network", p.cfg.Network,
		"--env", "HOME=" + p.sessionHome(),
		"--env", "PATH=" + p.containerPath(),
		"--workdir", WorkDir,
	}
	for _, kv := range p.cfg.Env {
		args = append(args, "--env", kv)
	}
	if len(p.cfg.HostMounts) > 0 || (p.cfg.ClaudeBin != "" && p.usesClaude()) {
		// The bound trees and the Claude binary are not Hobbes's to
		// relabel (see HostMounts, ClaudeBin); the session's own mounts
		// keep their z, which is harmless with labeling off.
		args = append(args, "--security-opt", "label=disable")
	}
	if p.EgressEnabled() {
		for _, kv := range p.egressEnv() {
			args = append(args, "--env", kv)
		}
	}
	if p.usesClaude() && p.cfg.ClaudeBin != "" {
		// No self-update and no telemetry: the allowlist names the model
		// endpoint alone, and a session's binary is the host's, pinned.
		// Only when the doer is configured, so a plain session keeps the
		// clean HOME-and-PATH environment.
		args = append(args, "--env", "DISABLE_AUTOUPDATER=1", "--env", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1")
		if p.cfg.ClaudeToken != "" {
			// By name: podman copies the value from its own environment
			// (PodmanEnv), so the token is never in an argv or a dry run.
			args = append(args, "--env", ClaudeTokenEnv)
		}
	}
	if ReadOnlyRoles[p.cfg.Role] {
		// A read-only worktree still has to run the repo's tests
		// (verifier): python must not try to write __pycache__ into
		// it, or every import is a noisy EROFS before the test runs.
		args = append(args, "--env", "PYTHONDONTWRITEBYTECODE=1")
	}
	if p.cfg.Runtime != "" && p.cfg.LLMKey != "" {
		// The model credential: the one secret a live session carries
		// (C-41). Passed as env rather than a file so it never lands in
		// the session dir, which outlives the container.
		args = append(args, "--env", "HOBBES_LLM_API_KEY="+p.cfg.LLMKey)
	}
	for _, m := range p.mounts() {
		args = append(args, "-v", m)
	}
	args = append(args, p.cfg.Image)
	args = append(args, p.command()...)
	return args
}

// redactedArgs is PodmanArgs with the model credential masked.
func (p *Plan) redactedArgs() []string {
	args := p.PodmanArgs()
	for i, a := range args {
		if strings.HasPrefix(a, "HOBBES_LLM_API_KEY=") {
			args[i] = "HOBBES_LLM_API_KEY=<redacted>"
		}
	}
	return args
}

// DryRun renders the plan as inspectable text (ADR-018): the podman argv
// and the MCP config the agent will receive.
func (p *Plan) DryRun() string {
	var b strings.Builder
	fmt.Fprintf(&b, "session:  %s (role %s)\n", p.cfg.SessionID, p.cfg.Role)
	fmt.Fprintf(&b, "image:    %s   network: %s\n", p.cfg.Image, p.cfg.Network)
	fmt.Fprintf(&b, "worktree: %s (%s)\n", p.cfg.HostWorktree, p.WorktreeMode())
	if p.cfg.HostAgentDir != "" {
		fmt.Fprintf(&b, "agent:    %s (ro at %s)\n", p.cfg.HostAgentDir, AgentDir)
	}
	if p.cfg.Runtime != "" {
		fmt.Fprintf(&b, "runtime:  %s → %s (%s)\n", p.cfg.Runtime, p.cfg.LLMBaseURL, p.cfg.Model)
	}
	if p.usesClaude() {
		bin, tok := p.cfg.ClaudeBin, "absent"
		if bin == "" {
			bin = "(none: pass --claude-bin)"
		}
		if p.cfg.ClaudeToken != "" {
			tok = "set, passed by name"
		}
		fmt.Fprintf(&b, "doer:     Claude Code %s → %s; %s %s\n", bin, ClaudeBinPath, ClaudeTokenEnv, tok)
	}
	if p.EgressEnabled() {
		fmt.Fprintf(&b, "egress:   %s → %s:%s (allow %s); log %s\n", p.cfg.Network, p.EgressProxyName(), EgressPort,
			strings.Join(p.cfg.Egress, ", "), p.EgressLogHostPath())
		for _, a := range p.EgressSetup() {
			b.WriteString("  setup:    podman " + strings.Join(a, " ") + "\n")
		}
		for _, a := range p.EgressTeardown() {
			b.WriteString("  teardown: podman " + strings.Join(a, " ") + "\n")
		}
	}
	// The dry run never prints the credential.
	b.WriteString("\npodman " + strings.Join(p.redactedArgs(), " ") + "\n")
	b.WriteString("\nMCP config (" + p.MCPConfigHostPath() + "):\n")
	b.WriteString(p.MCPConfig() + "\n")
	return b.String()
}

// SessionID exposes the id for the caller (worktree/dir naming).
func (p *Plan) SessionID() string { return p.cfg.SessionID }

// PodmanEnv is what the launcher adds to podman's own environment for the
// variables PodmanArgs passes by name: today the Claude Code token, when
// the doer is configured (a binary to run).
func (p *Plan) PodmanEnv() []string {
	if p.usesClaude() && p.cfg.ClaudeBin != "" && p.cfg.ClaudeToken != "" {
		return []string{ClaudeTokenEnv + "=" + p.cfg.ClaudeToken}
	}
	return nil
}

// EgressEnabled reports whether the session runs behind the egress proxy.
func (p *Plan) EgressEnabled() bool { return len(p.cfg.Egress) > 0 }

// EgressAllow is the normalized allowlist (host:port, sorted).
func (p *Plan) EgressAllow() []string { return append([]string{}, p.cfg.Egress...) }

// egressNetwork is a session's own --internal network. Podman names are
// lowercased so a generated id is always a valid one.
func egressNetwork(id string) string { return "hobbes-int-" + strings.ToLower(id) }

// EgressProxyName is the proxy container's name — also the host name the
// session's proxy variables point at, resolved on the internal network.
func (p *Plan) EgressProxyName() string { return "hobbes-egress-" + strings.ToLower(p.cfg.SessionID) }

// EgressLogHostPath is the proxy's JSONL log on the host: the session dir,
// beside the flight log, where it outlives both containers.
func (p *Plan) EgressLogHostPath() string {
	return filepath.Join(p.cfg.HostSessions, p.cfg.SessionID, EgressLogName)
}

// egressEnv points every HTTP client in the session at the proxy; both
// spellings, since tools disagree on which they read.
func (p *Plan) egressEnv() []string {
	u := "http://" + p.EgressProxyName() + ":" + EgressPort
	return []string{"HTTPS_PROXY=" + u, "https_proxy=" + u, "HTTP_PROXY=" + u, "http_proxy=" + u,
		"NO_PROXY=localhost,127.0.0.1", "no_proxy=localhost,127.0.0.1"}
}

// EgressBridgeArgs creates the shared egress bridge. The launcher runs it
// only when `podman network exists` says the bridge is missing. A custom
// bridge, not podman's default: attaching to the default one broke DNS in
// ADR-097's measurement.
func EgressBridgeArgs() []string { return []string{"network", "create", EgressBridge} }

// EgressSetup is the podman argv list, in order, that stands the route up
// before the session starts: the session's internal network, then the
// proxy container on that network and on the bridge. The proxy is the
// same static hobbes-proxy the session mounts, and it writes its log into
// the session dir.
func (p *Plan) EgressSetup() [][]string {
	if !p.EgressEnabled() {
		return nil
	}
	run := []string{"run", "-d", "--rm", "--name", p.EgressProxyName(),
		"--network", p.cfg.Network, "--network", EgressBridge,
		"--env", "HOME=/tmp", "--env", "PATH=" + "/usr/local/bin:/usr/bin:/bin",
		"-v", p.cfg.HostProxyBin + ":" + ProxyPath + ":ro,z",
		"-v", filepath.Join(p.cfg.HostSessions, p.cfg.SessionID) + ":" + egressLogDir + ":rw,z",
		p.cfg.Image, ProxyPath, "egress", "--listen", "0.0.0.0:" + EgressPort, "--log", egressLogDir + "/" + EgressLogName}
	for _, h := range p.cfg.Egress {
		run = append(run, "--allow", h)
	}
	return [][]string{{"network", "create", "--internal", p.cfg.Network}, run}
}

// EgressTeardown removes the route after the session: the proxy container,
// then the session's network. The bridge is shared and stays.
func (p *Plan) EgressTeardown() [][]string {
	if !p.EgressEnabled() {
		return nil
	}
	return [][]string{{"rm", "-f", "-t", "0", p.EgressProxyName()}, {"network", "rm", "-f", p.cfg.Network}}
}
