// Package gorta is the Go reachability oracle (design §4, D-O1): load a
// module with its tests, build SSA, run RTA from every main (binaries
// and the synthesized test mains), and export every in-repo call site
// of every reachable non-synthetic function with the targets RTA
// resolved it to.
//
// Normalisation, as the design demands: synthetic functions (wrappers,
// thunks, bound closures, generic instantiations) are unwound to the
// source declaration before they are reported; closures are identified
// by declaration position only; test-variant packages (the same file
// compiled twice under `Tests: true`) collapse by position. Package
// initialisers are in the graded set — `init` functions are reachable
// from every main and their sites are real calls.
package gorta

import (
	"fmt"
	"go/token"
	"go/types"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"golang.org/x/tools/go/callgraph"
	"golang.org/x/tools/go/callgraph/rta"
	"golang.org/x/tools/go/packages"
	"golang.org/x/tools/go/ssa"
	"golang.org/x/tools/go/ssa/ssautil"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

// Options selects one cell: the repo root and the module directory
// (repo-relative) whose packages are loaded with `./...`. Tags are extra
// build tags; the default tag set of the box is always in force.
type Options struct {
	Repo   string
	Module string
	Tags   []string
	// NoTests loads the module without its test packages: roots are the
	// binaries only, and the cell says so (its Roots list has no `.test`
	// entries). The memory shape of a large monorepo root with tests
	// doubled its packages past a 30 GB box (H-9); this is the honest
	// smaller question, not a silent downgrade.
	NoTests bool
}

// Run loads, analyses and exports one cell. Roots are the main and init
// functions of every main package in the loaded program — binaries and
// the test mains `Tests: true` synthesizes — so a library module is
// analysed through its test binaries (the cell's Roots say which).
func Run(o Options) (*edges.OracleExport, error) {
	repo, err := filepath.Abs(o.Repo)
	if err != nil {
		return nil, err
	}
	dir := filepath.Join(repo, o.Module)
	cfg := &packages.Config{
		Mode: packages.NeedName | packages.NeedFiles | packages.NeedImports |
			packages.NeedDeps | packages.NeedTypes | packages.NeedSyntax |
			packages.NeedTypesInfo | packages.NeedModule,
		Dir:   dir,
		Tests: !o.NoTests,
	}
	if len(o.Tags) > 0 {
		cfg.BuildFlags = []string{"-tags=" + strings.Join(o.Tags, ",")}
	}
	pkgs, err := packages.Load(cfg, "./...")
	if err != nil {
		return nil, fmt.Errorf("load %s: %w", dir, err)
	}
	var loadErrs []string
	packages.Visit(pkgs, nil, func(p *packages.Package) {
		for _, e := range p.Errors {
			loadErrs = append(loadErrs, e.Error())
		}
	})
	if len(loadErrs) > 0 {
		return nil, fmt.Errorf("load %s: %d error(s), first: %s", dir, len(loadErrs), loadErrs[0])
	}
	prog, _ := ssautil.AllPackages(pkgs, ssa.InstantiateGenerics)
	prog.Build()

	var roots []*ssa.Function
	var rootNames []string
	for _, p := range prog.AllPackages() {
		if p.Pkg.Name() != "main" {
			continue
		}
		// Root at init as well as main: the runtime calls init, main never
		// does, and the synthesized test main's table of Test functions is
		// address-taken in its init — without it no test is reachable.
		// (x/tools' own `callgraph` command roots the same way.)
		if fn := p.Func("main"); fn != nil {
			roots = append(roots, fn)
			rootNames = append(rootNames, p.Pkg.Path())
			if ini := p.Func("init"); ini != nil {
				roots = append(roots, ini)
			}
		}
	}
	sort.Strings(rootNames)
	if len(roots) == 0 {
		return nil, fmt.Errorf("%s: no main functions (binaries or tests) to root RTA at", dir)
	}
	res := rta.Analyze(roots, true)

	rel := func(pos token.Pos) (edges.Pos, int, bool) {
		if !pos.IsValid() {
			return edges.Pos{}, 0, false
		}
		p := prog.Fset.Position(pos)
		r, err := filepath.Rel(repo, p.Filename)
		if err != nil || strings.HasPrefix(r, "..") {
			return edges.Pos{Path: p.Filename, Line: p.Line}, p.Column, false
		}
		return edges.Pos{Path: filepath.ToSlash(r), Line: p.Line}, p.Column, true
	}
	target := func(fn *ssa.Function) (edges.Target, bool) {
		if fn == nil {
			return edges.Target{}, false
		}
		if o := fn.Origin(); o != nil {
			fn = o
		}
		pos, _, inRepo := rel(fn.Pos())
		if !fn.Pos().IsValid() {
			return edges.Target{}, false
		}
		return edges.Target{Pos: pos, Name: fn.String(), External: !inRepo, Closure: fn.Parent() != nil}, true
	}

	files := map[string]bool{}
	for _, p := range pkgs {
		for _, f := range p.GoFiles {
			if r, err := filepath.Rel(repo, f); err == nil && !strings.HasPrefix(r, "..") && underModule(filepath.ToSlash(r), o.Module) {
				files[filepath.ToSlash(r)] = true
			}
		}
	}

	type key struct {
		pos edges.Pos
		col int
	}
	sites := map[key]*edges.Site{}
	seenTarget := map[key]map[edges.Pos]bool{}
	for fn, node := range res.CallGraph.Nodes {
		if fn == nil || fn.Synthetic != "" || fn.Pkg == nil {
			continue
		}
		if _, _, inRepo := rel(fn.Pos()); !inRepo {
			continue
		}
		bySite := map[ssa.CallInstruction][]*ssa.Function{}
		for _, e := range node.Out {
			if e.Site == nil {
				continue
			}
			bySite[e.Site] = append(bySite[e.Site], unwind(res.CallGraph, e.Callee.Func, 0)...)
		}
		for _, b := range fn.Blocks {
			for _, ins := range b.Instrs {
				call, ok := ins.(ssa.CallInstruction)
				if !ok {
					continue
				}
				pos, col, inRepo := rel(call.Pos())
				if !inRepo || !underModule(pos.Path, o.Module) {
					continue
				}
				k := key{pos, col}
				s := sites[k]
				if s == nil {
					s = &edges.Site{Pos: pos, Col: col, Caller: fn.String(), Mode: "static"}
					common := call.Common()
					if common.IsInvoke() {
						s.Mode = "dynamic"
						if m := common.Method; m != nil {
							ip, _, inRepo := rel(m.Pos())
							s.Interface = &edges.Target{Pos: ip, Name: qualified(m), External: !inRepo}
						}
					} else if common.StaticCallee() == nil {
						s.Mode = "dynamic"
					}
					sites[k] = s
					seenTarget[k] = map[edges.Pos]bool{}
				}
				for _, callee := range bySite[call] {
					t, ok := target(callee)
					if !ok || seenTarget[k][t.Pos] {
						continue
					}
					seenTarget[k][t.Pos] = true
					s.Targets = append(s.Targets, t)
				}
			}
		}
	}
	oracle := "go-rta"
	if o.NoTests {
		oracle = "go-rta (no test packages)"
	}
	out := &edges.OracleExport{Oracle: oracle, Kind: "reachability", Module: o.Module, Roots: rootNames, Tags: o.Tags}
	for f := range files {
		out.Files = append(out.Files, f)
	}
	sort.Strings(out.Files)
	for _, s := range sites {
		sort.Slice(s.Targets, func(i, j int) bool { return s.Targets[i].Pos.Key() < s.Targets[j].Pos.Key() })
		out.Sites = append(out.Sites, *s)
	}
	sort.Slice(out.Sites, func(i, j int) bool {
		a, b := out.Sites[i], out.Sites[j]
		if a.Pos != b.Pos {
			if a.Pos.Path != b.Pos.Path {
				return a.Pos.Path < b.Pos.Path
			}
			return a.Pos.Line < b.Pos.Line
		}
		return a.Col < b.Col
	})
	return out, nil
}

// unwind follows synthetic callees (wrappers, thunks, bound closures) to
// the source functions they end in; generic instantiations are folded by
// the caller through Origin. Depth-bounded: a wrapper chain deeper than
// four is not a shape SSA produces.
func unwind(g *callgraph.Graph, fn *ssa.Function, depth int) []*ssa.Function {
	if fn == nil {
		return nil
	}
	// A generic instantiation is synthetic too, but it *is* the source
	// function (folded to its origin by the caller) — following its body
	// would report the callee's callees at the caller's site (the O2
	// match-defect: sortedKeys[string] graded as sort.Strings).
	if fn.Synthetic == "" || fn.Origin() != nil || depth > 4 {
		return []*ssa.Function{fn}
	}
	node := g.Nodes[fn]
	if node == nil || len(node.Out) == 0 {
		// A synthetic with nowhere to go (a wrapper whose body RTA did
		// not expand) keeps its own position, which is the wrapped
		// declaration's.
		return []*ssa.Function{fn}
	}
	var out []*ssa.Function
	for _, e := range node.Out {
		out = append(out, unwind(g, e.Callee.Func, depth+1)...)
	}
	return out
}

// underModule scopes a cell: sites and loaded files are reported only
// under the module directory, while targets may land anywhere in the
// repo (a replaced sibling module is inside the program — C-33's join).
func underModule(p, module string) bool {
	module = strings.Trim(filepath.ToSlash(module), "/")
	return module == "" || module == "." || p == module || strings.HasPrefix(p, module+"/")
}

func qualified(m *types.Func) string {
	if r := m.Signature().Recv(); r != nil {
		return types.TypeString(r.Type(), nil) + "." + m.Name()
	}
	return m.FullName()
}

// Exists reports whether dir is a directory (for CLI argument checks).
func Exists(dir string) bool {
	st, err := os.Stat(dir)
	return err == nil && st.IsDir()
}
