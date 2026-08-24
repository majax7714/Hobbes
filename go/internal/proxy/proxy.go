// Package proxy implements the M4 tool proxy (architecture §5.2 tier 2):
// the MCP server standing between an agent session and the machine. Agents
// get no raw shell — they call the exec tool, the proxy resolves the
// command against the merged policy chain (internal/policy, ADR-002),
// executes or refuses or escalates, and logs every call to the session's
// flight recorder (internal/recorder, ADR-015). Escalated commands park
// as queue records (internal/escalation, ADR-016) and run inside the
// original call once a human approves. One proxy process serves one
// session (ADR-014).
package proxy

import (
	"bytes"
	"context"
	"fmt"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/majax7714/Hobbes/go/internal/escalation"
	"github.com/majax7714/Hobbes/go/internal/policy"
	"github.com/majax7714/Hobbes/go/internal/recorder"
)

// outputCap is the per-stream capture limit for exec results (ADR-015):
// a runaway command must not flood the agent's context window.
const outputCap = 50 * 1024

// DefaultTimeout bounds one exec call unless the caller overrides it.
const DefaultTimeout = 10 * time.Minute

// DefaultEscalationTimeout is §9's expire-to-deny default.
const DefaultEscalationTimeout = 30 * time.Minute

// Parked-call cadences: how often the proxy re-reads the escalation
// record, and how often it reassures the client that the call is alive.
const (
	pollInterval     = 200 * time.Millisecond
	progressInterval = 10 * time.Second
)

// Config identifies the session this proxy serves and where it enforces.
type Config struct {
	Session    string
	Role       string
	RepoRoot   string        // absolute repo root; commands are confined to it
	BoxPath    string        // box policy path, "" for none (ADR-003 rules)
	SessionDir string        // per-session state dir (escalations/ lives here)
	Timeout    time.Duration // per-command wall clock; 0 means DefaultTimeout
	// EscalationTimeout is the park deadline; 0 means the §9 default.
	EscalationTimeout time.Duration
	Rec               *recorder.Recorder
	// AgentDir is the host path of the session's derived agent dir
	// (ADR-054): policy.yaml is loaded as the chain's agent level on
	// every exec, and context.json, when present, is the context
	// manifest knowledge queries are judged against. "" for none.
	AgentDir string
	// KnowledgeOnly serves the read-only knowledge tools and nothing else
	// (ADR-087): exec and reflect are absent from the tool list, not
	// refused — the host session keeps its own shell and its own policy,
	// and Hobbes contributes evidence. Every answer is still recorded.
	KnowledgeOnly bool
}

// Server owns the exec handler for one session.
type Server struct {
	cfg      Config
	manifest *contextManifest // nil when the agent dir carries none
}

// New validates the config and returns a Server.
func New(cfg Config) (*Server, error) {
	if cfg.Session == "" || cfg.Role == "" {
		return nil, fmt.Errorf("proxy: session and role are required")
	}
	root, err := filepath.Abs(cfg.RepoRoot)
	if err != nil {
		return nil, fmt.Errorf("proxy: %w", err)
	}
	cfg.RepoRoot = root
	if cfg.SessionDir == "" {
		return nil, fmt.Errorf("proxy: a session dir is required — escalations park there")
	}
	if cfg.Timeout <= 0 {
		cfg.Timeout = DefaultTimeout
	}
	if cfg.EscalationTimeout <= 0 {
		cfg.EscalationTimeout = DefaultEscalationTimeout
	}
	if cfg.Rec == nil {
		return nil, fmt.Errorf("proxy: a flight recorder is required — the proxy never runs unaudited")
	}
	s := &Server{cfg: cfg}
	if cfg.AgentDir != "" {
		m, err := loadManifest(filepath.Join(cfg.AgentDir, "context.json"))
		if err != nil {
			return nil, fmt.Errorf("proxy: %w", err)
		}
		s.manifest = m
	}
	return s, nil
}

