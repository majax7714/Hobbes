package proxy

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	schema "github.com/majax7714/Hobbes/go/internal/derived"
	"github.com/majax7714/Hobbes/go/internal/escalation"
	"github.com/majax7714/Hobbes/go/internal/knowledge"
	"github.com/majax7714/Hobbes/go/internal/recorder"
)

// testPolicy allows the commands the tests run, escalates pushes, and
// denies recursive deletes.
const testPolicy = `version: 1
scope: repo
default: escalate
rules:
  - pattern: "echo *"
    decision: allow
  - pattern: "sleep *"
    decision: allow
  - pattern: "head *"
    decision: allow
  - pattern: "tr *"
    decision: allow
  - pattern: "cat *"
    decision: allow
  - pattern: "false"
    decision: allow
  - pattern: "git push*"
    decision: escalate
    reason: "pushes need a human"
  - pattern: "rm -rf *"
    decision: deny
    reason: "no recursive deletes"
`

func git(t *testing.T, repo string, args ...string) string {
	t.Helper()
	full := append([]string{"-C", repo, "-c", "user.name=t", "-c", "user.email=t@t"}, args...)
	out, err := exec.Command("git", full...).Output()
	if err != nil {
		t.Fatalf("git %v: %v", args, err)
	}
	return strings.TrimSpace(string(out))
}

// testRepo makes a one-commit git repo carrying the test repo policy.
func testRepo(t *testing.T) string {
	t.Helper()
	repo := t.TempDir()
	policyPath := filepath.Join(repo, ".hobbes", "policies", "repo.policy")
	if err := os.MkdirAll(filepath.Dir(policyPath), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(policyPath, []byte(testPolicy), 0o644); err != nil {
		t.Fatal(err)
	}
	git(t, repo, "init", "-q")
	git(t, repo, "add", ".")
	git(t, repo, "commit", "-qm", "fixture")
	return repo
}

// newServerFull builds a proxy over repo; returns it with its flight-log
// path and session dir (where escalations park).
func newServerFull(t *testing.T, repo string, timeout, escTimeout time.Duration) (*Server, string, string) {
	t.Helper()
	sessionDir := t.TempDir()
	logPath := filepath.Join(sessionDir, "flight.jsonl")
	rec, err := recorder.Open(logPath)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { rec.Close() })
	s, err := New(Config{
		Session:           "S-test",
		Role:              "implementer",
		RepoRoot:          repo,
		SessionDir:        sessionDir,
		Timeout:           timeout,
		EscalationTimeout: escTimeout,
		Rec:               rec,
	})
	if err != nil {
		t.Fatal(err)
	}
	return s, logPath, sessionDir
}

// newServer is newServerFull with a short escalation timeout, so tests
// that trip an unattended escalation expire in milliseconds, not §9's 30m.
func newServer(t *testing.T, repo string, timeout time.Duration) (*Server, string) {
	t.Helper()
	s, logPath, _ := newServerFull(t, repo, timeout, 400*time.Millisecond)
	return s, logPath
}

// pendingEscalation waits for the park loop to write the queue record.
func pendingEscalation(t *testing.T, sessionDir string) string {
	t.Helper()
	dir := filepath.Join(sessionDir, "escalations")
	for i := 0; i < 100; i++ {
		entries, err := os.ReadDir(dir)
		if err == nil && len(entries) == 1 {
			return filepath.Join(dir, entries[0].Name())
		}
		time.Sleep(20 * time.Millisecond)
	}
	t.Fatal("no escalation record appeared")
	return ""
}

func events(t *testing.T, logPath string) []recorder.Event {
	t.Helper()
	f, err := os.Open(logPath)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	var evs []recorder.Event
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		var ev recorder.Event
		if err := json.Unmarshal(scanner.Bytes(), &ev); err != nil {
			t.Fatalf("bad flight line: %v", err)
		}
		evs = append(evs, ev)
	}
	return evs
}

