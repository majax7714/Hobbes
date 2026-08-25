// Command oracle is the oracle-grading lane's one binary (ADR-089,
// docs/oracle-grading.md): `export` reads a Hobbes graph.json into graded
// edges, `go-rta` runs the Go reachability oracle on one module, and
// `grade` matches the two and prints the cell's report. A cell is data —
// a repo, a module directory, a graph — never a script of its own.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
	"github.com/majax7714/Hobbes/bench/oracle/internal/export"
	"github.com/majax7714/Hobbes/bench/oracle/internal/gorta"
	"github.com/majax7714/Hobbes/bench/oracle/internal/grade"
)

func main() {
	if len(os.Args) < 2 {
		usage()
	}
	var err error
	switch os.Args[1] {
	case "export":
		err = runExport(os.Args[2:])
	case "go-rta":
		err = runGoRTA(os.Args[2:])
	case "grade":
		err = runGrade(os.Args[2:])
	default:
		usage()
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, "oracle:", err)
		os.Exit(1)
	}
}

func usage() {
	fmt.Fprintln(os.Stderr, `usage:
  oracle export --graph .hobbes/derived/graph.json --module go [--lang go|ts] [--out hobbes.json]
  node ts/tsc-oracle.mjs --repo . --zone web --out oracle.json      (the TypeScript oracle)
  oracle go-rta --repo . --module go [--tags a,b] [--out oracle.json]
  oracle grade  --hobbes hobbes.json --oracle oracle.json [--json report.json]`)
	os.Exit(2)
}

func runExport(args []string) error {
	fs := flag.NewFlagSet("export", flag.ExitOnError)
	graph := fs.String("graph", ".hobbes/derived/graph.json", "Hobbes graph.json")
	module := fs.String("module", "", "repo-relative module directory (cell)")
	lang := fs.String("lang", "go", "go|ts — the extension set of the cell")
	exclude := fs.String("exclude", "", "comma-separated repo-relative directories to drop (nested modules)")
	out := fs.String("out", "", "output path (default stdout)")
	fs.Parse(args)
	h, err := export.FromFile(*graph, *module, *lang, splitComma(*exclude)...)
	if err != nil {
		return err
	}
	return write(*out, h)
}

func runGoRTA(args []string) error {
	fs := flag.NewFlagSet("go-rta", flag.ExitOnError)
	repo := fs.String("repo", ".", "repo root")
	module := fs.String("module", "", "repo-relative Go module directory (cell)")
	tags := fs.String("tags", "", "comma-separated extra build tags")
	noTests := fs.Bool("no-tests", false, "load without test packages (roots = binaries only; the cell records it)")
	pkgsFlag := fs.String("packages", "", "comma-separated package patterns relative to the module (default ./...)")
	exclFlag := fs.String("exclude", "", "comma-separated repo-relative directories to drop (nested modules), as for export")
	out := fs.String("out", "", "output path (default stdout)")
	fs.Parse(args)
	o := gorta.Options{Repo: *repo, Module: *module, NoTests: *noTests, Packages: splitComma(*pkgsFlag), Exclude: splitComma(*exclFlag)}
	if *tags != "" {
		o.Tags = splitComma(*tags)
	}
	res, err := gorta.Run(o)
	if err != nil {
		return err
	}
	return write(*out, res)
}

func runGrade(args []string) error {
	fs := flag.NewFlagSet("grade", flag.ExitOnError)
	hp := fs.String("hobbes", "", "HobbesExport JSON from `oracle export`")
	op := fs.String("oracle", "", "OracleExport JSON from an oracle subcommand")
	jp := fs.String("json", "", "write the full report (rows, misses) here")
	fs.Parse(args)
	var h edges.HobbesExport
	var o edges.OracleExport
	if err := read(*hp, &h); err != nil {
		return err
	}
	if err := read(*op, &o); err != nil {
		return err
	}
	r := grade.Grade(&h, &o)
	grade.Print(os.Stdout, r)
	if *jp != "" {
		return write(*jp, r)
	}
	return nil
}

func read(path string, v any) error {
	if path == "" {
		return fmt.Errorf("missing input path")
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(raw, v)
}

func write(path string, v any) error {
	raw, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	if path == "" {
		_, err = os.Stdout.Write(raw)
		return err
	}
	return os.WriteFile(path, raw, 0o644)
}

func splitComma(s string) []string {
	var out []string
	start := 0
	for i := 0; i <= len(s); i++ {
		if i == len(s) || s[i] == ',' {
			if i > start {
				out = append(out, s[start:i])
			}
			start = i + 1
		}
	}
	return out
}
