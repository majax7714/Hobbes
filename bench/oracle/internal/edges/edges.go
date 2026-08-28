// Package edges is the shared shape of the oracle lane (ADR-089): the
// Hobbes-side export of graded call edges and the oracle-side export of
// analysed call sites, both at the design's grain — (call-site position,
// callee declaration identity), positions as repo-relative path + 1-based
// line of the identifier (D-O4).
package edges

import "strings"

// Pos is a repo-relative file and a 1-based line. Columns are not part
// of the grain: Hobbes' evidence carries lines only, so the matcher works
// at line grain and the oracle's column is kept for the triage rows.
type Pos struct {
	Path string `json:"path"`
	Line int    `json:"line"`
}

// Key is the map key form of a Pos.
func (p Pos) Key() string { return p.Path + ":" + itoa(p.Line) }

// HobbesEdge is one graded Hobbes call edge: one evidence line of one
// `calls` symbol edge.
type HobbesEdge struct {
	Site     Pos    `json:"site"`
	Target   Pos    `json:"target"`
	TargetID string `json:"target_id"`
	// TargetKind is the graph symbol's kind at the target ("function",
	// "method", "type", "const", "var", …): the grader reads it to
	// bucket a call through a function-valued variable as abstract
	// (D-O4, 2026-08-28) the way an interface method is.
	TargetKind string   `json:"target_kind,omitempty"`
	Caller     string   `json:"caller"`
	Tier       string   `json:"tier"`
	Lanes      []string `json:"lanes"`
}

// HobbesExport is the Hobbes side of one cell. Excluded counts the
// `calls` edges dropped before grading because the oracle has no call
// there by construction — "macro": a Rust macro invocation drawn to the
// `macro_rules!` symbol, which the compiler expands rather than calls.
type HobbesExport struct {
	SHA      string         `json:"sha"`
	Module   string         `json:"module"`
	Edges    []HobbesEdge   `json:"edges"`
	Excluded map[string]int `json:"excluded,omitempty"`
}

// Target is one callee the oracle resolved a site to. External marks a
// declaration outside the repo (stdlib, module cache) — out of the
// in-repo recall denominator (D-O3), counted separately.
type Target struct {
	Pos      Pos    `json:"pos"`
	Name     string `json:"name"`
	External bool   `json:"external,omitempty"`
	Closure  bool   `json:"closure,omitempty"`
	// Kind is what the declaration is (function, method, class, variable,
	// property, parameter, type-member, closure); oracles that do not
	// classify leave it empty and the grader falls back to named/closure.
	Kind string `json:"kind,omitempty"`
	// Via marks a target the oracle added by a secondary rule — "binding"
	// for the callee's binding declaration behind an anonymous signature.
	Via string `json:"via,omitempty"`
}

// Site is one call site the oracle analysed. Mode is "static" or
// "dynamic" (interface invoke / function value). Interface is set for an
// invoke: the abstract method's declaration, so a Hobbes edge to the
// interface method can be bucketed as abstract rather than contradicted.
type Site struct {
	Pos       Pos      `json:"pos"`
	Col       int      `json:"col"`
	Caller    string   `json:"caller"`
	Mode      string   `json:"mode"`
	Interface *Target  `json:"interface,omitempty"`
	Targets   []Target `json:"targets"`
	// Trace oracles only: how many calls the line made across the runs,
	// and how many of them reached a C callee (no Python declaration to
	// match — counted, never listed as a target).
	Hits     int `json:"hits,omitempty"`
	CCallees int `json:"c_callees,omitempty"`
}

// OracleExport is the oracle side of one cell. Files is every in-repo
// file the oracle loaded; a Hobbes site in a file outside it is
// oracle-silent as not-loaded (build tags, C-26 orphans) — for a trace
// oracle, a module whose body never ran. Kind is "reachability"
// (Go RTA), "resolution" (tsc) or "trace" (the Python interpreter): the
// grader's buckets switch on it (design §3 vs §3.1).
type OracleExport struct {
	Oracle string   `json:"oracle"`
	Kind   string   `json:"kind"`
	Module string   `json:"module"`
	Roots  []string `json:"roots"`
	Tags   []string `json:"tags"`
	Files  []string `json:"files"`
	Sites  []Site   `json:"sites"`
	// Trace oracles only: the union is over Runs suite runs (N stated,
	// design §3.1), and Coverage is the mandatory coverage line —
	// files_loaded / files_in_module, functions_started /
	// functions_declared, c_callee_calls, external_python_targets,
	// subprocesses_traced.
	Runs           int            `json:"runs,omitempty"`
	SuiteExitCodes []int          `json:"suite_exit_codes,omitempty"`
	Coverage       map[string]int `json:"coverage,omitempty"`
	// Excluded counts sites the oracle saw and dropped by rule — "generated"
	// for calls in compiler-written code (Rust's test harness, attribute
	// and derive output), which no source line makes.
	Excluded map[string]int `json:"excluded,omitempty"`
	// State names a cell that could not be graded and says why, as its
	// own state rather than an empty result (A-1, RR-6): "no-roots" — a
	// reachability oracle found no main or test binary to root at, so
	// the module (a library without tests) was loaded but nothing was
	// analysed. Empty when the cell graded.
	State string `json:"state,omitempty"`
	// Containment says where an executing oracle ran (ADR-092 phase 2):
	// "contained" (the sandbox image) or "host: <reason>" (the escape
	// hatch). Empty for the oracles that execute no repo code.
	Containment string `json:"containment,omitempty"`
}

// StateNoRoots is the reachability oracle's "nothing to root at" state.
const StateNoRoots = "no-roots"

// Under reports whether repo-relative path p lies in directory dir
// ("" or "." meaning the whole repo). Excluded reports whether p lies
// in any of dirs. These are THE cell-membership predicates (RR-3): the
// export and every oracle extractor call these two, never a local copy
// — H-2 and H-10 were both the same rule written twice and evolved
// once. Both sides normalise their directory strings here, so a
// trailing slash or a leading "./" cannot split them.
func Under(p, dir string) bool {
	dir = cleanDir(dir)
	return dir == "" || p == dir || strings.HasPrefix(p, dir+"/")
}

// Excluded is Under over a list; an empty or "." entry excludes nothing.
func Excluded(p string, dirs []string) bool {
	for _, d := range dirs {
		if d = cleanDir(d); d != "" && Under(p, d) {
			return true
		}
	}
	return false
}

func cleanDir(d string) string {
	d = strings.Trim(strings.ReplaceAll(d, "\\", "/"), "/")
	d = strings.TrimPrefix(d, "./")
	if d == "." {
		return ""
	}
	return d
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	neg := n < 0
	if neg {
		n = -n
	}
	var b [20]byte
	i := len(b)
	for n > 0 {
		i--
		b[i] = byte('0' + n%10)
		n /= 10
	}
	if neg {
		i--
		b[i] = '-'
	}
	return string(b[i:])
}
