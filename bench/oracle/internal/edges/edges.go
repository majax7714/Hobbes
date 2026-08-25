// Package edges is the shared shape of the oracle lane (ADR-089): the
// Hobbes-side export of graded call edges and the oracle-side export of
// analysed call sites, both at the design's grain — (call-site position,
// callee declaration identity), positions as repo-relative path + 1-based
// line of the identifier (D-O4).
package edges

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
	Site     Pos      `json:"site"`
	Target   Pos      `json:"target"`
	TargetID string   `json:"target_id"`
	Caller   string   `json:"caller"`
	Tier     string   `json:"tier"`
	Lanes    []string `json:"lanes"`
}

// HobbesExport is the Hobbes side of one cell.
type HobbesExport struct {
	SHA    string       `json:"sha"`
	Module string       `json:"module"`
	Edges  []HobbesEdge `json:"edges"`
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
}

// OracleExport is the oracle side of one cell. Files is every in-repo
// file the oracle loaded; a Hobbes site in a file outside it is
// oracle-silent as not-loaded (build tags, C-26 orphans).
type OracleExport struct {
	Oracle string   `json:"oracle"`
	Kind   string   `json:"kind"`
	Module string   `json:"module"`
	Roots  []string `json:"roots"`
	Tags   []string `json:"tags"`
	Files  []string `json:"files"`
	Sites  []Site   `json:"sites"`
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
