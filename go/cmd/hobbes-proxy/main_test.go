package main

import (
	"bytes"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
	"time"

	"github.com/majax7714/Hobbes/go/internal/escalation"
)

// cli runs the binary's dispatcher, capturing both streams.
func cli(args ...string) (int, string, string) {
	var stdout, stderr bytes.Buffer
	code := run(args, &stdout, &stderr)
	return code, stdout.String(), stderr.String()
}

func TestNoArgsPrintsUsage(t *testing.T) {
	code, _, stderr := cli()
	if code != exitUsage || !strings.Contains(stderr, "usage:") {
		t.Errorf("code=%d stderr=%q", code, stderr)
	}
}

func TestUnknownCommandRejected(t *testing.T) {
	if code, _, _ := cli("resolve"); code != exitUsage {
		t.Errorf("exit = %d, want %d", code, exitUsage)
	}
}

func TestServeRequiresRepoAndRole(t *testing.T) {
	if code, _, _ := cli("serve", "--repo", t.TempDir()); code != exitUsage {
		t.Errorf("missing --role: exit = %d, want %d", code, exitUsage)
	}
	if code, _, _ := cli("serve", "--role", "implementer"); code != exitUsage {
		t.Errorf("missing --repo: exit = %d, want %d", code, exitUsage)
	}
}

func TestServeRejectsMissingRepoDir(t *testing.T) {
	code, _, stderr := cli("serve", "--repo", "/nonexistent-hobbes", "--role", "r")
	if code != exitError || !strings.Contains(stderr, "not a directory") {
		t.Errorf("code=%d stderr=%q", code, stderr)
	}
}

func TestParseServeDefaultsAndSessionDir(t *testing.T) {
	repo := t.TempDir()
	var stderr bytes.Buffer
	cfg, logPath, err := parseServe(
		[]string{"--repo", repo, "--role", "implementer", "--session", "S-x",
			"--log-dir", "/logs", "--timeout", "30s",
			"--escalation-timeout", "5m"}, &stderr)
	if err != nil {
		t.Fatal(err)
	}
	if cfg.Role != "implementer" || cfg.Timeout != 30*time.Second ||
		cfg.EscalationTimeout != 5*time.Minute {
		t.Errorf("cfg = %+v", cfg)
	}
	if cfg.SessionDir != "/logs/S-x" || logPath != "/logs/S-x/flight.jsonl" {
		t.Errorf("sessionDir=%q logPath=%q", cfg.SessionDir, logPath)
	}
}

func TestGeneratedSessionIDShape(t *testing.T) {
	id, err := generateSessionID()
	if err != nil {
		t.Fatal(err)
	}
	if !regexp.MustCompile(`^S-\d{8}T\d{6}Z-[0-9a-f]{4}$`).MatchString(id) {
		t.Errorf("session id %q has unexpected shape", id)
	}
	other, _ := generateSessionID()
	if id == other {
		t.Error("two generated ids collided")
	}
}

// parkRecord plants a pending escalation under root for CLI tests.
func parkRecord(t *testing.T, root, session string, age time.Duration) *escalation.Record {
	t.Helper()
	r, err := escalation.NewRecord(session, "implementer", "/repo",
		"git push origin main", "", "repo.policy: git push*", "pushes need a human",
		time.Now().Add(-age), 30*time.Minute)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := escalation.Create(filepath.Join(root, session, "escalations"), r); err != nil {
		t.Fatal(err)
	}
	return r
}

func TestEscalationsListShowsPending(t *testing.T) {
	root := t.TempDir()
	r := parkRecord(t, root, "S-1", 0)
	code, stdout, _ := cli("escalations", "list", "--log-dir", root)
	if code != exitOK {
		t.Fatalf("exit = %d", code)
	}
	if !strings.Contains(stdout, r.ID) || !strings.Contains(stdout, "git push origin main") ||
		!strings.Contains(stdout, "pending") {
		t.Errorf("list output = %q", stdout)
	}
}

func TestEscalationsBareCommandDefaultsToList(t *testing.T) {
	root := t.TempDir()
	code, stdout, _ := cli("escalations", "--log-dir", root)
	if code != exitOK || !strings.Contains(stdout, "no pending escalations") {
		t.Errorf("code=%d stdout=%q", code, stdout)
	}
}

func TestEscalationsListHidesExpiredUnlessAll(t *testing.T) {
	root := t.TempDir()
	r := parkRecord(t, root, "S-1", time.Hour) // past its 30m deadline
	_, stdout, _ := cli("escalations", "list", "--log-dir", root)
	if strings.Contains(stdout, r.ID) {
		t.Errorf("expired record in default list: %q", stdout)
	}
	_, stdout, _ = cli("escalations", "list", "--all", "--log-dir", root)
	if !strings.Contains(stdout, r.ID) || !strings.Contains(stdout, "expired") {
		t.Errorf("--all should show it as expired: %q", stdout)
	}
}

func TestEscalationsApproveRecordsUser(t *testing.T) {
	root := t.TempDir()
	r := parkRecord(t, root, "S-1", 0)
	code, stdout, _ := cli("escalations", "approve", r.ID, "--log-dir", root)
	if code != exitOK || !strings.Contains(stdout, "approved "+r.ID) {
		t.Fatalf("code=%d stdout=%q", code, stdout)
	}
	item, err := escalation.FindByID(root, r.ID)
	if err != nil {
		t.Fatal(err)
	}
	if item.Record.Status != escalation.Approved || item.Record.Approver == "" {
		t.Errorf("record = %+v", item.Record)
	}
}

func TestEscalationsDeny(t *testing.T) {
	root := t.TempDir()
	r := parkRecord(t, root, "S-1", 0)
	code, stdout, _ := cli("escalations", "deny", r.ID, "--log-dir", root)
	if code != exitOK || !strings.Contains(stdout, "denied "+r.ID) {
		t.Fatalf("code=%d stdout=%q", code, stdout)
	}
}

func TestEscalationsApproveUnknownIDFails(t *testing.T) {
	code, _, stderr := cli("escalations", "approve", "E-nope", "--log-dir", t.TempDir())
	if code != exitError || !strings.Contains(stderr, "no escalation") {
		t.Errorf("code=%d stderr=%q", code, stderr)
	}
}

func TestEscalationsApproveExpiredFails(t *testing.T) {
	root := t.TempDir()
	r := parkRecord(t, root, "S-1", time.Hour)
	code, _, stderr := cli("escalations", "approve", r.ID, "--log-dir", root)
	if code != exitError || !strings.Contains(stderr, "expired") {
		t.Errorf("code=%d stderr=%q", code, stderr)
	}
}

func TestEscalationsApproveTwiceFails(t *testing.T) {
	root := t.TempDir()
	r := parkRecord(t, root, "S-1", 0)
	cli("escalations", "approve", r.ID, "--log-dir", root)
	code, _, stderr := cli("escalations", "approve", r.ID, "--log-dir", root)
	if code != exitError || !strings.Contains(stderr, "already approved") {
		t.Errorf("code=%d stderr=%q", code, stderr)
	}
}

func TestEscalationsMissingIDIsUsage(t *testing.T) {
	if code, _, _ := cli("escalations", "approve", "--log-dir", t.TempDir()); code != exitUsage {
		t.Errorf("exit = %d, want %d", code, exitUsage)
	}
}
