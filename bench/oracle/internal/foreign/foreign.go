// Package foreign turns a third-party tool's call edges into the oracle
// lane's HobbesExport, so a graph Hobbes did not build can be graded
// against the same answer keys with the same matcher (ADR-101, the
// comparative programme). The oracle does not care who produced an edge.
//
// The input is the minimal shape a converter under bench/oracle/adapters
// emits — one object per graded pair, positions as "repo-relative
// path:1-based line" at the lane's grain (D-O4: the site is the line of
// the call's opening parenthesis, the callee the line of the declared
// identifier):
//
//	{ "repo": "<path>", "sha": "<sha>", "tool": "<name>", "version": "<pin>",
//	  "converter": "<adapter>@<version>",
//	  "edges": [ { "site": "file:line", "callee": "file:line",
//	               "caller": "<optional>", "kind": "<optional callee kind>",
//	               "label": "<optional: the tool's own confidence or tier>" } ] }
//
// What is and is not carried across (ADR-101): the site and callee
// positions are graded exactly as Hobbes' are — line grain on the site,
// any declaration of the resolved overload set, the callee's binding
// rule and the interface `abstract` bucket all live on the oracle's
// side and apply to every graph alike. Two tolerances read the Hobbes
// graph's own metadata and therefore fire for a foreign graph only when
// the converter supplies it: the function-valued-binding rule (a callee
// whose `kind` is a variable is `abstract`, never contradicted) needs
// `kind`; the Rust macro exclusion needs a `macro` kind. A converter
// that cannot tell the kind leaves it empty and its cell record says so
// (C-95). The tool's `label` becomes the edge's tier, so the report's
// per-tier split reads the tool's own confidence ladder.
package foreign

import (
	"encoding/json"
	"fmt"
	"os"
	"path"
	"sort"
	"strconv"
	"strings"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
	"github.com/majax7714/Hobbes/bench/oracle/internal/export"
)

// Edge is one (call site, callee declaration) pair as a converter wrote it.
type Edge struct {
	Site   string `json:"site"`
	Callee string `json:"callee"`
	Caller string `json:"caller,omitempty"`
	Kind   string `json:"kind,omitempty"`
	Label  string `json:"label,omitempty"`
}

// File is a converter's output for one repo at one commit.
type File struct {
	Repo      string `json:"repo"`
	SHA       string `json:"sha"`
	Tool      string `json:"tool"`
	Version   string `json:"version"`
	Converter string `json:"converter,omitempty"`
	Edges     []Edge `json:"edges"`
}

// MaxErrors is how many malformed positions Convert lists before it
// stops reading; one is already a converter defect.
const MaxErrors = 5

// FromFile reads a converter's file and converts it for the cell
// (module, lang, exclude — the same predicates `oracle export` applies
// to a Hobbes graph, RR-3).
func FromFile(p, module, lang string, exclude ...string) (*edges.HobbesExport, *File, error) {
	raw, err := os.ReadFile(p)
	if err != nil {
		return nil, nil, err
	}
	var f File
	if err := json.Unmarshal(raw, &f); err != nil {
		return nil, nil, fmt.Errorf("%s: %w", p, err)
	}
	h, err := Convert(&f, module, lang, exclude...)
	return h, &f, err
}

// Convert builds the graded export. A malformed position is an error,
// never a silently dropped edge: a converter defect must grade as
// nothing rather than as the tool's error (C-94). Edges outside the
// cell, in another language's files, or repeated are counted in
// Excluded and dropped, as the Hobbes export drops them.
func Convert(f *File, module, lang string, exclude ...string) (*edges.HobbesExport, error) {
	if strings.TrimSpace(f.Tool) == "" {
		return nil, fmt.Errorf("foreign file names no tool")
	}
	exts, ok := export.Exts[lang]
	if !ok {
		return nil, fmt.Errorf("unknown lang %q (go|ts|py|rust|java)", lang)
	}
	module = path.Clean("/" + module)[1:]
	out := &edges.HobbesExport{SHA: f.SHA, Module: module, Excluded: map[string]int{}}
	seen := map[string]bool{}
	var errs []string
	for i, e := range f.Edges {
		site, err := parsePos(e.Site)
		if err == nil {
			var cerr error
			var callee edges.Pos
			callee, cerr = parsePos(e.Callee)
			if cerr != nil {
				err = cerr
			} else {
				if !hasExt(site.Path, exts) || !hasExt(callee.Path, exts) {
					out.Excluded["other-language"]++
					continue
				}
				if !edges.Under(site.Path, module) || edges.Excluded(site.Path, exclude) {
					out.Excluded["outside-cell"]++
					continue
				}
				if e.Kind == "macro" {
					out.Excluded["macro"]++
					continue
				}
				key := site.Key() + "->" + callee.Key()
				if seen[key] {
					out.Excluded["duplicate"]++
					continue
				}
				seen[key] = true
				tier := f.Tool
				if e.Label != "" {
					tier = f.Tool + ":" + e.Label
				}
				out.Edges = append(out.Edges, edges.HobbesEdge{
					Site:       site,
					Target:     callee,
					TargetID:   f.Tool + ":" + callee.Key(),
					TargetKind: e.Kind,
					Caller:     e.Caller,
					Tier:       tier,
					Lanes:      []string{f.Tool},
				})
				continue
			}
		}
		errs = append(errs, fmt.Sprintf("edge %d: %v", i, err))
		if len(errs) >= MaxErrors {
			break
		}
	}
	if len(errs) > 0 {
		return nil, fmt.Errorf("%s: malformed positions (a converter defect, C-94):\n  %s", f.Tool, strings.Join(errs, "\n  "))
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

// parsePos reads "path:line". The path is repo-relative with forward
// slashes and no leading "./"; the line is 1-based.
func parsePos(s string) (edges.Pos, error) {
	i := strings.LastIndex(s, ":")
	if i <= 0 || i == len(s)-1 {
		return edges.Pos{}, fmt.Errorf("%q is not path:line", s)
	}
	line, err := strconv.Atoi(s[i+1:])
	if err != nil || line < 1 {
		return edges.Pos{}, fmt.Errorf("%q: line must be a positive integer", s)
	}
	p := strings.ReplaceAll(s[:i], "\\", "/")
	p = strings.TrimPrefix(p, "./")
	if p == "" || strings.HasPrefix(p, "/") || strings.HasPrefix(p, "../") {
		return edges.Pos{}, fmt.Errorf("%q: path must be repo-relative", s)
	}
	return edges.Pos{Path: p, Line: line}, nil
}

func hasExt(p string, exts []string) bool {
	for _, x := range exts {
		if strings.HasSuffix(p, x) {
			return true
		}
	}
	return false
}
