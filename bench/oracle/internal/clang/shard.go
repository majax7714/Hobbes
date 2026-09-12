package clang

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

// Decl is one FunctionDecl node a unit saw: a bare declaration or a
// definition (Body true). Merge joins these by Name, across and within
// shards, to resolve C's linkage rules (ADR-110): internal linkage is
// resolved unit-local, external linkage is a name join across every
// shard, as javac's keyed merge joins classes.
type Decl struct {
	Name string `json:"name"`
	// Body is true when the node carries a CompoundStmt: a definition,
	// not a bare declaration.
	Body bool `json:"body"`
	// Static is this declaration's own storageClass == "static"; any
	// one static declaration of a name in a unit makes every call to it
	// in that unit internal linkage.
	Static bool `json:"static"`
	// Implicit is clang's isImplicit: a builtin declared at its first
	// use, with no real source declaration.
	Implicit bool `json:"implicit"`
	// InRepo is whether Pos lies under the repo.
	InRepo bool      `json:"in_repo"`
	Pos    edges.Pos `json:"pos"`
}

// Call is one CallExpr the unit saw whose site lies in the repo: the
// peeled callee's mode and, for a resolvable direct callee, the name
// Merge joins by. Spell is the callee's spelling position, tracked
// separately from Site because ADR-110's identity rule keys on both: a
// macro's several written tokens share one invocation's Site but not
// their Spell, and one written call a macro argument expands twice
// shares both.
type Call struct {
	Site     edges.Pos `json:"site"`
	Col      int       `json:"col"`
	Spell    edges.Pos `json:"spell"`
	SpellCol int       `json:"spell_col"`
	Caller   string    `json:"caller"`
	// Mode is "static", "macro" or "dynamic".
	Mode string `json:"mode"`
	// Callee is the function name a static or macro site names; empty
	// for a dynamic site.
	Callee string `json:"callee,omitempty"`
}

// Shard is one translation unit's clang dump, reduced to what Merge
// needs: the file the entry compiled, every in-repo file it loaded, its
// function declarations and definitions, and its in-repo call sites.
// Failed and Stderr record a unit clang rejected — unit B fills them
// from clang's exit — and such a shard is graded not loaded (its Files
// stay empty).
type Shard struct {
	File   string   `json:"file"`
	Files  []string `json:"files"`
	Decls  []Decl   `json:"decls"`
	Calls  []Call   `json:"calls"`
	Failed bool     `json:"failed"`
	Stderr string   `json:"stderr,omitempty"`
}

// Save writes the shard as one indented JSON file.
func (s *Shard) Save(path string) error {
	raw, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, raw, 0o644)
}

// LoadShards reads every "*.json" file under dir, in name order, as a
// shard.
func LoadShards(dir string) ([]*Shard, error) {
	names, err := filepath.Glob(filepath.Join(dir, "*.json"))
	if err != nil {
		return nil, err
	}
	sort.Strings(names)
	out := make([]*Shard, 0, len(names))
	for _, n := range names {
		raw, err := os.ReadFile(n)
		if err != nil {
			return nil, err
		}
		var s Shard
		if err := json.Unmarshal(raw, &s); err != nil {
			return nil, fmt.Errorf("%s: %w", n, err)
		}
		out = append(out, &s)
	}
	return out, nil
}