func callExec(t *testing.T, s *Server, args ExecArgs) *mcp.CallToolResult {
	t.Helper()
	res, _, err := s.handleExec(context.Background(), nil, args)
	if err != nil {
		t.Fatalf("handleExec returned protocol error: %v", err)
	}
	return res
}

func text(res *mcp.CallToolResult) string {
	var b strings.Builder
	for _, c := range res.Content {
		if tc, ok := c.(*mcp.TextContent); ok {
			b.WriteString(tc.Text)
		}
	}
	return b.String()
}

func TestAllowedCommandRunsAndLogs(t *testing.T) {
	repo := testRepo(t)
	s, logPath := newServer(t, repo, 0)

	res := callExec(t, s, ExecArgs{Command: "echo hobbes"})
	if res.IsError {
		t.Fatalf("allowed command marked error: %s", text(res))
	}
	out := text(res)
	if !strings.HasPrefix(out, "exit 0") || !strings.Contains(out, "hobbes") {
		t.Errorf("unexpected result text: %q", out)
	}

	evs := events(t, logPath)
	if len(evs) != 1 {
		t.Fatalf("got %d events, want 1", len(evs))
	}
	ev := evs[0]
	if ev.Decision != "allow" || ev.Exit == nil || *ev.Exit != 0 {
		t.Errorf("event = %+v", ev)
	}
	if want := []string{"/bin/sh", "-c", "echo hobbes"}; strings.Join(ev.Argv, "\x00") != strings.Join(want, "\x00") {
		t.Errorf("argv = %v", ev.Argv)
	}
	if ev.PolicyRule != filepath.Join(repo, ".hobbes", "policies", "repo.policy")+": echo *" {
		t.Errorf("policy_rule = %q", ev.PolicyRule)
	}
	if ev.SHA != git(t, repo, "rev-parse", "HEAD") {
		t.Errorf("sha = %q, want repo HEAD", ev.SHA)
	}
}

func TestNonzeroExitIsErrorButLogged(t *testing.T) {
	s, logPath := newServer(t, testRepo(t), 0)
	res := callExec(t, s, ExecArgs{Command: "false"})
	if !res.IsError || !strings.HasPrefix(text(res), "exit 1") {
		t.Errorf("want isError with exit 1, got %v %q", res.IsError, text(res))
	}
	ev := events(t, logPath)[0]
	if ev.Exit == nil || *ev.Exit != 1 {
		t.Errorf("exit = %v, want 1", ev.Exit)
	}
}

func TestDeniedCommandDoesNotRun(t *testing.T) {
	repo := testRepo(t)
	s, logPath := newServer(t, repo, 0)
	victim := filepath.Join(repo, "victim.txt")
	if err := os.WriteFile(victim, []byte("x"), 0o644); err != nil {
		t.Fatal(err)
	}

	res := callExec(t, s, ExecArgs{Command: "rm -rf " + victim})
	if !res.IsError || !strings.Contains(text(res), "policy denied") {
		t.Fatalf("want policy denial, got %v %q", res.IsError, text(res))
	}
	if !strings.Contains(text(res), "no recursive deletes") {
		t.Errorf("denial should carry the rule reason: %q", text(res))
	}
	if _, err := os.Stat(victim); err != nil {
		t.Error("denied command ran anyway: victim deleted")
	}
	ev := events(t, logPath)[0]
	if ev.Decision != "deny" || ev.Exit != nil {
		t.Errorf("event = %+v", ev)
	}
}

func TestTfstateFloorHoldsWithAllowingRepoPolicy(t *testing.T) {
	// The repo policy allows "cat *", but the builtin box floor
	// (ADR-011) still denies state files — deny is unshadowable.
	s, logPath := newServer(t, testRepo(t), 0)
	res := callExec(t, s, ExecArgs{Command: "cat prod.tfstate"})
	if !res.IsError || !strings.Contains(text(res), "builtin:tfstate-floor") {
		t.Errorf("want builtin floor denial, got %q", text(res))
	}
	if ev := events(t, logPath)[0]; ev.Decision != "deny" {
		t.Errorf("decision = %q", ev.Decision)
	}
}

