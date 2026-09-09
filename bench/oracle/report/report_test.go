// Package report holds render.py — the comparative graphics regenerated
// from the cell records (ADR-102) — and this test, which fails when the
// committed data or graphics drift from docs/oracle-cells/: a regraded
// cell without a regenerated picture is a P8 violation with a picture on
// it. python3 only.
package report

import (
	"os/exec"
	"testing"
)

func TestGraphicsMatchTheCellRecords(t *testing.T) {
	cmd := exec.Command("python3", "render.py", "check")
	if b, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("render.py check: %v\n%s\n(run `python3 bench/oracle/report/render.py cells` then `render` and commit the result)", err, b)
	}
}
