package grade

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"testing"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

// The two JavaScript shapes the Preact cell's first triage charged to
// the oracle (§10.22), each with its own file so the fixture says which
// defect it holds:
//
//   - H-34: `lib/use.js` calls `area`, which `require("./shape")`
//     resolves to `lib/shape.d.ts` — the repo types its own JavaScript,
//     as Preact does in `src/index.d.ts`. The target is keyed
//     repo-relative and is not external, so it meets the Hobbes edge to
//     the same line of the same file.
//   - H-35: `lib/typed.js` calls `twice`, a function carrying a JSDoc
//     `@type` function type. The resolved signature's declaration is the
//     type node inside the comment (line 1); the callee is the function
//     it is attached to (line 2).
//
// Before the fix the oracle keyed `lib/use.js:2` to the *absolute*
// `…/lib/shape.d.ts:1` with `external: true`, and `lib/typed.js:5` to
// `lib/typed.js:1` as a `closure`.
func TestJsdeclInRepoDeclarationAndJSDocType(t *testing.T) {
	o := runJSOracleAt(t, "../../testdata/jsdecl", "--no-tsconfig")
	if o.Kind != "resolution" {
		t.Fatalf("kind: %s", o.Kind)
	}
	// A `.d.ts` contributes no sites and is not a graded file, in-repo or
	// not: the site walk still skips it.
	wantFiles := []string{"lib/shape.js", "lib/typed.js", "lib/use.js"}
	if fmt.Sprint(o.Files) != fmt.Sprint(wantFiles) {
		t.Fatalf("files: %v", o.Files)
	}

	for _, tc := range []struct {
		site   string
		target string
		kind   string
	}{
		{"lib/use.js:2", "lib/shape.d.ts:1", "function"}, // H-34
		{"lib/typed.js:5", "lib/typed.js:2", "function"}, // H-35
	} {
		t.Run(tc.site, func(t *testing.T) {
			var s edges.Site
			for _, cand := range o.Sites {
				if cand.Pos.Key() == tc.site {
					s = cand
				}
			}
			if s.Pos.Key() != tc.site {
				t.Fatalf("no site at %s; the oracle read %v", tc.site, siteKeys(o))
			}
			if len(s.Targets) != 1 {
				t.Fatalf("targets: %+v", s.Targets)
			}
			tg := s.Targets[0]
			if tg.Pos.Key() != tc.target {
				t.Errorf("target %s, want %s", tg.Pos.Key(), tc.target)
			}
			if tg.External {
				t.Errorf("a declaration inside the repo is in-repo: %+v", tg)
			}
			if tg.Kind != tc.kind || tg.Closure {
				t.Errorf("kind %q closure %v, want %q and not a closure", tg.Kind, tg.Closure, tc.kind)
			}
			if c := missClass(s, tg); c != "static→"+tc.kind {
				t.Errorf("miss class: %s", c)
			}
		})
	}
}

func siteKeys(o *edges.OracleExport) []string {
	keys := make([]string, 0, len(o.Sites))
	for _, s := range o.Sites {
		keys = append(keys, s.Pos.Key())
	}
	return keys
}

// runJSOracle's sibling for a fixture that is the oracle's own rather
// than the pipeline's: it takes the repo path instead of a name under
// `fixtures`.
func runJSOracleAt(t *testing.T, repo string, extra ...string) *edges.OracleExport {
	t.Helper()
	needNode(t)
	out := filepath.Join(t.TempDir(), "oracle.json")
	argv := append([]string{"../../ts/tsc-oracle.mjs", "--repo", repo, "--zone", ".", "--out", out}, extra...)
	cmd := exec.Command("node", argv...)
	if b, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("tsc-oracle: %v\n%s", err, b)
	}
	raw, err := os.ReadFile(out)
	if err != nil {
		t.Fatal(err)
	}
	var o edges.OracleExport
	if err := json.Unmarshal(raw, &o); err != nil {
		t.Fatal(err)
	}
	return &o
}
