// Command hobbes-proxy is the per-session tool proxy daemon (M4, ADR-014):
// an MCP server over stdio that exposes one tool, exec, gated by the merged
// Hobbes policy chain and logged to the session's flight recorder. The
// session wrapper lists it in the sandboxed Claude Code's MCP config; one
// proxy process serves one session and dies with it. The escalations
// subcommand is the human side of the queue (ADR-016): list parked
// commands, approve or deny them by id.
//
// Usage:
//
//	hobbes-proxy serve --repo DIR --role ROLE [--session ID] [--box FILE]
//	                   [--log-dir DIR] [--timeout DUR] [--escalation-timeout DUR]
//	hobbes-proxy escalations list [--all] [--log-dir DIR]
//	hobbes-proxy escalations approve <id> [--log-dir DIR]
//	hobbes-proxy escalations deny <id> [--log-dir DIR]
//
// For serve, stdout carries the MCP protocol; all diagnostics go to
// stderr. Exit codes: 0 ok · 1 runtime error · 2 usage.
package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/user"
	"path/filepath"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/majax7714/Hobbes/go/internal/escalation"
	"github.com/majax7714/Hobbes/go/internal/proxy"
	"github.com/majax7714/Hobbes/go/internal/recorder"
)

const (
	exitOK    = 0
	exitError = 1
	exitUsage = 2
)

const usage = `usage: hobbes-proxy <serve | escalations> [flags]

serve --repo DIR --role ROLE   run the tool proxy for one agent session
  [--knowledge-only]           (knowledge tools only: for a host session
                               that keeps its own shell, ADR-087):
  an MCP server on stdio exposing exec, policy-checked
  (allow | deny | escalate) and logged to the session flight recorder
  (~/.hobbes/sessions/<session>/flight.jsonl).
    --session ID              session id (default: generated S-<utc>-<rand>)
    --box FILE                box policy (default: ~/.hobbes/box.policy if present)
    --log-dir DIR             session-state root (default: ~/.hobbes/sessions)
    --timeout DUR             per-command wall clock (default 10m)
    --escalation-timeout DUR  park deadline, expires to deny (default 30m)
    --agent-dir DIR           derived agent dir (ADR-054): policy.yaml joins the
                              chain as its agent level; context.json, if present,
                              tags out-of-manifest knowledge queries as context
                              faults; adds the reflect tool's inbox channel

escalations [list | approve <id> | deny <id>]   the human side of the
  queue: parked commands across all sessions, oldest first.
    --all           list resolved records too
    --log-dir DIR   session-state root (default: ~/.hobbes/sessions)
`

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

// run dispatches subcommands. Split from main for testability.
func run(args []string, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		fmt.Fprint(stderr, usage)
		return exitUsage
	}
	switch args[0] {
	case "serve":
		return runServe(args[1:], stderr)
	case "escalations":
		return runEscalations(args[1:], stdout, stderr)
	case "help", "-h", "--help":
		fmt.Fprint(stderr, usage)
		return exitOK
	default:
		fmt.Fprintf(stderr, "hobbes-proxy: unknown command %q\n\n%s", args[0], usage)
		return exitUsage
	}
}

// runServe validates flags, opens the recorder, and serves MCP on stdio.
func runServe(args []string, stderr io.Writer) int {
	cfg, logPath, err := parseServe(args, stderr)
	if err != nil {
		if errors.Is(err, flag.ErrHelp) || errors.Is(err, errUsage) {
			return exitUsage
		}
		fmt.Fprintf(stderr, "hobbes-proxy serve: %v\n", err)
		return exitError
	}

	rec, err := recorder.Open(logPath)
	if err != nil {
		fmt.Fprintf(stderr, "hobbes-proxy serve: %v\n", err)
		return exitError
	}
	defer rec.Close()
	cfg.Rec = rec

	server, err := proxy.New(cfg)
	if err != nil {
		fmt.Fprintf(stderr, "hobbes-proxy serve: %v\n", err)
		return exitError
	}

	fmt.Fprintf(stderr, "hobbes-proxy: session %s role %s repo %s\nhobbes-proxy: flight log %s\n",
		cfg.Session, cfg.Role, cfg.RepoRoot, logPath)
	if err := server.MCP().Run(context.Background(), &mcp.StdioTransport{}); err != nil {
		fmt.Fprintf(stderr, "hobbes-proxy serve: %v\n", err)
		return exitError
	}
	return exitOK
}

