// Package export turns a Hobbes graph.json into the oracle lane's
// HobbesExport: one graded edge per evidence line of every `calls`
// symbol edge whose site sits under the cell's module directory.
//
// Positions come straight from the artifact: the site is the evidence
// row's (path, line); the target is the callee symbol's declaring file
// (the module node's path — one Go file is one Hobbes module) and its
// declaration line, which the extractor records at the identifier.
package export

import (
	"encoding/json"
	"fmt"
	"os"
	"path"
	"sort"
	"strings"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

type graph struct {
	SHA   string `json:"sha"`
	Nodes []struct {
		ID   string `json:"id"`
		Kind string `json:"kind"`
		Path string `json:"path"`
	} `json:"nodes"`
	Symbols []struct {
		ID     string `json:"id"`
		Module string `json:"module"`
		Line   int    `json:"line"`
	} `json:"symbols"`
	SymbolEdges []struct {
		From     string `json:"from"`
		To       string `json:"to"`
		Type     string `json:"type"`
		Tier     string `json:"tier"`
		Evidence []struct {
			Lane string `json:"lane"`
			Path string `json:"path"`
			Line int    `json:"line"`
		} `json:"evidence"`
	} `json:"symbol_edges"`
}

// Exts is the file-extension set of one language's cell.
var Exts = map[string][]string{
	"go": {".go"},
	"ts": {".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs"},
}

// FromFile reads graph.json and exports the cell for module (a
// repo-relative directory, "" or "." for the whole repo) in lang ("go"
// or "ts": the extension set of the sites and targets kept).
func FromFile(graphPath, module, lang string, exclude ...string) (*edges.HobbesExport, error) {
	raw, err := os.ReadFile(graphPath)
	if err != nil {
		return nil, err
	}
	var g graph
	if err := json.Unmarshal(raw, &g); err != nil {
		return nil, fmt.Errorf("%s: %w", graphPath, err)
	}
	return From(&g, module, lang, exclude...)
}

// From exports the cell. exclude lists repo-relative directories whose
// sites are dropped — the nested modules of a monorepo root, which are
// cells of their own and which the root's `./...` load does not see.
func From(g *graph, module, lang string, exclude ...string) (*edges.HobbesExport, error) {
	exts, ok := Exts[lang]
	if !ok {
		return nil, fmt.Errorf("unknown lang %q (go|ts)", lang)
	}
	module = path.Clean("/" + module)[1:]
	modulePath := map[string]string{}
	for _, n := range g.Nodes {
		if n.Kind == "module" {
			modulePath[n.ID] = n.Path
		}
	}
	symLine := map[string]int{}
	symModule := map[string]string{}
	for _, s := range g.Symbols {
		symLine[s.ID] = s.Line
		symModule[s.ID] = s.Module
	}
	out := &edges.HobbesExport{SHA: g.SHA, Module: module}
	for _, e := range g.SymbolEdges {
		if e.Type != "calls" {
			continue
		}
		file, ok := modulePath[symModule[e.To]]
		if !ok || !hasExt(file, exts) {
			continue
		}
		for _, ev := range e.Evidence {
			if !hasExt(ev.Path, exts) || !under(ev.Path, module) || excluded(ev.Path, exclude) {
				continue
			}
			out.Edges = append(out.Edges, edges.HobbesEdge{
				Site:     edges.Pos{Path: ev.Path, Line: ev.Line},
				Target:   edges.Pos{Path: file, Line: symLine[e.To]},
				TargetID: e.To,
				Caller:   e.From,
				Tier:     e.Tier,
				Lanes:    []string{ev.Lane},
			})
		}
	}
	sort.Slice(out.Edges, func(i, j int) bool {
		a, b := out.Edges[i], out.Edges[j]
		if a.Site != b.Site {
			return a.Site.Key() < b.Site.Key()
		}
		return a.Target.Key() < b.Target.Key()
	})
	return out, nil
}

func hasExt(p string, exts []string) bool {
	for _, x := range exts {
		if strings.HasSuffix(p, x) {
			return true
		}
	}
	return false
}

func excluded(p string, dirs []string) bool {
	for _, d := range dirs {
		d = path.Clean("/" + d)[1:]
		if d != "" && under(p, d) {
			return true
		}
	}
	return false
}

func under(p, dir string) bool {
	return dir == "" || p == dir || strings.HasPrefix(p, dir+"/")
}