// agentPolicyPath is the derived agent policy inside the agent dir, or
// "" when the session has no agent dir.
func (s *Server) agentPolicyPath() string {
	if s.cfg.AgentDir == "" {
		return ""
	}
	return filepath.Join(s.cfg.AgentDir, "policy.yaml")
}

// ExecArgs is the exec tool's input schema (generated for the agent by the
// MCP SDK from these tags).
type ExecArgs struct {
	Command string `json:"command" jsonschema:"the shell command to run (via /bin/sh -c)"`
	Dir     string `json:"dir,omitempty" jsonschema:"working directory relative to the repo root (default: the repo root)"`
}

// MCP returns the MCP server exposing this session's tools.
func (s *Server) MCP() *mcp.Server {
	srv := mcp.NewServer(&mcp.Implementation{Name: "hobbes-proxy", Version: "0.1.0"}, nil)
	if s.cfg.KnowledgeOnly {
		s.addKnowledgeTools(srv)
		return srv
	}
	mcp.AddTool(srv, &mcp.Tool{
		Name: "exec",
		Description: "Run a shell command in the session repo, gated by the " +
			"merged Hobbes policy chain. allow runs; deny refuses; escalate " +
			"parks this call until a human approves or denies the command " +
			"from the escalation CLI (unanswered escalations expire to " +
			"deny). Every call is logged to the session flight recorder.",
	}, s.handleExec)
	s.addKnowledgeTools(srv)
	s.addReflectTool(srv)
	return srv
}

// errResult wraps a message as a tool-level error the agent can see.
func errResult(format string, args ...any) *mcp.CallToolResult {
	return &mcp.CallToolResult{
		IsError: true,
		Content: []mcp.Content{&mcp.TextContent{Text: fmt.Sprintf(format, args...)}},
	}
}

// handleExec is the exec tool: confine dir → resolve policy → act → log.
func (s *Server) handleExec(ctx context.Context, req *mcp.CallToolRequest, args ExecArgs) (*mcp.CallToolResult, any, error) {
	if strings.TrimSpace(args.Command) == "" {
		return errResult("exec: empty command"), nil, nil
	}

	// Dir confinement is a proxy error, not a policy question (ADR-015).
	dir := filepath.Join(s.cfg.RepoRoot, filepath.FromSlash(args.Dir))
	rel, err := filepath.Rel(s.cfg.RepoRoot, dir)
	if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return errResult("exec: dir %q escapes the repo root", args.Dir), nil, nil
	}

	// The chain is loaded per call: folder policies depend on dir, and a
	// mid-session policy edit should take effect on the next command.
	chain, err := policy.LoadChainFor(policy.ChainOpts{
		BoxPath:     s.cfg.BoxPath,
		RepoRoot:    s.cfg.RepoRoot,
		Dir:         dir,
		Role:        s.cfg.Role,
		AgentPolicy: s.agentPolicyPath(),
	})
	if err != nil {
		return errResult("exec: loading policy chain: %v", err), nil, nil
	}
	// Compound-aware: a `cd /work && pytest` or `git add && git commit` is
	// resolved per segment, as permitted as its least-permitted part (ADR-075).
	res := chain.ResolveCommand(args.Command)

	ev := recorder.Event{
		Session: s.cfg.Session,
		Role:    s.cfg.Role,
		Tool:    "exec",
		// The raw command, not res.Command: normalization is for
		// matching, and may not preserve quoting semantics.
		Argv:       []string{"/bin/sh", "-c", args.Command},
		PolicyRule: policyRuleLabel(res),
		Decision:   string(res.Decision),
		SHA:        headSHA(s.cfg.RepoRoot),
	}

	switch res.Decision {
	case policy.Deny:
		result := errResult("policy denied: %s%s\nThe command was NOT run.",
			ev.PolicyRule, reasonSuffix(res))
		return s.record(ev, result), nil, nil
	case policy.Escalate:
		return s.park(ctx, req, args, dir, res, ev), nil, nil
	}

	result := s.run(ctx, args.Command, dir, &ev)
	return s.record(ev, result), nil, nil
}

