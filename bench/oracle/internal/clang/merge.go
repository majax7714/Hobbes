package clang

import (
	"sort"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

// declKey is what Merge joins declarations by: the mangled name where
// clang gives one — unique per entity, so C++'s overloads and a
// template's specialisations are told apart — and otherwise the name
// qualified by the declaration's class, javac's owner-qualified key
// (H-23) on the C reader: a class template's pattern members carry a
// class and no mangling at all, so `A::format_as` and `B::format_as` are
// two entities, not one (ADR-113 §3, H-29). A declaration with no class
// keeps the bare name (`extern "C"`, `main`), and in C the mangled name
// is the plain one, so C's name join is unchanged (ADR-110).
func declKey(d Decl) string {
	if d.Mangled != "" {
		return d.Mangled
	}
	return qualify(d.Class, d.Name)
}

// shardInfo is one shard's linkage picture: which keys it declares
// static (internal linkage in that unit), where its own definition of a
// key sits (Body && InRepo), which keys it declares in-repo and
// non-implicitly (ADR-110's "declared in the repo" test for undefined
// vs external), and what each key declares (a target's Kind).
type shardInfo struct {
	static         map[string]bool
	ownDef         map[string]edges.Pos
	declaredInRepo map[string]bool
	kind           map[string]string
}

func buildShardInfo(s *Shard) shardInfo {
	info := shardInfo{static: map[string]bool{}, ownDef: map[string]edges.Pos{},
		declaredInRepo: map[string]bool{}, kind: map[string]string{}}
	for _, d := range s.Decls {
		if d.Static {
			info.static[declKey(d)] = true
		}
	}
	for _, d := range s.Decls {
		k := declKey(d)
		if d.Body && d.InRepo {
			info.ownDef[k] = d.Pos
		}
		if d.InRepo && !d.Implicit {
			info.declaredInRepo[k] = true
		}
		if d.Kind != "" {
			info.kind[k] = d.Kind
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
// shard's info and the join of every shard's external definitions. The
// key is the call's Callee (a mangled name where C++ gives one); the
// target reports the name as written and what the declaration is.
func resolveCall(c Call, info shardInfo, globalDefs map[string]map[edges.Pos]bool) resolved {
	r := resolved{call: c}
	if c.Mode == "dynamic" {
		return r
	}
	key := c.Callee
	name := c.CalleeName
	if name == "" {
		name = key
	}
	kind := info.kind[key]
	if kind == "" {
		kind = "function"
	}
	switch {
	case info.static[key]:
		if p, ok := info.ownDef[key]; ok {
			r.targets = []edges.Target{{Pos: p, Name: name, Kind: kind}}
		} else if info.declaredInRepo[key] {
			r.reason = "undefined"
		} else {
			// A static function with no in-repo trace at all: defined
			// (or only declared) outside the repo, a system header's
			// `static inline` (ADR-110's example, `__bswap_16`).
			r.targets = []edges.Target{{Name: name, Kind: kind, External: true}}
		}
	case len(globalDefs[key]) == 0:
		if info.declaredInRepo[key] {
			r.reason = "undefined"
		} else {
			r.targets = []edges.Target{{Name: name, Kind: kind, External: true}}
		}
	case len(globalDefs[key]) == 1:
		for p := range globalDefs[key] {
			r.targets = []edges.Target{{Pos: p, Name: name, Kind: kind}}
		}
	default:
		if p, ok := info.ownDef[key]; ok {
			r.targets = []edges.Target{{Pos: p, Name: name, Kind: kind}}
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

// bucketOf is the coverage bucket a resolved site's mode counts in.
func bucketOf(mode string) string {
	switch mode {
	case "macro", "virtual", "operator", "constructor":
		return "sites_" + mode
	}
	return "sites_static"
}

func keyOf(c Call) siteKey {
	return siteKey{c.Site.Path, c.Site.Line, c.Col, c.Spell.Path, c.Spell.Line, c.SpellCol, c.Mode, c.Callee}
}

// Merge joins every shard's declarations by declKey (javac's keyed
// merge, C's and C++'s face of it) to resolve ADR-110's linkage rules,
// unions each site's targets across the shards that share it, and
// classifies every site into the coverage buckets oracle-grading.md §7c
// and ADR-113 §3 define. Oracle,
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
			k := declKey(d)
			if d.Body && d.InRepo && !info.static[k] {
				if globalDefs[k] == nil {
					globalDefs[k] = map[edges.Pos]bool{}
				}
				globalDefs[k][d.Pos] = true
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
		"units": len(shards), "units_failed": 0, "units_cpp": 0,
		"sites_static": 0, "sites_macro": 0, "sites_dynamic": 0,
		"sites_virtual": 0, "sites_operator": 0, "sites_constructor": 0,
		"sites_external": 0, "sites_link_ambiguous": 0, "sites_undefined": 0, "sites_tu_split": 0,
	}
	for _, s := range shards {
		if s.Failed {
			cov["units_failed"]++
		}
		if s.CXX {
			cov["units_cpp"]++
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
			cov[bucketOf(mode)]++
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
