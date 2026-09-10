// Package shape holds the callee-shape bucket tools (docs/oracle/
// oracle-misses.md): shapes.mjs, the checker's reading of every call
// site's callee in a TS zone (ts-morph from tsextract/node_modules),
// and bucket.py, a cell's misses joined to that record and to lane A's
// facts, bucketed by shape, with the collapsed recall. Each carries its
// own suite beside it — bucket_test.py (stdlib unittest) and
// shapes.test.mjs (node:test) — which this test runs, so `go test ./...`
// in bench/oracle runs them wherever python3 and node are. Bench
// tooling, never product.
package shape

import (
	"os"
	"os/exec"
	"testing"
)

func TestBucketSuite(t *testing.T) {
	cmd := exec.Command("python3", "-m", "unittest", "-v", "bucket_test")
	if b, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("bucket_test: %v\n%s", err, b)
	}
}

func TestShapesSuite(t *testing.T) {
	if _, err := os.Stat("../../../tsextract/node_modules/ts-morph"); err != nil {
		t.Skip("shapes.mjs reads ts-morph from tsextract/node_modules: `cd tsextract && npm install`")
	}
	cmd := exec.Command("node", "--test", "shapes.test.mjs")
	if b, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("shapes.test.mjs: %v\n%s", err, b)
	}
}