// park implements the escalation tier (§9, ADR-016): write the pending
// record, log the park line, then block this call polling for the human's
// verdict. Approved → the command runs here, inside the original call.
// Denied, expired (deadline or disconnect) → refusal. The proxy's clock
// is the expiry authority.
func (s *Server) park(ctx context.Context, req *mcp.CallToolRequest, args ExecArgs, dir string, res policy.Result, ev recorder.Event) *mcp.CallToolResult {
	now := time.Now()
	rec, err := escalation.NewRecord(s.cfg.Session, s.cfg.Role, s.cfg.RepoRoot,
		args.Command, args.Dir, ev.PolicyRule, ruleReason(res), now, s.cfg.EscalationTimeout)
	if err != nil {
		return errResult("exec: %v", err)
	}
	path, err := escalation.Create(filepath.Join(s.cfg.SessionDir, "escalations"), rec)
	if err != nil {
		return errResult("exec: %v", err)
	}

	parkEv := ev
	parkEv.Escalation = &recorder.EscalationRef{ID: rec.ID}
	if err := s.cfg.Rec.Record(parkEv); err != nil {
		// An unlogged park must not sit approvable for half an hour.
		_, _ = escalation.MarkExpired(path, time.Now())
		return errResult("exec: flight recorder write failed while parking: %v", err)
	}

	resolved := func(resolution, approver string) recorder.Event {
		out := ev
		out.Escalation = &recorder.EscalationRef{
			ID: rec.ID, Resolution: resolution, Approver: approver,
		}
		return out
	}

	deadline := now.Add(s.cfg.EscalationTimeout)
	poll := time.NewTicker(pollInterval)
	defer poll.Stop()
	progress := time.NewTicker(progressInterval)
	defer progress.Stop()

	for {
		select {
		case <-ctx.Done():
			_, _ = escalation.MarkExpired(path, time.Now())
			return s.record(resolved("expired", ""),
				errResult("escalation %s: session ended while parked — command NOT run", rec.ID))
		case <-progress.C:
			s.notifyParked(ctx, req, rec.ID, time.Until(deadline))
			continue
		case <-poll.C:
		}

		if time.Now().After(deadline) {
			_, _ = escalation.MarkExpired(path, time.Now())
			return s.record(resolved("expired", ""), errResult(
				"escalation %s expired after %s with no human response — "+
					"command NOT run (expires to deny, architecture §9)",
				rec.ID, s.cfg.EscalationTimeout))
		}

		current, err := escalation.Load(path)
		if err != nil {
			continue // mid-rename read; next poll settles it
		}
		switch current.Status {
		case escalation.Approved:
			runEv := resolved("approved", current.Approver)
			result := s.run(ctx, args.Command, dir, &runEv)
			result.Content = append([]mcp.Content{&mcp.TextContent{
				Text: fmt.Sprintf("escalation %s approved by %s\n", rec.ID, current.Approver),
			}}, result.Content...)
			return s.record(runEv, result)
		case escalation.Denied:
			return s.record(resolved("denied", current.Approver), errResult(
				"escalation %s denied by %s — command NOT run",
				rec.ID, current.Approver))
		case escalation.Expired:
			// The CLI settled it (a too-late approval attempt).
			return s.record(resolved("expired", ""), errResult(
				"escalation %s expired — command NOT run", rec.ID))
		}
	}
}

// notifyParked keeps the client's tool call alive during a park, when the
// client asked for progress (a token in the request metadata).
func (s *Server) notifyParked(ctx context.Context, req *mcp.CallToolRequest, id string, remaining time.Duration) {
	if req == nil || req.Session == nil || req.Params == nil {
		return
	}
	token := req.Params.Meta["progressToken"]
	if token == nil {
		return
	}
	elapsed := s.cfg.EscalationTimeout - remaining
	_ = req.Session.NotifyProgress(ctx, &mcp.ProgressNotificationParams{
		ProgressToken: token,
		Progress:      elapsed.Seconds(),
		Total:         s.cfg.EscalationTimeout.Seconds(),
		Message: fmt.Sprintf("escalation %s awaiting human approval (%s until expiry)",
			id, remaining.Round(time.Second)),
	})
}

