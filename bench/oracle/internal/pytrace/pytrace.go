// Package pytrace runs the Python runtime-trace oracle (design §6,
// D-O5): `py/trace_oracle.py` under the target's own interpreter, which
// runs the target's pytest suite under sys.monitoring and writes the
// lane's OracleExport with kind "trace". The tracer must be Python (the
// split-by-focus rule, D1); this package is the harness's handle on it —
// the subcommand and the fixture test share it.
package pytrace

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/majax7714/Hobbes/bench/oracle/internal/contain"
	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

// Options is one trace cell.
type Options struct {
	Repo   string // repo root
	Module string // repo-relative directory of the cell ("" or "." for the repo)
	// Python is the interpreter command that can import the target and
	// pytest — e.g. []string{"uv", "run", "--project", "pipeline", "python"}.
	// Default: python3 on PATH.
	Python  []string
	Runs    int      // suite runs unioned (default 1)
	SysPath []string // repo-relative dirs prepended to sys.path (src layouts without an install)
	Label   string   // how the suite was invoked, for the record
	Pytest  []string // pytest arguments
	Script  string   // path to trace_oracle.py (default: beside this package's source)
	Out     string   // where the export is written
}

// Run executes the tracer and reads its export back.
func Run(o Options) (*edges.OracleExport, error) {
	script := o.Script
	if script == "" {
		script = DefaultScript()
	}
	py := o.Python
	if len(py) == 0 {
		py = []string{"python3"}
	}
	if o.Runs == 0 {
		o.Runs = 1
	}
	if o.Out == "" {
		return nil, fmt.Errorf("pytrace: Out is required")
	}
	module := o.Module
	if module == "" {
		module = "."
	}
	args := append([]string{}, py[1:]...)
	args = append(args, script, "--repo", o.Repo, "--module", module, "--out", o.Out, "--runs", fmt.Sprint(o.Runs))
	for _, p := range o.SysPath {
		args = append(args, "--sys-path", p)
	}
	if o.Label != "" {
		args = append(args, "--label", o.Label)
	}
	args = append(args, "--")
	args = append(args, o.Pytest...)
	// The suite runs inside the sandbox image (ADR-092 phase 2): the
	// repo as an overlay at its host path, the export's directory rw,
	// the tracer script and the interpreter's install chain ro. No
	// network. The interpreter is a path (the target's venv python) —
	// `uv run` is not in the image and would resolve to that path anyway.
	repo, err := filepath.Abs(o.Repo)
	if err != nil {
		return nil, err
	}
	dir := repo
	if module != "." {
		dir = filepath.Join(repo, module)
	}
	outAbs, _ := filepath.Abs(o.Out)
	scriptAbs, _ := filepath.Abs(script)
	ro := []string{filepath.Dir(scriptAbs)}
	if filepath.IsAbs(py[0]) {
		ro = append(ro, filepath.Dir(filepath.Dir(py[0])))
		ro = append(ro, contain.InterpreterMounts(py[0])...)
	}
	plan, err := contain.New("py-trace", append([]string{py[0]}, args...), dir, repo,
		[]string{filepath.Dir(outAbs)}, ro, []string{"HOBBES_SCIP=0"})
	if err != nil {
		return nil, err
	}
	outcome, err := contain.Run(plan)
	if err != nil {
		return nil, fmt.Errorf("pytrace: %s %s: %w", py[0], strings.Join(args, " "), err)
	}
	raw, err := os.ReadFile(o.Out)
	if err != nil {
		return nil, err
	}
	var out edges.OracleExport
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, fmt.Errorf("%s: %w", o.Out, err)
	}
	// The record says where the suite ran; rewritten so oracle.json
	// carries it into the grade.
	out.Containment = outcome.Containment()
	if data, err := json.MarshalIndent(&out, "", " "); err == nil {
		_ = os.WriteFile(o.Out, data, 0o644)
	}
	return &out, nil
}

// DefaultScript is py/trace_oracle.py relative to this source tree — the
// binary is built from the tree by run-cell.sh, so the path holds.
func DefaultScript() string {
	_, file, _, _ := runtime.Caller(0)
	return filepath.Join(filepath.Dir(file), "..", "..", "py", "trace_oracle.py")
}
