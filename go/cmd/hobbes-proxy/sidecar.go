package main

import (
	"context"
	"flag"
	"fmt"
	"io"
	"net"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"

	"github.com/majax7714/Hobbes/go/internal/egress"
	"github.com/majax7714/Hobbes/go/internal/sink"
)

// allowFlag collects the repeatable --allow flag.
type allowFlag []string

func (a *allowFlag) String() string     { return strings.Join(*a, ",") }
func (a *allowFlag) Set(v string) error { *a = append(*a, v); return nil }

// sidecarConfig is serveSidecar's input: the listeners and the egress
// destination runSidecar has already opened, split out so the tests can
// run the sidecar in-process without a signal handler.
type sidecarConfig struct {
	Dir, Session, Role string
	SinkLn             net.Listener
	EgressLn           net.Listener // nil when --allow was not given
	Allow              egress.Allowlist
	EgressLog          io.Writer // nil when EgressLn is nil
}

// runSidecar is `hobbes-proxy sidecar`: a session's records sink and its
// allowlisted route out, in one container of its own (ADR-112). The
// doer's container mounts no part of the session dir read-write and
// writes none of its own records; this is the only writer of
// flight.jsonl, escalations/, mail.jsonl and, with --allow, egress.jsonl.
// It serves until SIGTERM or SIGINT.
func runSidecar(args []string, stderr io.Writer) int {
	fs := flag.NewFlagSet("sidecar", flag.ContinueOnError)
	fs.SetOutput(stderr)
	dirFlag := fs.String("dir", "", "the session dir to write records under (required)")
	sessionFlag := fs.String("session", "", "session id (required)")
	roleFlag := fs.String("role", "", "session role (required)")
	sinkListenFlag := fs.String("sink-listen", "0.0.0.0:"+sink.DefaultPort, "address the flight sink listens on")
	var allow allowFlag
	fs.Var(&allow, "allow", "host or host:port a session may reach (repeatable; 443 by default)")
	listenFlag := fs.String("listen", "0.0.0.0:3128", "address the egress proxy listens on")
	if err := fs.Parse(args); err != nil {
		return exitUsage
	}
	if *dirFlag == "" || *sessionFlag == "" || *roleFlag == "" {
		fmt.Fprintf(stderr, "hobbes-proxy sidecar: --dir, --session and --role are required\n\n%s", usage)
		return exitUsage
	}

	var list egress.Allowlist
	if len(allow) > 0 {
		var err error
		list, err = egress.ParseAllowlist(allow)
		if err != nil {
			fmt.Fprintf(stderr, "hobbes-proxy sidecar: %v\n", err)
			return exitUsage
		}
	}

	sinkLn, err := net.Listen("tcp", *sinkListenFlag)
	if err != nil {
		fmt.Fprintf(stderr, "hobbes-proxy sidecar: %v\n", err)
		return exitError
	}

	cfg := sidecarConfig{Dir: *dirFlag, Session: *sessionFlag, Role: *roleFlag, SinkLn: sinkLn}
	fmt.Fprintf(stderr, "hobbes-proxy sidecar: session %s role %s dir %s\nhobbes-proxy sidecar: sink on %s\n",
		*sessionFlag, *roleFlag, *dirFlag, sinkLn.Addr())

	if len(allow) > 0 {
		egressLn, err := net.Listen("tcp", *listenFlag)
		if err != nil {
			fmt.Fprintf(stderr, "hobbes-proxy sidecar: %v\n", err)
			return exitError
		}
		logFile, err := os.OpenFile(filepath.Join(*dirFlag, "egress.jsonl"), os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o600)
		if err != nil {
			fmt.Fprintf(stderr, "hobbes-proxy sidecar: %v\n", err)
			return exitError
		}
		defer logFile.Close()
		cfg.EgressLn, cfg.Allow, cfg.EgressLog = egressLn, list, logFile
		fmt.Fprintf(stderr, "hobbes-proxy sidecar: egress on %s; allow %s\n", egressLn.Addr(), strings.Join(list.Entries(), ", "))
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	if err := serveSidecar(ctx, cfg); err != nil {
		fmt.Fprintf(stderr, "hobbes-proxy sidecar: %v\n", err)
		return exitError
	}
	return exitOK
}

// serveSidecar runs the sink and, when configured, the egress proxy,
// until ctx ends. Both run in this one process (ADR-112), and both or
// neither: when one fails, the other is stopped too, so a sink that
// cannot open its log never leaves the route out serving alone, and the
// launcher sees the failure instead of a silent wait.
func serveSidecar(ctx context.Context, cfg sidecarConfig) error {
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()
	errc := make(chan error, 2)
	go func() {
		errc <- sink.Serve(ctx, cfg.SinkLn, sink.Config{Dir: cfg.Dir, Session: cfg.Session, Role: cfg.Role})
	}()
	if cfg.EgressLn != nil {
		go func() {
			errc <- egress.Serve(ctx, cfg.EgressLn, &egress.Proxy{Allow: cfg.Allow, Log: egress.NewLog(cfg.EgressLog)})
		}()
	} else {
		errc <- nil
	}
	var first error
	for i := 0; i < 2; i++ {
		if err := <-errc; err != nil {
			if first == nil {
				first = err
			}
			cancel()
		}
	}
	return first
}
