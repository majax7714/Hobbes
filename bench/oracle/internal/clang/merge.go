package clang

import (
	"sort"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

// shardInfo is one shard's linkage picture: which names it declares
// static (internal linkage in that unit), where its own definition of a
// name sits (Body && InRepo), and which names it declares in-repo and
// non-implicitly (ADR-110's "declared in the repo" test for undefined
// vs external).
type shardInfo struct {
	static         map[string]bool
	ownDef         map[string]edges.Pos
	declaredInRepo map[string]bool
}

func buildShardInfo(s *Shard) shardInfo {
	info := shardInfo{static: map[string]bool{}, ownDef: map[string]edges.Pos{}, declaredInRepo: map[string]bool{}}
	for _, d := range s.Decls {
		if d.Static {
			info.static[d.Name] = true
		}
	}
	for _, d := range s.Decls {
		if d.Body && d.InRepo {
			info.ownDef[d.Name] = d.Pos
		}
		if d.InRepo && !d.Implicit {
			info.declaredInRepo[d.Name] = true
		}
	}
	return info
}

// resolved is one shard's resolution of one of its calls, before
// merging identical sites across shards.
type resolved struct {
	call    Call
	targets []edges.Target
	// reason is "undefined" or "link-ambiguous", set only when targets
	// is empty.
	reason string
}

// resolveCall applies ADR-110's target rules to one call using its own
// shard's info and the join of every shard's external definitions.
func resolveCall(c Call, info shardInfo, globalDefs map[string]map[edges.Pos]bool) resolved {
	r := resolved{call: c}
	if c.Mode == "dynamic" {
		return r
	}
	name := c.Callee
	switch {
	case info.static[name]:
		if p, ok := info.ownDef[name]; ok {
			r.targets = []edges.Target{{Pos: p, Name: name, Kind: "function"}}
		} else if info.declaredInRepo[name] {
			r.reason = "undefined"
		} else {
			// A static function with no in-repo trace at all: defined
			// (or only declared) outside the repo, a system header's
			// `static inline` (ADR-110's example, `__bswap_16`).
			r.targets = []edges.Target{{Name: name, Kind: "function", External: true}}
		}
	case len(globalDefs[name]) == 0:
		if info.declaredInRepo[name] {
			r.reason = "undefined"
		} else {
			r.targets = []edges.Target{{Name: name, Kind: "function", External: true}}
		}
	case len(globalDefs[name]) == 1:
		for p := range globalDefs[name] {
			r.targets = []edges.Target{{Pos: p, Name: name, Kind: "function"}}
		}
	default:
		if p, ok := info.ownDef[name]; ok {
			r.targets = []edges.Target{{Pos: p, Name: name, Kind: "function"}}
		} else {
			r.reason = "link-ambiguous"
		}
	}
	return r
}

// siteKey is ADR-110's site identity: (site path, line, column,
// spelling path, line, column, mode, callee name). Mode and callee join
// the position pair because a callee that is itself a call
// (`get_fn()(2)`) is two sites sharing one (site, spelling) position:
// the inner call, static, and the outer call through its result,
// dynamic.
type siteKey struct {
	sitePath            string
	siteLine, siteCol   int
	spellPath           string
	spellLine, spellCol int
	mode                string
	callee              string
}

func keyOf(c Call) siteKey {
	return siteKey{c.Site.Path, c.Site.Line, c.Col, c.Spell.Path, c.Spell.Line, c.SpellCol, c.Mode, c.Callee}
}

// Merge joins every shard's declarations by name (javac's keyed merge,
// C's face of it) to resolve ADR-110's linkage rules, unions each
// site's targets across the shards that share it, and classifies every
// site into the coverage buckets oracle-grading.md §7c defines. Oracle,
// Roots and Containment are the caller's to set: this package runs no
// clang and knows nothing about how the shards were produced.
func Merge(shards []*Shard, module string) *edges.OracleExport {
	out := &edges.OracleExport{Kind: "resolution", Module: module}

	fileSet := map[string]bool{}
	for _, s := range shards {
		for _, f := range s.Files {
			fileSet[f] = true
		}
	}
	out.Files = make([]string, 0, len(fileSet))
	for f := range fileSet {
		out.Files = append(out.Files, f)
	}
	sort.Strings(out.Files)

	infos := make([]shardInfo, len(shards))
	globalDefs := map[string]map[edges.Pos]bool{}
	for i, s := range shards {
		infos[i] = buildShardInfo(s)
	}
	for i, s := range shards {
		info := infos[i]
		for _, d := range s.Decls {
			if d.Body && d.InRepo && !info.static[d.Name] {
				if globalDefs[d.Name] == nil {
					globalDefs[d.Name] = map[edges.Pos]bool{}
				}
				globalDefs[d.Name][d.Pos] = true
			}
		}
	}

	groups := map[siteKey][]resolved{}
	var order []siteKey
	for i, s := range shards {
		info := infos[i]
		for _, c := range s.Calls {
			r := resolveCall(c, info, globalDefs)
			k := keyOf(c)
			if _, ok := groups[k]; !ok {
				order = append(order, k)
			}
			groups[k] = append(groups[k], r)
		}
	}

	cov := map[string]int{
		"units": len(shards), "units_failed": 0,
		"sites_static": 0, "sites_macro": 0, "sites_dynamic": 0,
		"sites_external": 0, "sites_link_ambiguous": 0, "sites_undefined": 0, "sites_tu_split": 0,
	}
	for _, s := range shards {
		if s.Failed {
			cov["units_failed"]++
		}
	}

	sites := make([]edges.Site, 0, len(order))
	for _, k := range order {
		rs := groups[k]
		mode, caller := rs[0].call.Mode, rs[0].call.Caller
		site := edges.Site{Pos: edges.Pos{Path: k.sitePath, Line: k.siteLine}, Col: k.siteCol, Caller: caller, Mode: mode}
		if mode == "dynamic" {
			cov["sites_dynamic"]++
			sites = append(sites, site)
			continue
		}
		seen := map[edges.Target]bool{}
		var targets []edges.Target
		for _, r := range rs {
			for _, t := range r.targets {
				if !seen[t] {
					seen[t] = true
					targets = append(targets, t)
				}
			}
		}
		sort.Slice(targets, func(i, j int) bool {
			if targets[i].Pos != targets[j].Pos {
				return targets[i].Pos.Key() < targets[j].Pos.Key()
			}
			return targets[i].Name < targets[j].Name
		})
		switch {
		case len(targets) >= 2:
			cov["sites_tu_split"]++
		case len(targets) == 1 && targets[0].External:
			cov["sites_external"]++
		case len(targets) == 1:
			if mode == "macro" {
				cov["sites_macro"]++
			} else {
				cov["sites_static"]++
			}
		default:
			if rs[0].reason == "undefined" {
				cov["sites_undefined"]++
			} else {
				cov["sites_link_ambiguous"]++
			}
		}
		site.Targets = targets
		sites = append(sites, site)
	}
	sort.Slice(sites, func(i, j int) bool {
		a, b := sites[i], sites[j]
		if a.Pos != b.Pos {
			return a.Pos.Key() < b.Pos.Key()
		}
		return a.Col < b.Col
	})
	out.Sites = sites
	out.Coverage = cov
	return out
}
