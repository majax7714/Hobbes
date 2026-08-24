// Command hobbes-web serves the human surface (M7, architecture §7,
// ADR-022): one local HTTP server per repo exposing the derived
// knowledge layer as JSON and the built single-page app that renders it
// — Graph, Tests, Docs, Diff, and Sessions, with escalation approve/deny
// in the browser.
//
// Usage:
//
//	hobbes-web serve [--repo DIR] [--addr HOST:PORT] [--log-dir DIR]
//
// The server binds loopback only: it has no authentication and can
// resolve escalations, and §7 puts remote access out of scope. Put a
// tunnel in front if you need it elsewhere.
//
// Exit codes: 0 ok · 1 runtime error · 2 usage.
package main

import (
	"errors"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"github.com/majax7714/Hobbes/go/internal/web"
)

const (
	exitOK    = 0
	exitError = 1
	exitUsage = 2
)

const usage = `usage: hobbes-web serve [flags]

Serve the Hobbes human surface for one repo on a local port: the
architecture graph, the behavioral test index, narrative docs with stale
badges and provenance links, the line diff, and a live session monitor
with escalation approve/deny.

flags:
  --repo DIR      repo to serve (default: current directory)
  --addr ADDR     bind address, loopback only (default 127.0.0.1:7777)
  --log-dir DIR   session-state root (default ~/.hobbes/sessions)

Artifacts are read per request, so a re-ingest or narrate pass shows up
on the next reload.
`

func main() { os.Exit(run(os.Args[1:], os.Stdout, os.Stderr)) }

func run(args []string, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		fmt.Fprint(stderr, usage)
		return exitUsage
	}
	switch args[0] {
	case "serve":
		return runServe(args[1:], stdout, stderr)
	case "help", "-h", "--help":
		fmt.Fprint(stdout, usage)
		return exitOK
	default:
		fmt.Fprintf(stderr, "hobbes-web: unknown command %q\n\n%s", args[0], usage)
		return exitUsage
	}
}

func runServe(args []string, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("serve", flag.ContinueOnError)
	fs.SetOutput(stderr)
	fs.Usage = func() { fmt.Fprint(stderr, usage) }
	repo := fs.String("repo", ".", "repo to serve")
	addr := fs.String("addr", "127.0.0.1:7777", "bind address (loopback only)")
	logDir := fs.String("log-dir", "", "session-state root (default ~/.hobbes/sessions)")
	if err := fs.Parse(args); err != nil {
		return exitUsage
	}
	if fs.NArg() > 0 {
		fmt.Fprintf(stderr, "hobbes-web: unexpected argument %q\n", fs.Arg(0))
		return exitUsage
	}

	if err := web.LoopbackAddr(*addr); err != nil {
		fmt.Fprintf(stderr, "hobbes-web: %v\n", err)
		return exitUsage
	}
	root, err := sessionRoot(*logDir)
	if err != nil {
		fmt.Fprintf(stderr, "hobbes-web: %v\n", err)
		return exitError
	}
	srv, err := web.New(web.Config{RepoRoot: *repo, LogDir: root})
	if err != nil {
		fmt.Fprintf(stderr, "hobbes-web: %v\n", err)
		return exitError
	}

	ln, err := net.Listen("tcp", *addr)
	if err != nil {
		fmt.Fprintf(stderr, "hobbes-web: listen: %v\n", err)
		return exitError
	}
	httpSrv := &http.Server{
		Handler:           srv.Handler(),
		ReadHeaderTimeout: 10 * time.Second,
	}

	// Ctrl-C shuts the listener down cleanly; the surface holds no state
	// of its own, so there is nothing else to flush. Registered before
	// the banner so a signal during startup is caught, not fatal.
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)
	defer signal.Stop(stop)

	fmt.Fprintf(stdout, "hobbes-web serving %s on http://%s\n", srv.RepoRoot(), ln.Addr())
	if !web.Built() {
		fmt.Fprintln(stdout, "  note: web app not built into this binary — "+
			"run `cd web && npm install && npm run build`, then rebuild")
	}

	errc := make(chan error, 1)
	go func() { errc <- httpSrv.Serve(ln) }()

	select {
	case <-stop:
		fmt.Fprintln(stdout, "\nhobbes-web: shutting down")
		_ = httpSrv.Close()
		return exitOK
	case err := <-errc:
		if err != nil && !errors.Is(err, http.ErrServerClosed) {
			fmt.Fprintf(stderr, "hobbes-web: %v\n", err)
			return exitError
		}
		return exitOK
	}
}

// sessionRoot resolves --log-dir, defaulting to ~/.hobbes/sessions — the
// same root the proxy writes and the escalations CLI reads.
func sessionRoot(flagValue string) (string, error) {
	if flagValue != "" {
		return filepath.Abs(flagValue)
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("cannot resolve home directory: %w", err)
	}
	return filepath.Join(home, ".hobbes", "sessions"), nil
}