// errUsage marks flag-validation failures whose message is already printed.
var errUsage = errors.New("usage")

// parseServe turns serve flags into a proxy config and flight-log path.
func parseServe(args []string, stderr io.Writer) (proxy.Config, string, error) {
	fs := flag.NewFlagSet("serve", flag.ContinueOnError)
	fs.SetOutput(stderr)
	repoFlag := fs.String("repo", "", "repo root (required)")
	roleFlag := fs.String("role", "", "session role (required)")
	sessionFlag := fs.String("session", "", "session id (default: generated)")
	boxFlag := fs.String("box", "", "box policy path")
	logDirFlag := fs.String("log-dir", "", "session-state root (default: ~/.hobbes/sessions)")
	timeoutFlag := fs.Duration("timeout", proxy.DefaultTimeout, "per-command wall clock")
	escalationFlag := fs.Duration("escalation-timeout", proxy.DefaultEscalationTimeout,
		"park deadline, expires to deny")
	agentDirFlag := fs.String("agent-dir", "", "derived agent dir (policy.yaml, context.json)")
	knowledgeOnlyFlag := fs.Bool("knowledge-only", false,
		"serve only the read-only knowledge tools; exec and reflect are absent (ADR-087)")
	if err := fs.Parse(args); err != nil {
		return proxy.Config{}, "", errUsage
	}

	if *repoFlag == "" || *roleFlag == "" {
		fmt.Fprintf(stderr, "hobbes-proxy serve: --repo and --role are required\n\n%s", usage)
		return proxy.Config{}, "", errUsage
	}
	repoRoot, err := filepath.Abs(*repoFlag)
	if err != nil {
		return proxy.Config{}, "", err
	}
	if info, err := os.Stat(repoRoot); err != nil || !info.IsDir() {
		return proxy.Config{}, "", fmt.Errorf("repo root %s is not a directory", repoRoot)
	}

	boxPath, err := resolveBoxPath(*boxFlag)
	if err != nil {
		return proxy.Config{}, "", err
	}

	session := *sessionFlag
	if session == "" {
		session, err = generateSessionID()
		if err != nil {
			return proxy.Config{}, "", err
		}
	}

	logDir, err := sessionRoot(*logDirFlag)
	if err != nil {
		return proxy.Config{}, "", err
	}
	sessionDir := filepath.Join(logDir, session)

	agentDir := ""
	if *agentDirFlag != "" {
		agentDir, err = filepath.Abs(*agentDirFlag)
		if err != nil {
			return proxy.Config{}, "", err
		}
		if info, err := os.Stat(agentDir); err != nil || !info.IsDir() {
			return proxy.Config{}, "", fmt.Errorf("agent dir %s is not a directory", agentDir)
		}
	}

	cfg := proxy.Config{
		Session:           session,
		Role:              *roleFlag,
		RepoRoot:          repoRoot,
		BoxPath:           boxPath,
		SessionDir:        sessionDir,
		Timeout:           *timeoutFlag,
		EscalationTimeout: *escalationFlag,
		AgentDir:          agentDir,
		KnowledgeOnly:     *knowledgeOnlyFlag,
	}
	return cfg, filepath.Join(sessionDir, "flight.jsonl"), nil
}

// sessionRoot resolves the session-state root shared by serve and the
// escalations CLI (ADR-014/016).
func sessionRoot(flagValue string) (string, error) {
	if flagValue != "" {
		return flagValue, nil
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("no home directory for the default --log-dir: %w", err)
	}
	return filepath.Join(home, ".hobbes", "sessions"), nil
}

