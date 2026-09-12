package main

import (
	"context"
	"flag"
	"fmt"
	"io"
	"net"
	"os"
	"os/signal"
	"strings"
	"syscall"

	"github.com/majax7714/Hobbes/go/internal/egress"
)

// allowFlag collects the repeatable --allow flag.
type allowFlag []string

func (a *allowFlag) String() string     { return strings.Join(*a, ",") }
func (a *allowFlag) Set(v string) error { *a = append(*a, v); return nil }

// runEgress is `hobbes-proxy egress`: the session's allowlisted route out
// (ADR-107). hobbes-session runs it in its own container on the session's
// internal network and the egress bridge; it tunnels CONNECT to the listed
// hosts, answers 403 to everything else, and writes one JSONL line per
// decision to --log (default stdout). It serves until SIGTERM or SIGINT.
func runEgress(args []string, stderr io.Writer) int {
	fs := flag.NewFlagSet("egress", flag.ContinueOnError)
	fs.SetOutput(stderr)
	var allow allowFlag
	fs.Var(&allow, "allow", "host or host:port a session may reach (repeatable; 443 by default)")
	listen := fs.String("listen", "0.0.0.0:3128", "address to listen on")
	logPath := fs.String("log", "", "JSONL decision log (default: stdout)")
	if err := fs.Parse(args); err != nil {
		return exitUsage
	}
	if len(allow) == 0 {
		fmt.Fprintf(stderr, "hobbes-proxy egress: --allow is required; a route with no host is --network none\n\n%s", usage)
		return exitUsage
	}
	list, err := egress.ParseAllowlist(allow)
	if err != nil {
		fmt.Fprintf(stderr, "hobbes-proxy egress: %v\n", err)
		return exitUsage
	}
	var w io.Writer = os.Stdout
	if *logPath != "" {
		f, err := os.OpenFile(*logPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o600)
		if err != nil {
			fmt.Fprintf(stderr, "hobbes-proxy egress: %v\n", err)
			return exitError
		}
		defer f.Close()
		w = f
	}
	ln, err := net.Listen("tcp", *listen)
	if err != nil {
		fmt.Fprintf(stderr, "hobbes-proxy egress: %v\n", err)
		return exitError
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	fmt.Fprintf(stderr, "hobbes-proxy egress: listening on %s; allow %s\n", ln.Addr(), strings.Join(list.Entries(), ", "))
	if err := egress.Serve(ctx, ln, &egress.Proxy{Allow: list, Log: egress.NewLog(w)}); err != nil {
		fmt.Fprintf(stderr, "hobbes-proxy egress: %v\n", err)
		return exitError
	}
	return exitOK
}