func TestApprovedEscalationRunsAndLogsApprover(t *testing.T) {
	repo := testRepo(t)
	s, logPath, sessionDir := newServerFull(t, repo, 0, 10*time.Second)

	done := make(chan *mcp.CallToolResult, 1)
	go func() {
		res, _, _ := s.handleExec(context.Background(), nil,
			ExecArgs{Command: "git push origin main"})
		done <- res
	}()

	path := pendingEscalation(t, sessionDir)
	if _, err := escalation.Resolve(path, escalation.Approved, "max", time.Now()); err != nil {
		t.Fatal(err)
	}

	// The command isn't a real push — the test repo has no remote — but
	// it must RUN after approval; a failing run still proves execution.
	res := <-done
	out := text(res)
	if !strings.Contains(out, "approved by max") {
		t.Errorf("result should name the approver: %q", out)
	}
	if !strings.Contains(out, "exit ") {
		t.Errorf("approved command did not run: %q", out)
	}

	evs := events(t, logPath)
	if len(evs) != 2 {
		t.Fatalf("want park + resolution lines, got %d", len(evs))
	}
	park, resl := evs[0], evs[1]
	if park.Escalation == nil || park.Escalation.Resolution != "" {
		t.Errorf("park line = %+v", park)
	}
	if resl.Escalation == nil || resl.Escalation.Resolution != "approved" ||
		resl.Escalation.Approver != "max" {
		t.Errorf("resolution line = %+v", resl)
	}
	if resl.Decision != "escalate" {
		t.Errorf("policy decision must stay escalate, got %q", resl.Decision)
	}
	if resl.Exit == nil {
		t.Error("approved-and-ran line must carry an exit code")
	}
	if park.Escalation.ID != resl.Escalation.ID {
		t.Error("park and resolution lines must share the escalation id")
	}
}

func TestDeniedEscalationRefusesWithDenier(t *testing.T) {
	repo := testRepo(t)
	s, logPath, sessionDir := newServerFull(t, repo, 0, 10*time.Second)

	done := make(chan *mcp.CallToolResult, 1)
	go func() {
		res, _, _ := s.handleExec(context.Background(), nil,
			ExecArgs{Command: "git push origin main"})
		done <- res
	}()
	path := pendingEscalation(t, sessionDir)
	if _, err := escalation.Resolve(path, escalation.Denied, "max", time.Now()); err != nil {
		t.Fatal(err)
	}

	res := <-done
	if !res.IsError || !strings.Contains(text(res), "denied by max") {
		t.Errorf("want denial naming the denier, got %q", text(res))
	}
	evs := events(t, logPath)
	if len(evs) != 2 || evs[1].Escalation.Resolution != "denied" || evs[1].Exit != nil {
		t.Errorf("flight lines = %+v", evs)
	}
}

func TestUnansweredEscalationExpiresToDeny(t *testing.T) {
	repo := testRepo(t)
	s, logPath, sessionDir := newServerFull(t, repo, 0, 300*time.Millisecond)

	start := time.Now()
	res := callExec(t, s, ExecArgs{Command: "git push origin main"})
	if elapsed := time.Since(start); elapsed > 3*time.Second {
		t.Fatalf("expiry took %s", elapsed)
	}
	if !res.IsError || !strings.Contains(text(res), "expired") {
		t.Errorf("want expiry refusal, got %q", text(res))
	}

	record, err := escalation.Load(pendingEscalation(t, sessionDir))
	if err != nil {
		t.Fatal(err)
	}
	if record.Status != escalation.Expired {
		t.Errorf("record status = %q, want expired", record.Status)
	}
	evs := events(t, logPath)
	if len(evs) != 2 || evs[1].Escalation.Resolution != "expired" ||
		evs[1].Escalation.Approver != "" {
		t.Errorf("flight lines = %+v", evs)
	}
}

