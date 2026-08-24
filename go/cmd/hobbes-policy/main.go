// Command hobbes-policy is the CLI front-end to the Hobbes policy engine
// (internal/policy). Its one subcommand, resolve, merges the box → repo →
// folder policy chain for a directory and decides a command, printing the
// resolution as JSON on stdout and encoding the decision in the exit code so
// both the Python hobbes CLI and plain shell scripts can gate on it.
//
// Contract (ADR-003):
//
//	hobbes-policy resolve [--repo DIR] [--dir DIR] [--box FILE] <command>...
//
// Exit codes: 0 allow · 10 deny · 20 escalate · 1 runtime error · 2 usage.
package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"github.com/majax7714/Hobbes/go/internal/policy"
)

// Decision-to-exit-code mapping, frozen by ADR-003.
const (
	exitAllow    = 0
	exitError    = 1
	exitUsage    = 2
	exitDeny     = 10
	exitEscalate = 20
)

const usage = `usage: hobbes-policy resolve [flags] <command>...

Resolve a command against the merged Hobbes policy chain
(box -> repo -> folder; deny overrides allow; allow | deny | escalate).

Prints the resolution as JSON on stdout. Exit code encodes the decision:
0 allow, 10 deny, 20 escalate (1 runtime error, 2 usage error).

flags:
  --dir DIR    directory context the command runs in (default ".")
  --repo DIR   repo root (default: auto-detect via .git upward from --dir)
  --box FILE   box policy (default: ~/.hobbes/box.policy if present)
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
	case "resolve":
		return runResolve(args[1:], stdout, stderr)
	case "help", "-h", "--help":
		fmt.Fprint(stdout, usage)
		return 0
	default:
		fmt.Fprintf(stderr, "hobbes-policy: unknown command %q\n\n%s", args[0], usage)
		return exitUsage
	}
}

// runResolve implements the resolve subcommand.
func runResolve(args []string, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("resolve", flag.ContinueOnError)
	fs.SetOutput(stderr)
	repoFlag := fs.String("repo", "", "repo root (default: auto-detect via .git upward from --dir)")
	dirFlag := fs.String("dir", ".", "directory context the command runs in")
	boxFlag := fs.String("box", "", "box policy path (default: ~/.hobbes/box.policy if present)")
	if err := fs.Parse(args); err != nil {
		return exitUsage
	}
	if len(fs.Args()) == 0 {
		fmt.Fprintf(stderr, "hobbes-policy resolve: missing command to resolve\n\n%s", usage)
		return exitUsage
	}
	command := strings.Join(fs.Args(), " ")

	dir, err := filepath.Abs(*dirFlag)
	if err != nil {
		fmt.Fprintf(stderr, "hobbes-policy resolve: %v\n", err)
		return exitError
	}

	repoRoot := *repoFlag
	if repoRoot == "" {
		repoRoot, err = detectRepoRoot(dir)
		if err != nil {
			fmt.Fprintf(stderr, "hobbes-policy resolve: %v (pass --repo explicitly)\n", err)
			return exitError
		}
	}

	boxPath, err := resolveBoxPath(*boxFlag)
	if err != nil {
		fmt.Fprintf(stderr, "hobbes-policy resolve: %v\n", err)
		return exitError
	}

	chain, err := policy.LoadChain(boxPath, repoRoot, dir)
	if err != nil {
		fmt.Fprintf(stderr, "hobbes-policy resolve: %v\n", err)
		return exitError
	}

	result := chain.ResolveCommand(command)
	out, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		fmt.Fprintf(stderr, "hobbes-policy resolve: %v\n", err)
		return exitError
	}
	fmt.Fprintln(stdout, string(out))

	switch result.Decision {
	case policy.Deny:
		return exitDeny
	case policy.Escalate:
		return exitEscalate
	default:
		return exitAllow
	}
}

// detectRepoRoot walks up from dir looking for a .git entry.
func detectRepoRoot(dir string) (string, error) {
	for d := dir; ; d = filepath.Dir(d) {
		if _, err := os.Stat(filepath.Join(d, ".git")); err == nil {
			return d, nil
		}
		if d == filepath.Dir(d) {
			return "", fmt.Errorf("no repo root found: no .git between %s and /", dir)
		}
	}
}

// resolveBoxPath applies ADR-003's box policy rules: an explicitly passed
// path must exist; the ~/.hobbes/box.policy default is skipped when absent.
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