// runEscalations implements the human side of the queue (ADR-016):
// list parked commands, approve or deny one by id.
func runEscalations(args []string, stdout, stderr io.Writer) int {
	sub := "list"
	if len(args) > 0 && args[0][0] != '-' {
		sub, args = args[0], args[1:]
	}
	// The id must come off before flag parsing: the flag package stops
	// at the first positional, so "approve E-x --log-dir D" would
	// otherwise leave --log-dir unparsed.
	id := ""
	if (sub == "approve" || sub == "deny") && len(args) > 0 && args[0][0] != '-' {
		id, args = args[0], args[1:]
	}

	fs := flag.NewFlagSet("escalations", flag.ContinueOnError)
	fs.SetOutput(stderr)
	logDirFlag := fs.String("log-dir", "", "session-state root (default: ~/.hobbes/sessions)")
	allFlag := fs.Bool("all", false, "list resolved records too")
	if err := fs.Parse(args); err != nil {
		return exitUsage
	}
	root, err := sessionRoot(*logDirFlag)
	if err != nil {
		fmt.Fprintf(stderr, "hobbes-proxy escalations: %v\n", err)
		return exitError
	}

	switch sub {
	case "list":
		return listEscalations(root, *allFlag, stdout, stderr)
	case "approve", "deny":
		if id == "" {
			fmt.Fprintf(stderr, "hobbes-proxy escalations %s: missing escalation id\n\n%s", sub, usage)
			return exitUsage
		}
		verdict := escalation.Approved
		if sub == "deny" {
			verdict = escalation.Denied
		}
		return resolveEscalation(root, id, verdict, stdout, stderr)
	default:
		fmt.Fprintf(stderr, "hobbes-proxy escalations: unknown subcommand %q\n\n%s", sub, usage)
		return exitUsage
	}
}

// listEscalations prints the queue, pending first by default.
func listEscalations(root string, all bool, stdout, stderr io.Writer) int {
	items, err := escalation.List(root)
	if err != nil {
		fmt.Fprintf(stderr, "hobbes-proxy escalations list: %v\n", err)
		return exitError
	}
	now := time.Now()
	shown := 0
	for _, it := range items {
		r := it.Record
		status := r.EffectiveStatus(now)
		if !all && status != escalation.Pending {
			continue
		}
		shown++
		detail := ""
		switch status {
		case escalation.Pending:
			detail = fmt.Sprintf("%s left", time.Until(r.Deadline()).Round(time.Second))
		case escalation.Approved, escalation.Denied:
			detail = "by " + r.Approver
		}
		fmt.Fprintf(stdout, "%s  %-8s %-12s %s [%s]  %s\n",
			r.ID, status, detail, r.Session, r.Role, r.Command)
	}
	if shown == 0 {
		if all {
			fmt.Fprintln(stdout, "no escalations recorded")
		} else {
			fmt.Fprintln(stdout, "no pending escalations")
		}
	}
	return exitOK
}

// resolveEscalation applies a human verdict to one record.
func resolveEscalation(root, id string, verdict escalation.Status, stdout, stderr io.Writer) int {
	item, err := escalation.FindByID(root, id)
	if err != nil {
		fmt.Fprintf(stderr, "hobbes-proxy escalations: %v\n", err)
		return exitError
	}
	r, err := escalation.Resolve(item.Path, verdict, approverName(), time.Now())
	if err != nil {
		fmt.Fprintf(stderr, "hobbes-proxy escalations: %v\n", err)
		return exitError
	}
	if verdict == escalation.Approved {
		fmt.Fprintf(stdout, "approved %s — session %s will run: %s\n", r.ID, r.Session, r.Command)
	} else {
		fmt.Fprintf(stdout, "denied %s — session %s will NOT run: %s\n", r.ID, r.Session, r.Command)
	}
	return exitOK
}

// approverName identifies the resolving human for the audit trail (§9).
func approverName() string {
	if u, err := user.Current(); err == nil && u.Username != "" {
		return u.Username
	}
	if name := os.Getenv("USER"); name != "" {
		return name
	}
	return "unknown"
}

// generateSessionID makes a sortable, collision-safe id (ADR-014).
func generateSessionID() (string, error) {
	var b [2]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "", err
	}
	return fmt.Sprintf("S-%s-%s",
		time.Now().UTC().Format("20060102T150405Z"), hex.EncodeToString(b[:])), nil
}

// resolveBoxPath applies ADR-003's box policy rules (mirrors
// hobbes-policy): an explicit path must exist; the ~/.hobbes/box.policy
// default is skipped when absent.
func resolveBoxPath(flagValue string) (string, error) {
	if flagValue != "" {
		if _, err := os.Stat(flagValue); err != nil {
			return "", fmt.Errorf("box policy %s: %w", flagValue, err)
		}
		return flagValue, nil
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return "", nil // no home, no default box policy
	}
	def := filepath.Join(home, ".hobbes", "box.policy")
	if _, err := os.Stat(def); errors.Is(err, os.ErrNotExist) {
		return "", nil
	}
	return def, nil
}
