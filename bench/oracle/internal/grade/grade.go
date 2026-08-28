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
// Buckets for a trace oracle (design §3.1 — asymmetric: an observed edge
// is a fact, an unobserved edge is not a falsehood):
//
//   - confirmed     Hobbes' (site line, target) was observed at runtime
//   - suspect       the line executed, every observed Python callee on
//     it is in-repo and none is Hobbes' target — a triage
//     queue, never a contradiction (another input could
//     still take Hobbes' target)
//   - unobserved    charged to nobody: the file's module body never ran
//     (not-loaded), the line made no call in any run
//     (line-not-called), or the line ran but a callee on it
//     was C or out-of-repo, so Hobbes' site may be that
//     call (line-mixed)
//
// A trace cell has no precision; it reports the confirmation rate over
// Hobbes edges (coverage-limited), the suspect rate, recall-against-
// executed over observed in-repo pairs, and the coverage line.
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
	// Trace oracles only.
	Suspect    int `json:"suspect,omitempty"`
	Unobserved int `json:"unobserved,omitempty"`
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
	Oracle    string   `json:"oracle"`
	Kind      string   `json:"kind"`
	Module    string   `json:"module"`
	SHA       string   `json:"sha"`
	Roots     int      `json:"roots"`
	RootNames []string `json:"root_names"`
	// State carries the oracle's not-graded state (edges.OracleExport.State)
	// so the report says "no roots exist" as its own line (A-1).
	State string `json:"state,omitempty"`
	// Containment is where an executing oracle ran (edges.OracleExport).
	Containment    string                `json:"containment,omitempty"`
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
	// Trace oracles only (design §3.1): runs unioned, the tracer's
	// coverage line, the confirmation and suspect rates over Hobbes
	// edges, and how many of Hobbes' distinct sites the trace spoke about.
	Runs             int            `json:"runs,omitempty"`
	Coverage         map[string]int `json:"coverage,omitempty"`
	ConfirmationRate *float64       `json:"confirmation_rate,omitempty"`
	SuspectRate      *float64       `json:"suspect_rate,omitempty"`
	SitesObserved    int            `json:"hobbes_sites_observed,omitempty"`
	SitesTotal       int            `json:"hobbes_sites,omitempty"`
	// Poison is the seeded-wrong-edge check (design §11) when the cell
	// ran it: how many known-wrong edges the grader refused.
	Poison *PoisonCheck `json:"poison,omitempty"`
}

// PoisonCheck is the result of grading a poisoned export: Seeded wrong
// edges, of which Refused landed in a failure bucket (contradicted,
// suspect, abstract), Unjudged in a silent/unobserved one (the oracle
// could not speak at that site or line-mixed), and Confirmed — the
// number that must be zero — were accepted as right. A matcher that
// falsely confirms is invisible to triage, which reads only the failure
// buckets; this is the one line that sees it.
type PoisonCheck struct {
	Seeded    int   `json:"seeded"`
	Refused   int   `json:"refused"`
	Unjudged  int   `json:"unjudged"`
	Confirmed int   `json:"confirmed"`
	Passed    bool  `json:"passed"`
	Falsely   []Row `json:"falsely_confirmed,omitempty"`
}

