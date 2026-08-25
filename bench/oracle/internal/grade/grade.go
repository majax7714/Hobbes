// Package grade is the matcher and reporter (design §8): it buckets every
// Hobbes edge against an oracle export, computes precision-against-oracle
// and recall with their mandatory companions (root count, silent size,
// per-tier split, miss decomposition) and emits the triage rows.
//
// Buckets for a resolution or reachability oracle (design §3):
//
//   - confirmed     the oracle has the same (site line, target declaration)
//   - contradicted  the oracle resolved that site and Hobbes' target is
//     not among its targets
//   - abstract      the site is a dynamic dispatch and Hobbes' target is
//     the interface method's declaration — right at the
//     declaration grain, not a concrete target; reported
//     on its own, in neither precision term, and the
//     concrete oracle pairs at that site count as misses
//     (D-O3 prices the dispatch ceiling on the recall side)
//   - silent        the oracle could not speak: the file was not loaded
//     (not-loaded), no reachable function holds a call on
//     that line (unreachable), or the site is reachable and
//     RTA resolved it to nothing (no-targets)
//
// Site matching is at line grain: a Hobbes edge is confirmed if its
// target is among the targets of any oracle site on the same file and
// line. A line holding several oracle sites is logged as tolerance.
package grade

import (
	"fmt"
	"io"
	"sort"
	"strings"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

// Row is one graded Hobbes edge, with its bucket and — for contradicted
// rows — the oracle's targets, which is the triage queue.
type Row struct {
	Edge          edges.HobbesEdge `json:"edge"`
	Bucket        string           `json:"bucket"`
	Reason        string           `json:"reason,omitempty"`
	OracleTargets []edges.Target   `json:"oracle_targets,omitempty"`
}

// Miss is one oracle (site, target) pair Hobbes did not emit.
type Miss struct {
	Site   edges.Pos    `json:"site"`
	Caller string       `json:"caller"`
	Mode   string       `json:"mode"`
	Target edges.Target `json:"target"`
	Class  string       `json:"class"`
}

// TierCounts is the bucket split for one confidence tier.
type TierCounts struct {
	Confirmed    int `json:"confirmed"`
	Contradicted int `json:"contradicted"`
	Abstract     int `json:"abstract"`
	Silent       int `json:"silent"`
}

// Fraction is hits over pairs for one oracle-pair class.
type Fraction struct {
	Hits  int `json:"hits"`
	Pairs int `json:"pairs"`
}

// Report is one cell's result. RecallBy splits the in-repo oracle pairs
// by class — static, static-closure, dynamic, dynamic-closure — because
// a reachability oracle over-approximates dynamic calls (a `func()`
// value resolves to every reachable `func()` in the program), so the
// dynamic classes inflate the denominator with pairs no run takes; the
// static class is the tight number and the report prints both.
type Report struct {
	Oracle         string                `json:"oracle"`
	Kind           string                `json:"kind"`
	Module         string                `json:"module"`
	SHA            string                `json:"sha"`
	Roots          int                   `json:"roots"`
	RootNames      []string              `json:"root_names"`
	Tags           []string              `json:"tags"`
	HobbesEdges    int                   `json:"hobbes_edges"`
	Total          TierCounts            `json:"total"`
	ByTier         map[string]TierCounts `json:"by_tier"`
	SilentBy       map[string]int        `json:"silent_by"`
	Precision      *float64              `json:"precision_against_oracle"`
	OraclePairs    int                   `json:"oracle_pairs_in_repo"`
	OracleExternal int                   `json:"oracle_pairs_external"`
	RecallHits     int                   `json:"recall_confirmed"`
	Recall         *float64              `json:"recall"`
	RecallBy       map[string]Fraction   `json:"recall_by_class"`
	MissBy         map[string]int        `json:"miss_by"`
	Tolerance      int                   `json:"tolerance_matches"`
	Rows           []Row                 `json:"rows"`
	Misses         []Miss                `json:"misses"`
}

// Grade matches h against o.
func Grade(h *edges.HobbesExport, o *edges.OracleExport) *Report {
	r := &Report{
		Oracle: o.Oracle, Kind: o.Kind, Module: o.Module, SHA: h.SHA,
		Roots: len(o.Roots), RootNames: o.Roots, Tags: o.Tags,
		HobbesEdges: len(h.Edges),
		ByTier:      map[string]TierCounts{}, SilentBy: map[string]int{}, MissBy: map[string]int{}, RecallBy: map[string]Fraction{},
	}
	loaded := map[string]bool{}
	for _, f := range o.Files {
		loaded[f] = true
	}
	byLine := map[string][]*edges.Site{}
	for i := range o.Sites {
		s := &o.Sites[i]
		byLine[s.Pos.Key()] = append(byLine[s.Pos.Key()], s)
	}
	hobbesPairs := map[string]bool{}
	for _, e := range h.Edges {
		hobbesPairs[e.Site.Key()+"->"+e.Target.Key()] = true
	}

	for _, e := range h.Edges {
		row := Row{Edge: e}
		sites := byLine[e.Site.Key()]
		switch {
		case !loaded[e.Site.Path]:
			row.Bucket, row.Reason = "silent", "not-loaded"
		case len(sites) == 0:
			row.Bucket, row.Reason = "silent", "unreachable"
		default:
			if len(sites) > 1 {
				r.Tolerance++
			}
			var targets []edges.Target
			abstract := false
			for _, s := range sites {
				targets = append(targets, s.Targets...)
				if s.Interface != nil && s.Interface.Pos == e.Target {
					abstract = true
				}
			}
			switch {
			case hasTarget(targets, e.Target):
				row.Bucket = "confirmed"
			case abstract:
				row.Bucket = "abstract"
				row.OracleTargets = targets
			case len(targets) == 0:
				row.Bucket, row.Reason = "silent", "no-targets"
			default:
				row.Bucket = "contradicted"
				row.OracleTargets = targets
			}
		}
		tc := r.ByTier[e.Tier]
		switch row.Bucket {
		case "confirmed":
			tc.Confirmed++
			r.Total.Confirmed++
		case "contradicted":
			tc.Contradicted++
			r.Total.Contradicted++
		case "abstract":
			tc.Abstract++
			r.Total.Abstract++
		case "silent":
			tc.Silent++
			r.Total.Silent++
			r.SilentBy[row.Reason]++
		}
		r.ByTier[e.Tier] = tc
		r.Rows = append(r.Rows, row)
	}
	if d := r.Total.Confirmed + r.Total.Contradicted; d > 0 {
		p := float64(r.Total.Confirmed) / float64(d)
		r.Precision = &p
	}

	for _, s := range o.Sites {
		for _, t := range s.Targets {
			if t.External {
				r.OracleExternal++
				continue
			}
			r.OraclePairs++
			class := missClass(s, t)
			f := r.RecallBy[class]
			f.Pairs++
			if hobbesPairs[s.Pos.Key()+"->"+t.Pos.Key()] {
				f.Hits++
				r.RecallBy[class] = f
				r.RecallHits++
				continue
			}
			r.RecallBy[class] = f
			r.MissBy[class]++
			r.Misses = append(r.Misses, Miss{Site: s.Pos, Caller: s.Caller, Mode: s.Mode, Target: t, Class: class})
		}
	}
	if r.OraclePairs > 0 {
		rc := float64(r.RecallHits) / float64(r.OraclePairs)
		r.Recall = &rc
	}
	sort.Slice(r.Misses, func(i, j int) bool { return r.Misses[i].Site.Key() < r.Misses[j].Site.Key() })
	return r
}

// missClass names an oracle pair by how the call is made and what it
// reaches, so a miss register can say what hurts most:
//
//   - interface→named / interface→closure  — an invoke through an interface
//   - func-value→named / func-value→closure — a call of a function value
//     (a reachability oracle over-approximates these: every reachable
//     function of the signature is a candidate, so the pair count is an
//     upper bound and the class is marked inflated in the report)
//   - static→named / static→closure — a direct call; static→closure is a
//     call of a closure bound to a local name
func missClass(s edges.Site, t edges.Target) string {
	how := "static"
	if s.Mode == "dynamic" {
		how = "func-value"
		if s.Interface != nil {
			how = "interface"
		}
	}
	what := "named"
	if t.Closure {
		what = "closure"
	}
	return how + "→" + what
}

func hasTarget(ts []edges.Target, p edges.Pos) bool {
	for _, t := range ts {
		if t.Pos == p {
			return true
		}
	}
	return false
}

// Print writes the human summary: the pair together, the silent size,
// the root count next to recall, the tier split, and the triage rows.
func Print(w io.Writer, r *Report) {
	fmt.Fprintf(w, "cell %s  oracle %s (%s)  sha %s\n", r.Module, r.Oracle, r.Kind, short(r.SHA))
	fmt.Fprintf(w, "hobbes edges %d: confirmed %d  contradicted %d  abstract %d  silent %d %v\n",
		r.HobbesEdges, r.Total.Confirmed, r.Total.Contradicted, r.Total.Abstract, r.Total.Silent, r.SilentBy)
	if r.Precision != nil {
		fmt.Fprintf(w, "precision-against-oracle %.1f%% (%d/%d)\n", *r.Precision*100, r.Total.Confirmed, r.Total.Confirmed+r.Total.Contradicted)
	} else {
		fmt.Fprintln(w, "precision-against-oracle: undefined (no confirmed or contradicted edges)")
	}
	if r.Recall != nil {
		fmt.Fprintf(w, "recall %.1f%% (%d/%d in-repo oracle pairs) at %d roots; external oracle pairs %d; misses %v\n",
			*r.Recall*100, r.RecallHits, r.OraclePairs, r.Roots, r.OracleExternal, r.MissBy)
	} else {
		fmt.Fprintf(w, "recall: undefined (no in-repo oracle pairs) at %d roots\n", r.Roots)
	}
	classes := make([]string, 0, len(r.RecallBy))
	for c := range r.RecallBy {
		classes = append(classes, c)
	}
	sort.Strings(classes)
	totalMiss := 0
	for _, n := range r.MissBy {
		totalMiss += n
	}
	for _, c := range classes {
		f := r.RecallBy[c]
		note := ""
		if strings.HasPrefix(c, "func-value") && r.Kind == "reachability" {
			note = "  (inflated: reachability oracle over-approximates function values; upper bound)"
		}
		share := 0.0
		if totalMiss > 0 {
			share = float64(f.Pairs-f.Hits) / float64(totalMiss) * 100
		}
		fmt.Fprintf(w, "  recall[%-18s] %5.1f%% (%d/%d)  misses %d = %.1f%% of all misses%s\n", c, pct(f), f.Hits, f.Pairs, f.Pairs-f.Hits, share, note)
	}
	tiers := make([]string, 0, len(r.ByTier))
	for t := range r.ByTier {
		tiers = append(tiers, t)
	}
	sort.Strings(tiers)
	for _, t := range tiers {
		c := r.ByTier[t]
		fmt.Fprintf(w, "  tier %-10s confirmed %d  contradicted %d  abstract %d  silent %d\n", t, c.Confirmed, c.Contradicted, c.Abstract, c.Silent)
	}
	if r.Tolerance > 0 {
		fmt.Fprintf(w, "  line-grain tolerance used on %d edge(s) (several oracle sites on one line)\n", r.Tolerance)
	}
	for _, row := range r.Rows {
		if row.Bucket == "contradicted" || row.Bucket == "abstract" {
			fmt.Fprintf(w, "  %-12s %s  hobbes %s (%s)  oracle %s\n", row.Bucket, row.Edge.Site.Key(), row.Edge.Target.Key(), row.Edge.TargetID, names(row.OracleTargets))
		}
	}
	for _, m := range r.Misses {
		fmt.Fprintf(w, "  missed       %s  %s -> %s (%s) [%s]\n", m.Site.Key(), m.Caller, m.Target.Pos.Key(), m.Target.Name, m.Class)
	}
}

func pct(f Fraction) float64 {
	if f.Pairs == 0 {
		return 0
	}
	return float64(f.Hits) / float64(f.Pairs) * 100
}

func names(ts []edges.Target) string {
	s := ""
	for i, t := range ts {
		if i > 0 {
			s += ", "
		}
		s += t.Pos.Key() + " (" + t.Name + ")"
	}
	if s == "" {
		return "-"
	}
	return s
}

func short(s string) string {
	if len(s) > 8 {
		return s[:8]
	}
	return s
}