// ruleReason is the decisive rule's reason, or "" for defaults.
func ruleReason(res policy.Result) string {
	if res.Rule == nil {
		return ""
	}
	return res.Rule.Reason
}

// run executes an allowed command and fills the event's exit code.
func (s *Server) run(ctx context.Context, command, dir string, ev *recorder.Event) *mcp.CallToolResult {
	cctx, cancel := context.WithTimeout(ctx, s.cfg.Timeout)
	defer cancel()

	cmd := exec.CommandContext(cctx, "/bin/sh", "-c", command)
	cmd.Dir = dir
	// Kill the whole process group on timeout, not just the shell.
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	cmd.Cancel = func() error {
		return syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL)
	}
	cmd.WaitDelay = 5 * time.Second

	stdout := &cappedBuffer{cap: outputCap}
	stderr := &cappedBuffer{cap: outputCap}
	cmd.Stdout = stdout
	cmd.Stderr = stderr

	runErr := cmd.Run()
	if cmd.ProcessState == nil {
		// Spawn failure: nothing ran, exit stays null (ADR-015).
		return errResult("exec: failed to start: %v", runErr)
	}
	exit := cmd.ProcessState.ExitCode()
	ev.Exit = &exit

	var b strings.Builder
	fmt.Fprintf(&b, "exit %d", exit)
	if cctx.Err() == context.DeadlineExceeded {
		fmt.Fprintf(&b, " (killed: timed out after %s)", s.cfg.Timeout)
	}
	b.WriteString("\n--- stdout ---\n")
	b.Write(stdout.bytes())
	b.WriteString("\n--- stderr ---\n")
	b.Write(stderr.bytes())

	return &mcp.CallToolResult{
		IsError: exit != 0,
		Content: []mcp.Content{&mcp.TextContent{Text: b.String()}},
	}
}

// record appends the event to the flight log. A recorder failure is
// surfaced on the result — an unauditable proxy must not look healthy.
func (s *Server) record(ev recorder.Event, result *mcp.CallToolResult) *mcp.CallToolResult {
	if err := s.cfg.Rec.Record(ev); err != nil {
		result.IsError = true
		result.Content = append(result.Content, &mcp.TextContent{
			Text: fmt.Sprintf("WARNING: flight recorder write failed: %v", err),
		})
	}
	return result
}

// policyRuleLabel renders the decisive rule for the recorder (ADR-015).
func policyRuleLabel(res policy.Result) string {
	if res.ByDefault {
		if res.DefaultSource == "" {
			return "default:engine"
		}
		return "default:" + res.DefaultSource
	}
	return fmt.Sprintf("%s: %s", res.Rule.Source, res.Rule.Pattern)
}

// reasonSuffix renders the decisive rule's reason, if it has one.
func reasonSuffix(res policy.Result) string {
	if res.Rule == nil || res.Rule.Reason == "" {
		return ""
	}
	return " — " + res.Rule.Reason
}

// headSHA reads the repo's current HEAD; empty when unreadable. Re-read
// per event: implementer sessions commit mid-session (ADR-015).
func headSHA(repoRoot string) string {
	out, err := exec.Command("git", "-C", repoRoot, "rev-parse", "HEAD").Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(out))
}

// cappedBuffer keeps the first cap bytes and notes any overflow.
type cappedBuffer struct {
	buf       bytes.Buffer
	cap       int
	truncated bool
}

func (c *cappedBuffer) Write(p []byte) (int, error) {
	if room := c.cap - c.buf.Len(); room > 0 {
		if len(p) > room {
			c.buf.Write(p[:room])
			c.truncated = true
		} else {
			c.buf.Write(p)
		}
	} else if len(p) > 0 {
		c.truncated = true
	}
	return len(p), nil
}

func (c *cappedBuffer) bytes() []byte {
	if c.truncated {
		return append(c.buf.Bytes(), fmt.Sprintf("\n[truncated at %d KiB]", c.cap/1024)...)
	}
	return c.buf.Bytes()
}
