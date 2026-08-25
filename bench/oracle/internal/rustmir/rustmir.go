// Package rustmir runs the Rust MIR resolution oracle (design §7, D-O6):
// `cargo check --all-targets` on one cargo package with the mir-oracle
// driver as RUSTC_WRAPPER, then merges the driver's per-target files into
// the lane's OracleExport (kind "resolution"). The driver must be Rust
// (rustc_private, D1); this package is the harness's handle on it.
package rustmir

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

// Options is one Rust cell: a cargo package directory inside the repo.
type Options struct {
	Repo    string // repo root
	Module  string // repo-relative directory holding Cargo.toml ("" or "." for the root)
	Driver  string // path to the built mir-oracle binary
	Out     string // directory for the per-target files and the cargo target dir
	Cargo   []string
	Feature []string // extra --features
}

type driverFile struct {
	Crate     string       `json:"crate"`
	Rustc     string       `json:"rustc"`
	Generated int          `json:"generated_sites"`
	Files     []string     `json:"files"`
	Sites     []edges.Site `json:"sites"`
}

// Run checks the package under the driver and merges the result. The
// cargo target dir is fresh under Out on every run, so every workspace
// target is recompiled and the wrapper sees each one (a cached check
// would skip the crate and the cell would read empty).
func Run(o Options) (*edges.OracleExport, error) {
	if o.Driver == "" {
		return nil, fmt.Errorf("rustmir: Driver is required")
	}
	repo, err := filepath.Abs(o.Repo)
	if err != nil {
		return nil, err
	}
	module := o.Module
	if module == "." {
		module = ""
	}
	dir := filepath.Join(repo, module)
	if _, err := os.Stat(filepath.Join(dir, "Cargo.toml")); err != nil {
		return nil, fmt.Errorf("rustmir: %s has no Cargo.toml", dir)
	}
	sites := filepath.Join(o.Out, "mir-sites")
	os.RemoveAll(sites)
	if err := os.MkdirAll(sites, 0o755); err != nil {
		return nil, err
	}
	target := filepath.Join(o.Out, "cargo-target")
	os.RemoveAll(target)
	cargo := o.Cargo
	if len(cargo) == 0 {
		cargo = []string{"cargo", "+nightly"}
	}
	args := append([]string{}, cargo[1:]...)
	args = append(args, "check", "--all-targets")
	if len(o.Feature) > 0 {
		args = append(args, "--features", strings.Join(o.Feature, ","))
	}
	cmd := exec.Command(cargo[0], args...)
	cmd.Dir = dir
	driver, _ := filepath.Abs(o.Driver)
	cmd.Env = append(os.Environ(),
		"RUSTC_WRAPPER="+driver,
		"HOBBES_ORACLE_OUT="+sites,
		"HOBBES_ORACLE_REPO="+repo,
		"CARGO_TARGET_DIR="+target,
	)
	if sysroot := rustcSysroot(cargo); sysroot != "" {
		cmd.Env = append(cmd.Env, "LD_LIBRARY_PATH="+filepath.Join(sysroot, "lib")+":"+os.Getenv("LD_LIBRARY_PATH"))
	}
	cmd.Stdout, cmd.Stderr = os.Stdout, os.Stderr
	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("rustmir: %s %s in %s: %w", cargo[0], strings.Join(args, " "), dir, err)
	}
	return Merge(sites, module)
}

// Merge unions the driver's per-target files: sites keyed by (path,
// line, col) with their targets unioned (a lib compiled for itself and
// again for its tests reports the same sites twice); files unioned;
// each target's label a root.
func Merge(dir, module string) (*edges.OracleExport, error) {
	names, err := filepath.Glob(filepath.Join(dir, "*.json"))
	if err != nil {
		return nil, err
	}
	if len(names) == 0 {
		return nil, fmt.Errorf("rustmir: the driver wrote nothing under %s (no workspace target compiled?)", dir)
	}
	sort.Strings(names)
	out := &edges.OracleExport{Kind: "resolution", Module: module, Tags: []string{}, Excluded: map[string]int{}}
	files := map[string]bool{}
	type key struct {
		path      string
		line, col int
	}
	merged := map[key]*edges.Site{}
	var order []key
	for _, n := range names {
		raw, err := os.ReadFile(n)
		if err != nil {
			return nil, err
		}
		var d driverFile
		if err := json.Unmarshal(raw, &d); err != nil {
			return nil, fmt.Errorf("%s: %w", n, err)
		}
		out.Oracle = "rustc-mir " + d.Rustc
		out.Roots = append(out.Roots, d.Crate)
		out.Excluded["generated"] += d.Generated
		for _, f := range d.Files {
			files[f] = true
		}
		for i := range d.Sites {
			s := d.Sites[i]
			k := key{s.Pos.Path, s.Pos.Line, s.Col}
			m, ok := merged[k]
			if !ok {
				c := s
				merged[k] = &c
				order = append(order, k)
				continue
			}
			for _, t := range s.Targets {
				if !hasTarget(m.Targets, t) {
					m.Targets = append(m.Targets, t)
				}
			}
			if m.Interface == nil && s.Interface != nil {
				m.Interface = s.Interface
			}
		}
	}
	sort.Slice(order, func(i, j int) bool {
		a, b := order[i], order[j]
		if a.path != b.path {
			return a.path < b.path
		}
		if a.line != b.line {
			return a.line < b.line
		}
		return a.col < b.col
	})
	for _, k := range order {
		out.Sites = append(out.Sites, *merged[k])
	}
	for f := range files {
		out.Files = append(out.Files, f)
	}
	sort.Strings(out.Files)
	return out, nil
}

func hasTarget(ts []edges.Target, t edges.Target) bool {
	for _, x := range ts {
		if x.Pos == t.Pos && x.Name == t.Name {
			return true
		}
	}
	return false
}

func rustcSysroot(cargo []string) string {
	args := []string{}
	for _, a := range cargo[1:] {
		if strings.HasPrefix(a, "+") {
			args = append(args, a)
		}
	}
	args = append(args, "--print", "sysroot")
	out, err := exec.Command("rustc", args...).Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(out))
}