// Poison seeds known-wrong edges from a Hobbes export: every edge is
// re-targeted to another declaration the export knows (a different file
// or line), skipping substitutes the oracle also lists at that site
// (two calls on one line are both right at line grain). Target ids are
// prefixed "poison:" so the rows read as what they are. The oracle is
// consulted only to build the exclusion set, never to pick a target.
func Poison(h *edges.HobbesExport, o *edges.OracleExport) *edges.HobbesExport {
	atLine := map[string]map[edges.Pos]bool{}
	for _, s := range o.Sites {
		m := atLine[s.Pos.Key()]
		if m == nil {
			m = map[edges.Pos]bool{}
			atLine[s.Pos.Key()] = m
		}
		for _, t := range s.Targets {
			m[t.Pos] = true
		}
		if s.Interface != nil {
			m[s.Interface.Pos] = true
		}
	}
	var decls []edges.Pos
	seen := map[edges.Pos]bool{}
	for _, e := range h.Edges {
		if !seen[e.Target] {
			seen[e.Target] = true
			decls = append(decls, e.Target)
		}
	}
	out := &edges.HobbesExport{SHA: h.SHA, Module: h.Module, Excluded: map[string]int{}}
	for i, e := range h.Edges {
		// Walk the declaration list from a rotating start so the
		// substitutes spread over the repo, never the same one; a cell
		// with a single target (minits: four calls to one helper) falls
		// back to the line after the declaration, which no call resolves to.
		var cand *edges.Pos
		for k := 0; k < len(decls); k++ {
			c := decls[(i+1+k)%len(decls)]
			if c != e.Target && !atLine[e.Site.Key()][c] {
				cand = &c
				break
			}
		}
		if cand == nil {
			c := edges.Pos{Path: e.Target.Path, Line: e.Target.Line + 1}
			if !atLine[e.Site.Key()][c] {
				cand = &c
			}
		}
		if cand == nil {
			continue
		}
		p := e
		p.Target = *cand
		p.TargetID = "poison:" + e.TargetID
		out.Edges = append(out.Edges, p)
	}
	return out
}

// CheckPoison grades the poisoned twin of h against o and summarises it.
func CheckPoison(h *edges.HobbesExport, o *edges.OracleExport) *PoisonCheck {
	pr := Grade(Poison(h, o), o)
	c := &PoisonCheck{Seeded: len(pr.Rows)}
	for _, row := range pr.Rows {
		switch row.Bucket {
		case "confirmed":
			c.Confirmed++
			c.Falsely = append(c.Falsely, row)
		case "contradicted", "suspect", "abstract":
			c.Refused++
		default:
			c.Unjudged++
		}
	}
	c.Passed = c.Seeded > 0 && c.Confirmed == 0
	return c
}

