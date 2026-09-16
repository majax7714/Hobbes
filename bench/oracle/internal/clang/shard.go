package clang

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

// Decl is one declaration node a unit saw — C's FunctionDecl, or one of
// C++'s four member shapes — as a bare declaration or a definition
// (Body true). Merge joins these by Mangled where a declaration has one
// and by Name otherwise, across and within shards, to resolve C's
// linkage rules and C++'s overload sets (ADR-110, ADR-113): internal
// linkage is resolved unit-local, external linkage is a join across
// every shard, as javac's keyed merge joins classes.
type Decl struct {
	Name string `json:"name"`
	// Mangled is clang's mangledName: unique per entity, so overloads
	// and a template's specialisations are told apart. Empty for a
	// declaration the dump gives none (a stub, and anything the front
	// end does not mangle).
	Mangled string `json:"mangled,omitempty"`
	// Kind is what the declaration is: "function", "method",
	// "constructor" or "destructor". A target carries it.
	Kind string `json:"kind,omitempty"`
	// Class is the enclosing C++ record's own name — the lexical one,
	// or, for an out-of-line definition, the one
	// parentDeclContextId names. Empty for a free function.
	Class string `json:"class,omitempty"`
	// Type is the node's type.qualType: a constructor site names its
	// target by the class and this signature, nothing else.
	Type string `json:"type,omitempty"`
	// Virtual is clang's virtual: a member call on such a declaration
	// is mode "virtual".
	Virtual bool `json:"virtual,omitempty"`
	// Body is true when the node carries a CompoundStmt: a definition,
	// not a bare declaration.
	Body bool `json:"body"`
	// Static is internal linkage: a free function's own storageClass ==
	// "static", or any declaration inside an unnamed namespace. Any one
	// such declaration of a key in a unit makes every call to it in that
	// unit internal linkage. A C++ member function's storageClass
	// "static" is not this — it is external linkage with no receiver.
	Static bool `json:"static"`
	// Implicit is clang's isImplicit: a builtin declared at its first
	// use, or a compiler-written member, with no real source declaration.
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
	// Mode is "static", "macro" or "dynamic", and for C++ also
	// "virtual", "operator" or "constructor".
	Mode string `json:"mode"`
	// Callee is the key Merge joins by, spelled as declKey spells it: a
	// declaration's mangled name where it has one, else its name
	// qualified by its class (a class template's pattern members, which
	// carry no mangling — ADR-113 §3, H-29), else the bare name. Empty
	// for a dynamic site.
	Callee string `json:"callee,omitempty"`
	// CalleeName is the name as written, which a mangled Callee does not
	// carry: the name a target reports. Empty when it is the Callee.
	CalleeName string `json:"callee_name,omitempty"`
}

// Shard is one translation unit's clang dump, reduced to what Merge
// needs: the file the entry compiled, every in-repo file it loaded, its
// function declarations and definitions, and its in-repo call sites.
// Failed and Stderr record a unit clang rejected — unit B fills them
// from clang's exit — and such a shard is graded not loaded (its Files
// stay empty).
type Shard struct {
	File  string   `json:"file"`
	Files []string `json:"files"`
	Decls []Decl   `json:"decls"`
	Calls []Call   `json:"calls"`
	// CXX is whether the unit ran the C++ binary (its entry's file has a
	// C++ extension, ADR-113): the coverage line counts them, so a mixed
	// build root says how it split.
	CXX    bool   `json:"cxx,omitempty"`
	Failed bool   `json:"failed"`
	Stderr string `json:"stderr,omitempty"`
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