func TestUnmatchedCommandFallsToDefault(t *testing.T) {
	// newServer's 400ms escalation timeout: the unattended park expires.
	s, logPath := newServer(t, testRepo(t), 0)
	res := callExec(t, s, ExecArgs{Command: "curl example.com"})
	if !res.IsError || !strings.Contains(text(res), "expired") {
		t.Errorf("unattended default-escalate should expire to deny: %q", text(res))
	}
	ev := events(t, logPath)[0]
	if ev.Decision != "escalate" || !strings.HasPrefix(ev.PolicyRule, "default:") {
		t.Errorf("event = %+v", ev)
	}
}

func TestEngineFallbackWhenNoPoliciesAtAll(t *testing.T) {
	repo := t.TempDir()
	git(t, repo, "init", "-q")
	git(t, repo, "commit", "-qm", "empty", "--allow-empty")
	s, logPath := newServer(t, repo, 0)

	res := callExec(t, s, ExecArgs{Command: "echo hi"})
	if !res.IsError {
		t.Error("with no policies, everything escalates (engine fallback)")
	}
	if ev := events(t, logPath)[0]; ev.PolicyRule != "default:engine" {
		t.Errorf("policy_rule = %q, want default:engine", ev.PolicyRule)
	}
}

func TestFolderPolicyDeniesInItsSubtreeOnly(t *testing.T) {
	repo := testRepo(t)
	folder := filepath.Join(repo, "vendored", ".hobbes")
	if err := os.MkdirAll(folder, 0o755); err != nil {
		t.Fatal(err)
	}
	folderPolicy := "version: 1\nscope: folder\nrules:\n" +
		"  - pattern: \"echo *\"\n    decision: deny\n    reason: \"read-only folder\"\n"
	if err := os.WriteFile(filepath.Join(folder, "folder.policy"), []byte(folderPolicy), 0o644); err != nil {
		t.Fatal(err)
	}
	s, _ := newServer(t, repo, 0)

	if res := callExec(t, s, ExecArgs{Command: "echo hi", Dir: "vendored"}); !res.IsError {
		t.Error("folder deny should apply inside the folder")
	}
	if res := callExec(t, s, ExecArgs{Command: "echo hi"}); res.IsError {
		t.Errorf("folder deny leaked to the repo root: %q", text(res))
	}
}

func TestDirEscapeRefusedWithoutLogging(t *testing.T) {
	s, logPath := newServer(t, testRepo(t), 0)
	res := callExec(t, s, ExecArgs{Command: "echo hi", Dir: "../.."})
	if !res.IsError || !strings.Contains(text(res), "escapes") {
		t.Errorf("want dir-escape refusal, got %q", text(res))
	}
	if evs := events(t, logPath); len(evs) != 0 {
		t.Errorf("proxy-level refusal should not reach the recorder, got %d events", len(evs))
	}
}

func TestTimeoutKillsAndLogs(t *testing.T) {
	s, logPath := newServer(t, testRepo(t), 200*time.Millisecond)
	start := time.Now()
	res := callExec(t, s, ExecArgs{Command: "sleep 5"})
	if elapsed := time.Since(start); elapsed > 3*time.Second {
		t.Fatalf("timeout did not kill promptly: took %s", elapsed)
	}
	if !res.IsError || !strings.Contains(text(res), "timed out") {
		t.Errorf("want timeout note, got %q", text(res))
	}
	ev := events(t, logPath)[0]
	if ev.Exit == nil || *ev.Exit != -1 {
		t.Errorf("exit = %v, want -1 for a killed process", ev.Exit)
	}
}

func TestOutputTruncatedAtCap(t *testing.T) {
	s, _ := newServer(t, testRepo(t), 0)
	res := callExec(t, s, ExecArgs{Command: "head -c 60000 /dev/zero | tr '\\0' x"})
	out := text(res)
	if !strings.Contains(out, "[truncated at 50 KiB]") {
		t.Error("oversized stdout should carry the truncation marker")
	}
	if len(out) > outputCap+1024 {
		t.Errorf("result text is %d bytes; cap failed", len(out))
	}
}