// Grade matches h against o.
func Grade(h *edges.HobbesExport, o *edges.OracleExport) *Report {
	r := &Report{
		Oracle: o.Oracle, Kind: o.Kind, Module: o.Module, SHA: h.SHA, Containment: o.Containment,
		Roots: len(o.Roots), RootNames: o.Roots, Tags: o.Tags, State: o.State,
		HobbesEdges: len(h.Edges),
		ByTier:      map[string]TierCounts{}, SilentBy: map[string]int{}, MissBy: map[string]int{}, RecallBy: map[string]Fraction{},
		// Initialised so the JSON says [] and not null (A-3, from H-11):
		// a consumer must never need null-tolerance for an empty cell.
		Rows: []Row{}, Misses: []Miss{},
	}
	if r.Tags == nil {
		r.Tags = []string{}
	}
	if r.RootNames == nil {
		r.RootNames = []string{}
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

	trace := o.Kind == "trace"
	if trace {
		r.Runs, r.Coverage = o.Runs, o.Coverage
		siteSeen := map[string]bool{}
		for _, e := range h.Edges {
			if _, dup := siteSeen[e.Site.Key()]; !dup {
				siteSeen[e.Site.Key()] = len(byLine[e.Site.Key()]) > 0
			}
		}
		r.SitesTotal = len(siteSeen)
		for _, seen := range siteSeen {
			if seen {
				r.SitesObserved++
			}
		}
	}
	for _, e := range h.Edges {
		row := Row{Edge: e}
		sites := byLine[e.Site.Key()]
		switch {
		case trace:
			row = traceRow(e, sites, loaded)
			if len(sites) > 1 {
				r.Tolerance++
			}
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
		case "suspect":
			tc.Suspect++
			r.Total.Suspect++
		case "unobserved":
			tc.Unobserved++
			r.Total.Unobserved++
			r.SilentBy[row.Reason]++
		}
		r.ByTier[e.Tier] = tc
		r.Rows = append(r.Rows, row)
	}
	if trace {
		if len(h.Edges) > 0 {
			c := float64(r.Total.Confirmed) / float64(len(h.Edges))
			r.ConfirmationRate = &c
		}
		if d := r.Total.Confirmed + r.Total.Suspect; d > 0 {
			sr := float64(r.Total.Suspect) / float64(d)
			r.SuspectRate = &sr
		}
	} else if d := r.Total.Confirmed + r.Total.Contradicted; d > 0 {
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

// traceRow buckets one Hobbes edge against a trace oracle (§3.1).
func traceRow(e edges.HobbesEdge, sites []*edges.Site, loaded map[string]bool) Row {
	row := Row{Edge: e}
	if !loaded[e.Site.Path] {
		row.Bucket, row.Reason = "unobserved", "not-loaded"
		return row
	}
	if len(sites) == 0 {
		row.Bucket, row.Reason = "unobserved", "line-not-called"
		return row
	}
	var targets []edges.Target
	mixed := false
	for _, s := range sites {
		if s.CCallees > 0 {
			mixed = true
		}
		for _, t := range s.Targets {
			if t.External {
				mixed = true
			}
			targets = append(targets, t)
		}
	}
	switch {
	case hasTarget(targets, e.Target):
		row.Bucket = "confirmed"
	case mixed:
		row.Bucket, row.Reason = "unobserved", "line-mixed"
		row.OracleTargets = targets
	default:
		row.Bucket = "suspect"
		row.OracleTargets = targets
	}
	return row
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
//   - macro→* — Rust: a call made by the body of a macro the repo does
//     not define, attributed to the invocation line (macro→generated:
//     to a function the macro also wrote)
//   - observed→* — a trace oracle's pairs, by what the callee is
func missClass(s edges.Site, t edges.Target) string {
	how := "static"
	if s.Mode == "observed" || s.Mode == "macro" {
		how = s.Mode
	}
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
	if t.Kind != "" {
		what = t.Kind
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
	if r.Containment != "" {
		fmt.Fprintf(w, "oracle ran %s (ADR-092)\n", r.Containment)
	}
	if r.Kind == "trace" {
		printTrace(w, r)
		printPoison(w, r)
		return
	}
	defer printPoison(w, r)
	fmt.Fprintf(w, "hobbes edges %d: confirmed %d  contradicted %d  abstract %d  silent %d %v\n",
		r.HobbesEdges, r.Total.Confirmed, r.Total.Contradicted, r.Total.Abstract, r.Total.Silent, r.SilentBy)
	if r.Precision != nil {
		fmt.Fprintf(w, "precision-against-oracle %.1f%% (%d/%d)\n", *r.Precision*100, r.Total.Confirmed, r.Total.Confirmed+r.Total.Contradicted)
	} else {
		fmt.Fprintln(w, "precision-against-oracle: undefined (no confirmed or contradicted edges)")
	}
	if r.State == edges.StateNoRoots {
		// Absence prints as its own state (RR-6): the module has no main
		// or test binary, so RTA had nothing to root at. Not "graded
		// empty" — nothing was graded.
		fmt.Fprintln(w, "recall: NOT GRADED — no roots exist (no main or test binary in the module; files loaded, 0 sites analysed)")
		return
	}
	roots := fmt.Sprintf("at %d roots", r.Roots)
	if r.Kind == "resolution" {
		roots = "over every resolved site in the cell (resolution oracle: no roots)"
	}
	if r.Recall != nil {
		fmt.Fprintf(w, "recall %.1f%% (%d/%d in-repo oracle pairs) %s; external oracle pairs %d; misses %v\n",
			*r.Recall*100, r.RecallHits, r.OraclePairs, roots, r.OracleExternal, r.MissBy)
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

// printTrace is the §3.1 report: no precision line, ever; the
// confirmation rate is labelled coverage-limited; recall is against the
// executed slice and carries the coverage line and the run count.
func printTrace(w io.Writer, r *Report) {
	fmt.Fprintf(w, "hobbes edges %d: confirmed %d  suspect %d  unobserved %d %v\n",
		r.HobbesEdges, r.Total.Confirmed, r.Total.Suspect, r.Total.Unobserved, r.SilentBy)
	if r.ConfirmationRate != nil {
		fmt.Fprintf(w, "confirmation rate %.1f%% (%d/%d hobbes edges; coverage-limited, not precision)\n", *r.ConfirmationRate*100, r.Total.Confirmed, r.HobbesEdges)
	}
	if r.SuspectRate != nil {
		fmt.Fprintf(w, "suspect rate %.1f%% (%d/%d executed hobbes edges; triage queue, never contradicted)\n", *r.SuspectRate*100, r.Total.Suspect, r.Total.Confirmed+r.Total.Suspect)
	}
	if r.Recall != nil {
		fmt.Fprintf(w, "recall-against-executed %.1f%% (%d/%d observed in-repo pairs) over %d run(s) of %v; external python targets %d; misses %v\n",
			*r.Recall*100, r.RecallHits, r.OraclePairs, r.Runs, r.RootNames, r.OracleExternal, r.MissBy)
	} else {
		fmt.Fprintf(w, "recall-against-executed: undefined (no observed in-repo pairs) over %d run(s)\n", r.Runs)
	}
	sitePct := 0.0
	if r.SitesTotal > 0 {
		sitePct = float64(r.SitesObserved) / float64(r.SitesTotal) * 100
	}
	fmt.Fprintf(w, "coverage: hobbes sites observed %d/%d (%.1f%%); files loaded %d/%d; declarations started %d/%d; c-callee calls %d; subprocesses traced %d\n",
		r.SitesObserved, r.SitesTotal, sitePct, r.Coverage["files_loaded"], r.Coverage["files_in_module"],
		r.Coverage["functions_started"], r.Coverage["functions_declared"], r.Coverage["c_callee_calls"], r.Coverage["subprocesses_traced"])
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
		share := 0.0
		if totalMiss > 0 {
			share = float64(f.Pairs-f.Hits) / float64(totalMiss) * 100
		}
		fmt.Fprintf(w, "  recall[%-18s] %5.1f%% (%d/%d)  misses %d = %.1f%% of all misses\n", c, pct(f), f.Hits, f.Pairs, f.Pairs-f.Hits, share)
	}
	tiers := make([]string, 0, len(r.ByTier))
	for t := range r.ByTier {
		tiers = append(tiers, t)
	}
	sort.Strings(tiers)
	for _, t := range tiers {
		c := r.ByTier[t]
		fmt.Fprintf(w, "  tier %-10s confirmed %d  suspect %d  unobserved %d\n", t, c.Confirmed, c.Suspect, c.Unobserved)
	}
	if r.Tolerance > 0 {
		fmt.Fprintf(w, "  line-grain tolerance used on %d edge(s) (several oracle sites on one line)\n", r.Tolerance)
	}
	for _, row := range r.Rows {
		if row.Bucket == "suspect" {
			fmt.Fprintf(w, "  %-12s %s  hobbes %s (%s)  observed %s\n", row.Bucket, row.Edge.Site.Key(), row.Edge.Target.Key(), row.Edge.TargetID, names(row.OracleTargets))
		}
	}
	for _, m := range r.Misses {
		fmt.Fprintf(w, "  missed       %s  %s -> %s (%s) [%s]\n", m.Site.Key(), m.Caller, m.Target.Pos.Key(), m.Target.Name, m.Class)
	}
}

// printPoison is the one line that sees a falsely confirming matcher.
func printPoison(w io.Writer, r *Report) {
	p := r.Poison
	if p == nil {
		fmt.Fprintln(w, "poison check: not run (pass --poison; every cell should)")
		return
	}
	verdict := "PASS"
	if !p.Passed {
		verdict = "FAIL"
	}
	fmt.Fprintf(w, "poison check: %s — %d seeded wrong edges: %d refused, %d unjudged (oracle silent there), %d falsely confirmed\n",
		verdict, p.Seeded, p.Refused, p.Unjudged, p.Confirmed)
	for _, row := range p.Falsely {
		fmt.Fprintf(w, "  FALSELY CONFIRMED %s -> %s (%s)\n", row.Edge.Site.Key(), row.Edge.Target.Key(), row.Edge.TargetID)
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