func TestShaTracksHeadAcrossCommits(t *testing.T) {
	repo := testRepo(t)
	s, logPath := newServer(t, repo, 0)
	callExec(t, s, ExecArgs{Command: "echo one"})
	git(t, repo, "commit", "-qm", "next", "--allow-empty")
	callExec(t, s, ExecArgs{Command: "echo two"})

	evs := events(t, logPath)
	if len(evs) != 2 || evs[0].SHA == evs[1].SHA {
		t.Errorf("per-event sha should track HEAD: %+v", evs)
	}
	if evs[1].SHA != git(t, repo, "rev-parse", "HEAD") {
		t.Errorf("second sha = %q, want current HEAD", evs[1].SHA)
	}
}

func TestKnowledgeQueryAnswersAndLogs(t *testing.T) {
	repo := testRepo(t)
	// Hand the fixture minimal derived artifacts.
	derived := filepath.Join(repo, ".hobbes", "derived")
	if err := os.MkdirAll(derived, 0o755); err != nil {
		t.Fatal(err)
	}
	sha := git(t, repo, "rev-parse", "HEAD")
	graph := fmt.Sprintf(`{"schema_version":%d,"sha":%q,"dirty":false,
		"nodes":[{"id":"app.a","kind":"module","path":"a.py"},{"id":"app.b","kind":"module","path":"b.py"}],
		"module_edges":[{"from":"app.a","to":"app.b","type":"imports","tier":"syntactic",
			"evidence":[{"path":"a.py","line":1,"lane":"tree-sitter"}]}],
		"symbols":[],"symbol_edges":[]}`, schema.Current, sha)
	if err := os.WriteFile(filepath.Join(derived, "graph.json"), []byte(graph), 0o644); err != nil {
		t.Fatal(err)
	}
	s, logPath := newServer(t, repo, 0)

	out := s.answer("graph_neighborhood", "app.a", knowledge.Open(repo).Neighborhood)
	if out.IsError || !strings.Contains(text(out), "-imports-> app.b") {
		t.Errorf("neighborhood answer: %q", text(out))
	}
	ev := events(t, logPath)[0]
	if ev.Tool != "graph_neighborhood" || ev.Decision != "allow" ||
		ev.PolicyRule != "builtin:knowledge-read" || ev.Exit != nil {
		t.Errorf("knowledge event = %+v", ev)
	}
	if len(ev.Argv) != 1 || ev.Argv[0] != "app.a" {
		t.Errorf("argv = %v", ev.Argv)
	}
}

func TestDisconnectWhileParkedSettlesRecord(t *testing.T) {
	repo := testRepo(t)
	s, logPath, sessionDir := newServerFull(t, repo, 0, 10*time.Second)

	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan *mcp.CallToolResult, 1)
	go func() {
		res, _, _ := s.handleExec(ctx, nil, ExecArgs{Command: "git push origin main"})
		done <- res
	}()
	path := pendingEscalation(t, sessionDir)
	cancel()

	res := <-done
	if !res.IsError || !strings.Contains(text(res), "session ended") {
		t.Errorf("want disconnect refusal, got %q", text(res))
	}
	record, err := escalation.Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if record.Status != escalation.Expired {
		t.Errorf("record left %q; a dead session must not leave approvable commands", record.Status)
	}
	evs := events(t, logPath)
	if len(evs) != 2 || evs[1].Escalation.Resolution != "expired" {
		t.Errorf("flight lines = %+v", evs)
	}
}

func TestNewRejectsAnonymousOrUnauditedProxies(t *testing.T) {
	rec, err := recorder.Open(filepath.Join(t.TempDir(), "f.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	defer rec.Close()
	dir := t.TempDir()
	if _, err := New(Config{RepoRoot: ".", SessionDir: dir, Rec: rec}); err == nil {
		t.Error("missing session/role must be rejected")
	}
	if _, err := New(Config{Session: "s", Role: "r", RepoRoot: ".", SessionDir: dir}); err == nil {
		t.Error("missing recorder must be rejected")
	}
	if _, err := New(Config{Session: "s", Role: "r", RepoRoot: ".", Rec: rec}); err == nil {
		t.Error("missing session dir must be rejected")
	}
}
