// Package knowledge answers the knowledge-layer queries (architecture
// §6, ADR-017) from a repo's derived artifacts: graph_neighborhood,
// who_calls, and tests_guarding over the extracted skeleton, and
// get_module_doc over the M5 narrative artifacts (ADR-019), read fresh
// from .hobbes/derived/ on every call. Answers are agent-facing text
// with file:line provenance and a visible staleness header (P1) — this
// package never writes.
package knowledge

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"slices"
	"sort"
	"strings"

	"gopkg.in/yaml.v3"

	"github.com/majax7714/Hobbes/go/internal/derived"
)

// Store reads one repo's derived artifacts.
type Store struct {
	repoRoot string
}

// Open returns a Store for the repo. No I/O happens until a query.
func Open(repoRoot string) *Store { return &Store{repoRoot: repoRoot} }

// evidence is a file:line citation on an edge.
type evidence struct {
	Path string `json:"path"`
	Line int    `json:"line"`
}

func (e evidence) String() string { return fmt.Sprintf("%s:%d", e.Path, e.Line) }

type edge struct {
	From     string     `json:"from"`
	To       string     `json:"to"`
	Type     string     `json:"type"`
	Tier     string     `json:"tier"`
	Evidence []evidence `json:"evidence"`
}

// qualify marks an edge the reader should trust less. Tier is the graph's
// trust signal (architecture §3.4): a `syntactic` edge is lane A's own
// resolution, kept because the semantic provider could not resolve the
// site and labelled because it can be wrong. An empty tier is a pre-v4
// artifact, which is not a guess and must not be styled as one.
func (e edge) qualify() string {
	if e.Tier == "syntactic" {
		return "  (syntactic — approximate)"
	}
	return ""
}

func (e edge) cite() string {
	if len(e.Evidence) == 0 {
		return ""
	}
	cites := make([]string, len(e.Evidence))
	for i, ev := range e.Evidence {
		cites[i] = ev.String()
	}
	return "  [" + strings.Join(cites, ", ") + "]"
}

type node struct {
	ID   string `json:"id"`
	Kind string `json:"kind"`
	Path string `json:"path"`
}

type symbol struct {
	ID     string `json:"id"`
	Module string `json:"module"`
	Kind   string `json:"kind"`
	Line   int    `json:"line"`
}

type graphDoc struct {
	SHA         string   `json:"sha"`
	Dirty       bool     `json:"dirty"`
	Nodes       []node   `json:"nodes"`
	ModuleEdges []edge   `json:"module_edges"`
	Symbols     []symbol `json:"symbols"`
	SymbolEdges []edge   `json:"symbol_edges"`

	// The honesty surface (ADR-045/047): what the extraction could not
	// account for, classified, plus the environment and degradation
	// records — the inputs list_blind_spots reads.
	ResolutionCoverage []coverageRow     `json:"resolution_coverage"`
	DependencyCoverage []depCoverage     `json:"dependency_coverage"`
	ExtractionErrors   []extractionError `json:"extraction_errors"`
	// Containment is where lane B ran when this artifact was built
	// (ADR-092 phase 3): every step and whether it was contained. Absent
	// in pre-ADR-092 artifacts.
	Containment *containmentDoc `json:"containment"`

	// Per tail-view language, the classes its providers could have
	// reported (C-32) — so an absent class reads as a boundary, not an
	// absence. Stamped by the pipeline; absent in pre-ADR-053 artifacts.
	TailClassesAvailable map[string][]string `json:"tail_classes_available"`
	// Per artifact language, how many repos Hobbes's accuracy was
	// measured on (architecture §3.8, C-31) — a property of Hobbes, not
	// of the repo, stamped so the proxy states it where an agent reads.
	VerificationBase map[string]verificationRow `json:"verification_base"`
}

type verificationRow struct {
	Repos int    `json:"repos"`
	Note  string `json:"note"`
}

type coverageRow struct {
	File       string         `json:"file"`
	Sites      int            `json:"sites"`
	Resolved   int            `json:"resolved"`
	External   int            `json:"external"`
	Unresolved int            `json:"unresolved"`
	Tail       map[string]int `json:"tail"`
}

type depCoverage struct {
	Declared int      `json:"declared"`
	Resolved int      `json:"resolved"`
	Missing  []string `json:"missing"`
}

type extractionError struct {
	Path    string `json:"path"`
	Stage   string `json:"stage"`
	Message string `json:"message"`
}

type test struct {
	ID             string   `json:"id"`
	File           string   `json:"file"`
	Line           int      `json:"line"`
	Reaches        []string `json:"reaches"`
	ReachesModules []string `json:"reaches_modules"`
}

type testsDoc struct {
	SHA   string `json:"sha"`
	Dirty bool   `json:"dirty"`
	Tests []test `json:"tests"`
}

// loadInto reads one derived artifact; a missing file is the one error
// agents can fix themselves, so say how.
func (s *Store) loadInto(name string, v any) error {
	path := filepath.Join(s.repoRoot, ".hobbes", "derived", name)
	data, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return fmt.Errorf("%s not found — run `hobbes ingest` first", path)
	}
	if err != nil {
		return err
	}
	// Version-check before decoding (ADR-028): these answers are cited at
	// agents with file:line, so a silently half-read graph would produce
	// confident wrong provenance. The tools read only fields present since
	// v3, so v4's additive tier/lane do not concern them.
	if err := derived.Unmarshal(name, data, derived.V3Compatible, v); err != nil {
		return err
	}
	return nil
}

// header renders the provenance line every answer starts with, plus a
// stale warning when the repo has moved past the ingest (P1: staleness
// is visible, never silent).
func (s *Store) header(sha string, dirty bool) string {
	h := fmt.Sprintf("knowledge from ingest @ %.12s", sha)
	if dirty {
		h += " (dirty tree)"
	}
	if head := gitHead(s.repoRoot); head != "" && head != sha {
		h += fmt.Sprintf("\nWARNING: repo HEAD is %.12s — artifacts are stale; rerun `hobbes ingest`", head)
	}
	return h + "\n"
}

func gitHead(repoRoot string) string {
	out, err := exec.Command("git", "-C", repoRoot, "rev-parse", "HEAD").Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(out))
}

// suggest lists ids containing the query, for near-miss answers.
func suggest(query string, ids []string) string {
	q := strings.ToLower(query)
	var hits []string
	for _, id := range ids {
		if strings.Contains(strings.ToLower(id), q) {
			hits = append(hits, id)
		}
	}
	sort.Strings(hits)
	if len(hits) == 0 {
		return ""
	}
	if len(hits) > 10 {
		hits = hits[:10]
	}
	return "did you mean:\n  " + strings.Join(hits, "\n  ") + "\n"
}

// Neighborhood answers graph_neighborhood(node): the node's kind, then
// every module edge in and out, with types and provenance.
func (s *Store) Neighborhood(nodeID string) (string, error) {
	var g graphDoc
	if err := s.loadInto("graph.json", &g); err != nil {
		return "", err
	}
	var b strings.Builder
	b.WriteString(s.header(g.SHA, g.Dirty))

	var found *node
	ids := make([]string, len(g.Nodes))
	for i := range g.Nodes {
		ids[i] = g.Nodes[i].ID
		if g.Nodes[i].ID == nodeID {
			found = &g.Nodes[i]
		}
	}
	if found == nil {
		// ADR-073: the planner's map lists "`id` — path"; a 7B passes the
		// path. A path that names exactly one node is that node.
		if found = byPath(g.Nodes, nodeID); found != nil {
			nodeID = found.ID
		}
	}
	if found == nil {
		b.WriteString(fmt.Sprintf("no node %q in the graph\n", nodeID))
		b.WriteString(suggest(nodeID, ids))
		return b.String(), nil
	}

	b.WriteString(fmt.Sprintf("%s (%s", found.ID, found.Kind))
	if found.Path != "" {
		b.WriteString(", " + found.Path)
	}
	b.WriteString(")\n")

	out, in := 0, 0
	for _, e := range g.ModuleEdges {
		if e.From == nodeID {
			if out == 0 {
				b.WriteString("outgoing:\n")
			}
			out++
			b.WriteString(fmt.Sprintf("  -%s-> %s%s\n", e.Type, e.To, e.cite()))
		}
	}
	for _, e := range g.ModuleEdges {
		if e.To == nodeID {
			if in == 0 {
				b.WriteString("incoming:\n")
			}
			in++
			b.WriteString(fmt.Sprintf("  <-%s- %s%s\n", e.Type, e.From, e.cite()))
		}
	}
	if out+in == 0 {
		b.WriteString("no module edges touch this node\n")
	}
	return b.String(), nil
}

// WhoCalls answers who_calls(symbol): every call edge into the symbol,
// with provenance and tier.
//
// Filtered to type "calls" deliberately. Since V2.M2 the symbol layer also
// carries `uses` edges — a resolution no call site claimed: a type
// annotation, an `except` clause, a value passed by name (ADR-029). Those
// are true and useful and they are emphatically not calls, so counting
// them here would make a tool named who_calls answer who_references, which
// is the precise failure ADR-029 was written to avoid. It arrived anyway,
// through the new edge type rather than through a stripped lane, because
// no consumer filtered on type.
//
// They are reported under their own heading rather than dropped: an agent
// asking who calls this usually also wants to know who else names it, and
// silently discarding a true edge is its own kind of dishonesty (P8).
func (s *Store) WhoCalls(symbolID string) (string, error) {
	var g graphDoc
	if err := s.loadInto("graph.json", &g); err != nil {
		return "", err
	}
	var b strings.Builder
	b.WriteString(s.header(g.SHA, g.Dirty))

	callers, users := 0, 0
	var uses strings.Builder
	for _, e := range g.SymbolEdges {
		if e.To != symbolID {
			continue
		}
		switch e.Type {
		case "calls":
			if callers == 0 {
				b.WriteString(fmt.Sprintf("callers of %s:\n", symbolID))
			}
			callers++
			b.WriteString(fmt.Sprintf("  %s%s%s\n", e.From, e.cite(), e.qualify()))
		case "uses":
			users++
			uses.WriteString(fmt.Sprintf("  %s%s\n", e.From, e.cite()))
		}
	}
	if users > 0 {
		if callers == 0 {
			b.WriteString(fmt.Sprintf("no callers of %s\n", symbolID))
		}
		b.WriteString(fmt.Sprintf("references %s without calling it (type annotations, except clauses, values passed by name):\n", symbolID))
		b.WriteString(uses.String())
	}
	if callers > 0 || users > 0 {
		return b.String(), nil
	}

	ids := make([]string, len(g.Symbols))
	known := false
	for i, sym := range g.Symbols {
		ids[i] = sym.ID
		known = known || sym.ID == symbolID
	}
	if known {
		b.WriteString(fmt.Sprintf("no recorded callers of %s (static call edges only — dynamic dispatch is not traced)\n", symbolID))
	} else {
		b.WriteString(fmt.Sprintf("no symbol %q in the graph\n", symbolID))
		b.WriteString(suggest(symbolID, ids))
	}
	return b.String(), nil
}

// TestsGuarding answers tests_guarding(target), where target is a module
// id or a path (file or directory prefix): the tests that statically
// reach it.
func (s *Store) TestsGuarding(target string) (string, error) {
	var g graphDoc
	if err := s.loadInto("graph.json", &g); err != nil {
		return "", err
	}
	var t testsDoc
	if err := s.loadInto("tests.json", &t); err != nil {
		return "", err
	}
	var b strings.Builder
	b.WriteString(s.header(t.SHA, t.Dirty))

	// Resolve target to a set of module ids: an exact module id, or the
	// modules whose source path sits under a path-ish target.
	modules := map[string]bool{}
	var moduleIDs []string
	for _, n := range g.Nodes {
		if n.Kind != "module" {
			continue
		}
		moduleIDs = append(moduleIDs, n.ID)
		if n.ID == target {
			modules[n.ID] = true
		} else if n.Path == target || strings.HasPrefix(n.Path, strings.TrimSuffix(target, "/")+"/") {
			modules[n.ID] = true
		}
	}
	if len(modules) == 0 {
		b.WriteString(fmt.Sprintf("no module matches %q (give a module id or a repo-relative path)\n", target))
		b.WriteString(suggest(target, moduleIDs))
		return b.String(), nil
	}

	guarded := 0
	for _, tc := range t.Tests {
		hit := false
		for _, m := range tc.ReachesModules {
			if modules[m] {
				hit = true
				break
			}
		}
		if !hit {
			continue
		}
		if guarded == 0 {
			b.WriteString(fmt.Sprintf("tests statically reaching %s:\n", target))
		}
		guarded++
		b.WriteString(fmt.Sprintf("  %s  [%s:%d]\n", tc.ID, tc.File, tc.Line))
	}
	if guarded == 0 {
		b.WriteString(fmt.Sprintf("no tests statically reach %s — changes there are unguarded\n", target))
	}
	return b.String(), nil
}

// --- module docs (ADR-019 artifacts) ---------------------------------------

// claim is one pinned narrative sentence (ADR-019).
type claim struct {
	Text string     `json:"text"`
	Pins []evidence `json:"pins"`
}

func (c claim) cite() string {
	if len(c.Pins) == 0 {
		return ""
	}
	cites := make([]string, len(c.Pins))
	for i, p := range c.Pins {
		cites[i] = p.String()
	}
	return "  [" + strings.Join(cites, ", ") + "]"
}

// Source is a blob-stamped file a narrative artifact cites (ADR-019).
// Exported because the web surface (ADR-022) computes the same badge
// over the same stamps; staleness has one implementation.
type Source struct {
	Path    string `json:"path"`
	BlobSHA string `json:"blob_sha"`
}

type moduleDoc struct {
	SHA              string   `json:"sha"`
	Dirty            bool     `json:"dirty"`
	ID               string   `json:"id"`
	Path             string   `json:"path"`
	Sources          []Source `json:"sources"`
	Purpose          claim    `json:"purpose"`
	Responsibilities []claim  `json:"responsibilities"`
	Gotchas          []claim  `json:"gotchas"`
}

// ModuleDoc answers get_module_doc(node): the narrative doc for one
// module — purpose, responsibilities, gotchas, every claim pinned. The
// stale warning is blob-level (ADR-019), not the HEAD compare the
// skeleton tools use: docs regenerate per cited file, so HEAD moving
// on its own proves nothing about this doc.
// byPath resolves a repo-relative path to the one node that carries it
// (a trailing "/" is tolerated); nil when none or several do.
func byPath(nodes []node, p string) *node {
	p = strings.TrimSuffix(p, "/")
	var hit *node
	for i := range nodes {
		if nodes[i].Path != "" && nodes[i].Path == p {
			if hit != nil {
				return nil
			}
			hit = &nodes[i]
		}
	}
	return hit
}

func (s *Store) ModuleDoc(nodeID string) (string, error) {
	// TS/JS module ids are repo-relative paths (ADR-021), so "/" is
	// legal and artifacts nest under docs/modules/; traversal is not.
	if nodeID == "" || strings.HasPrefix(nodeID, "/") ||
		strings.Contains(nodeID, "\\") || path.Clean(nodeID) != nodeID ||
		slices.Contains(strings.Split(nodeID, "/"), "..") {
		return "", fmt.Errorf("%q is not a module id", nodeID)
	}
	dir := filepath.Join(s.repoRoot, ".hobbes", "derived", "docs", "modules")
	data, err := os.ReadFile(filepath.Join(dir, filepath.FromSlash(nodeID)+".json"))
	if os.IsNotExist(err) {
		ids := docIDs(dir)
		if len(ids) == 0 {
			return "", fmt.Errorf("no module docs generated — run `hobbes narrate` first")
		}
		return fmt.Sprintf("no module doc for %q\n%s", nodeID, suggest(nodeID, ids)), nil
	}
	if err != nil {
		return "", err
	}
	var d moduleDoc
	if err := json.Unmarshal(data, &d); err != nil {
		return "", fmt.Errorf("module doc %s: %w", nodeID, err)
	}

	var b strings.Builder
	fmt.Fprintf(&b, "knowledge from narrate @ %.12s", d.SHA)
	if d.Dirty {
		b.WriteString(" (dirty tree)")
	}
	b.WriteString("\n")
	if changed := s.changedSources(d.Sources); len(changed) > 0 {
		fmt.Fprintf(&b,
			"WARNING: STALE — cited files changed since generation: %s; rerun `hobbes narrate`\n",
			strings.Join(changed, ", "))
	}
	fmt.Fprintf(&b, "module %s (%s)\n", d.ID, d.Path)
	fmt.Fprintf(&b, "purpose: %s%s\n", d.Purpose.Text, d.Purpose.cite())
	for _, section := range []struct {
		title  string
		claims []claim
	}{{"responsibilities", d.Responsibilities}, {"gotchas", d.Gotchas}} {
		if len(section.claims) == 0 {
			continue
		}
		b.WriteString(section.title + ":\n")
		for _, c := range section.claims {
			fmt.Fprintf(&b, "  - %s%s\n", c.Text, c.cite())
		}
	}
	return b.String(), nil
}

// docIDs lists the module ids with docs on disk (nested dirs included,
// ADR-021), for near-miss answers.
func docIDs(dir string) []string {
	var ids []string
	_ = filepath.WalkDir(dir, func(p string, d os.DirEntry, err error) error {
		if err != nil || d.IsDir() {
			return nil
		}
		if rel, relErr := filepath.Rel(dir, p); relErr == nil {
			if name, ok := strings.CutSuffix(filepath.ToSlash(rel), ".json"); ok {
				ids = append(ids, name)
			}
		}
		return nil
	})
	return ids
}

// changedSources reports which of this store's stamped sources changed.
func (s *Store) changedSources(sources []Source) []string {
	return ChangedSources(s.repoRoot, sources)
}

// ChangedSources reports which stamped sources' working-tree blobs no
// longer match (ADR-019 staleness). A vanished file counts as changed;
// git being unavailable degrades to no warning, like gitHead.
func ChangedSources(repoRoot string, sources []Source) []string {
	return ChangedSourcesMulti(repoRoot, map[string][]Source{"": sources})[""]
}

// ChangedSourcesMulti answers ChangedSources for several artifacts at
// once, hashing the working tree in a single git call. The web surface's
// docs index (ADR-022) asks the badge question about every artifact on
// every load; one subprocess per artifact would be the whole cost of the
// endpoint.
func ChangedSourcesMulti(repoRoot string, bySources map[string][]Source) map[string][]string {
	// Hash every distinct existing path once, then answer per artifact.
	wanted := map[string]bool{}
	for _, sources := range bySources {
		for _, src := range sources {
			if _, err := os.Stat(filepath.Join(repoRoot, src.Path)); err == nil {
				wanted[src.Path] = true
			}
		}
	}
	existing := make([]string, 0, len(wanted))
	for p := range wanted {
		existing = append(existing, p)
	}
	sort.Strings(existing)

	current := map[string]string{}
	if len(existing) > 0 {
		cmd := exec.Command("git", "-C", repoRoot, "hash-object", "--stdin-paths")
		cmd.Stdin = strings.NewReader(strings.Join(existing, "\n") + "\n")
		if out, err := cmd.Output(); err == nil {
			if hashes := strings.Fields(string(out)); len(hashes) == len(existing) {
				for i, p := range existing {
					current[p] = hashes[i]
				}
			}
		}
	}

	result := make(map[string][]string, len(bySources))
	for id, sources := range bySources {
		changed := map[string]bool{}
		for _, src := range sources {
			if !wanted[src.Path] {
				changed[src.Path] = true // gone
				continue
			}
			// An unhashable tree (no git) leaves current empty: no badge,
			// same degradation as gitHead.
			if h, ok := current[src.Path]; ok && h != src.BlobSHA {
				changed[src.Path] = true
			}
		}
		out := make([]string, 0, len(changed))
		for p := range changed {
			out = append(out, p)
		}
		sort.Strings(out)
		result[id] = out
	}
	return result
}

// --- invariants (ADR-024) ---------------------------------------------------

// invariantRecord is one confirmed rule from .hobbes/invariants/. Only
// the fields an agent needs to obey it are read; the compile rule is the
// compiler's business, and its target is enough to say how it is checked.
type invariantRecord struct {
	ID        string   `yaml:"id"`
	Statement string   `yaml:"statement"`
	Scope     string   `yaml:"scope"`
	Status    string   `yaml:"status"`
	GuardedBy []string `yaml:"guarded_by"`
	// Check is how the record is held (graph | emit | soft, ADR-039);
	// Compile.Target names the CI tool for emit records.
	Check   string `yaml:"check"`
	Compile struct {
		Target string `yaml:"target"`
	} `yaml:"compile"`
}

// ListInvariants answers list_invariants(scope): the confirmed rules
// that bind a path, so a session knows the constraints before it writes
// code rather than after review (ADR-017's fifth tool, whose data
// arrived with M8).
//
// An empty scope lists everything. Scope matching is the ADR-024 rule: a
// record binds a path when its own scope contains that path, or the
// other way round — asking about the repo root should not hide a rule
// scoped to a subdirectory inside it.
func (s *Store) ListInvariants(scope string) (string, error) {
	dir := filepath.Join(s.repoRoot, ".hobbes", "invariants")
	entries, err := os.ReadDir(dir)
	if os.IsNotExist(err) {
		return "no invariants directory — none have been confirmed for this repo\n", nil
	}
	if err != nil {
		return "", err
	}

	var records []invariantRecord
	skipped := 0
	for _, entry := range entries {
		if entry.IsDir() || filepath.Ext(entry.Name()) != ".yaml" {
			continue
		}
		data, readErr := os.ReadFile(filepath.Join(dir, entry.Name()))
		if readErr != nil {
			continue
		}
		var record invariantRecord
		if yaml.Unmarshal(data, &record) != nil || record.ID == "" {
			continue
		}
		if record.Status != "confirmed" {
			skipped++
			continue
		}
		if scope != "" && !scopeOverlaps(record.Scope, scope) {
			continue
		}
		records = append(records, record)
	}
	sort.Slice(records, func(i, j int) bool { return records[i].ID < records[j].ID })

	var b strings.Builder
	if scope == "" {
		fmt.Fprintf(&b, "confirmed invariants (%d)\n", len(records))
	} else {
		fmt.Fprintf(&b, "confirmed invariants binding %s (%d)\n", scope, len(records))
	}
	if len(records) == 0 {
		b.WriteString("  none — nothing has been confirmed for this scope\n")
	}
	for _, record := range records {
		var how string
		switch record.Check {
		case "soft":
			how = "soft (a reviewer judges it; cite evidence)"
		case "graph":
			how = "graph (the unified checker judges it on every review)"
		case "emit":
			how = "emit:" + record.Compile.Target
		default:
			// A pre-ADR-039 record; show what it carries rather than
			// guessing what it meant.
			how = record.Compile.Target
			if how == "soft" {
				how = "soft (a reviewer judges it; cite evidence)"
			}
		}
		fmt.Fprintf(&b, "%s [scope %s, checked by %s]\n  %s\n",
			record.ID, record.Scope, how, record.Statement)
		if len(record.GuardedBy) > 0 {
			fmt.Fprintf(&b, "  guarded by: %s\n", strings.Join(record.GuardedBy, ", "))
		}
	}
	if skipped > 0 {
		fmt.Fprintf(&b, "(%d record(s) not confirmed, so not binding)\n", skipped)
	}
	return b.String(), nil
}

// scopeOverlaps reports whether a record's scope and a queried scope
// touch the same tree in either direction.
// tailMeanings explains each ADR-045 tail class in an agent's terms and
// names the register entry it points to. Mirrors pipeline tail.py — the
// class vocabulary is shared, and each meaning is an observation, never
// a probability about a hypothetical edge (C-2's rule).
var tailMeanings = []struct{ class, meaning string }{
	{"fallback-resolved", "has a syntactic-tier edge from lane A's own resolver; semantics could not confirm it (C-7) — trust it less"},
	{"local-binding", "bound below the modelled vocabulary in its own file — a parameter, local, or nested def (C-9); seen and deliberately not modelled, the call stays inside that file"},
	{"nested-decl", "declared in another repo file below the modelled vocabulary (C-9)"},
	{"external-origin", "every declaration lives outside the repo — a dependency or ambient lib; often an environment gap (C-23/C-27/C-30)"},
	{"import-binding", "bound by a same-file import; where the call lands is unresolved — usually a missing environment (C-23/C-27/C-30)"},
	{"builtin-name", "the name matches the language's builtin list — language machinery, not architecture"},
	{"attr-call", "an attribute call whose receiver no static provider could type — the genuine limit (C-2); verify these targets yourself where they matter"},
	{"path-call", "a ::-qualified call the index left dark"},
	{"unclassified", "no observation applies — genuinely unknown; read this code yourself"},
}

// notModelled marks the classes the graph sees and deliberately
// abstains from (ADR-045's rollup) — knowledge, not ignorance.
var notModelled = map[string]bool{
	"local-binding": true, "nested-decl": true, "builtin-name": true,
	// A site the semantic lane resolved below the symbol floor — an
	// interface method, a closure — counted resolved, drawing no edge
	// (C-58); the tail names it per file since 2026-08-25.
	"below-floor": true,
}

// artifactLangBucket maps graph.json's language names onto the tail
// view's buckets, so a verification row can be matched to the call
// sites under a scope. hcl has no call sites and maps to nothing.
var artifactLangBucket = map[string]string{
	"python": "python", "typescript": "ts/js", "javascript": "ts/js",
	"go": "go", "rust": "rust",
}

var langByExt = map[string]string{
	".py": "python", ".ts": "ts/js", ".tsx": "ts/js", ".js": "ts/js",
	".jsx": "ts/js", ".mjs": "ts/js", ".cjs": "ts/js", ".go": "go",
	".rs": "rust",
}

// containmentDoc mirrors the pipeline's containment.summary().
type containmentDoc struct {
	Steps        []containmentStep `json:"steps"`
	AllContained bool              `json:"all_contained"`
	EscapeHatch  bool              `json:"escape_hatch"`
}

type containmentStep struct {
	Step      string `json:"step"`
	Contained bool   `json:"contained"`
	Reason    string `json:"reason,omitempty"`
}

// ListBlindSpots answers list_blind_spots(scope): what Hobbes cannot
// see under a path, stated as classified counts with the register
// entry each limit points to (ADR-047). This is the complement of
// every other knowledge tool: they serve the captured fraction; this
// serves the boundary, so an agent knows which context it must gather
// and verify itself. Scope is a repo-relative path prefix, "." for the
// whole repo.
func (s *Store) ListBlindSpots(scope string) (string, error) {
	var g graphDoc
	if err := s.loadInto("graph.json", &g); err != nil {
		return "", err
	}
	prefix := scope
	if prefix == "." {
		prefix = ""
	}
	var rows []coverageRow
	for _, row := range g.ResolutionCoverage {
		if strings.HasPrefix(row.File, prefix) {
			rows = append(rows, row)
		}
	}
	if len(rows) == 0 && scope != "." {
		return "", fmt.Errorf(
			"no detected call sites under %q — scope is a repo-relative "+
				"path prefix (e.g. src/app), or \".\" for the whole repo", scope)
	}

	var b strings.Builder
	b.WriteString(s.header(g.SHA, g.Dirty))
	fmt.Fprintf(&b, "what Hobbes cannot see under %s — the work to verify yourself:\n\n", scope)
	b.WriteString("never in any count below, because it is not detected at all: dynamic\n" +
		"dispatch and calls through values (C-1), fixture-injected test reach\n" +
		"(C-4), computed route paths (C-5). Every percentage here is a floor\n" +
		"over DETECTED call sites, not over the repo.\n")
	// Languages with detected call sites under the scope, by tail bucket
	// — the scoped verification line names only these (whole-repo scope
	// names every language the artifact lists, call sites or not).
	inScope := map[string]bool{}
	for _, row := range rows {
		if lang, ok := langByExt[path.Ext(row.File)]; ok {
			inScope[lang] = true
		}
	}
	first := true
	for _, lang := range sortedKeys(g.VerificationBase) {
		if scope != "." && !inScope[artifactLangBucket[lang]] {
			continue
		}
		if first {
			b.WriteString("\nverification base — a sample, not the language (C-31, architecture §3.8):\n")
			first = false
		}
		fmt.Fprintf(&b, "  %s: %s\n", lang, g.VerificationBase[lang].Note)
	}

	type agg struct {
		sites, unresolved int
		tail              map[string]int
	}
	langs := map[string]*agg{}
	for _, row := range rows {
		lang, ok := langByExt[path.Ext(row.File)]
		if !ok {
			continue
		}
		a := langs[lang]
		if a == nil {
			a = &agg{tail: map[string]int{}}
			langs[lang] = a
		}
		a.sites += row.Sites
		a.unresolved += row.Unresolved
		for class, n := range row.Tail {
			a.tail[class] += n
		}
	}
	present := map[string]bool{}
	for _, lang := range sortedKeys(langs) {
		a := langs[lang]
		if a.sites == 0 {
			continue
		}
		accounted := float64(a.sites-a.unresolved) / float64(a.sites) * 100
		fmt.Fprintf(&b, "\ncapture [%s]: %.1f%% of %d detected call sites accounted\n",
			lang, accounted, a.sites)
		seen, cannot := groupLine(a.tail, true), groupLine(a.tail, false)
		if seen != "" {
			fmt.Fprintf(&b, "  seen, not modelled by design: %s\n", seen)
		}
		if cannot != "" {
			fmt.Fprintf(&b, "  cannot resolve: %s\n", cannot)
		}
		if missing := classesMissing(lang, g.TailClassesAvailable); missing != "" {
			fmt.Fprintf(&b, "  classes this lane cannot report: %s (C-32)\n", missing)
		}
		for class := range a.tail {
			present[class] = true
		}
	}

	for _, dc := range g.DependencyCoverage {
		if len(dc.Missing) == 0 {
			continue
		}
		fmt.Fprintf(&b, "\nenvironment gap: %d/%d declared packages resolved; missing: %s\n"+
			"  (third-party calls into these are invisible, not absent — C-23/C-27/C-30)\n",
			dc.Resolved, dc.Declared, strings.Join(dc.Missing, ", "))
	}
	if c := g.Containment; c != nil && (!c.AllContained || c.EscapeHatch) {
		// The guarantee not holding is a boundary like any other here:
		// an artifact whose lane B ran on the host says so where the
		// agent reads the boundary (C-64).
		host := 0
		reasons := map[string]bool{}
		for _, s := range c.Steps {
			if !s.Contained {
				host++
				reasons[s.Reason] = true
			}
		}
		why := make([]string, 0, len(reasons))
		for r := range reasons {
			why = append(why, r)
		}
		sort.Strings(why)
		fmt.Fprintf(&b, "\ncontainment: %d of %d lane B step(s) ran on the host (%s) — repo code may have executed there; this artifact was not built under the ADR-092 guarantee (C-64)\n",
			host, len(c.Steps), strings.Join(why, "; "))
	}
	for i, e := range g.ExtractionErrors {
		if i == 10 {
			fmt.Fprintf(&b, "  … and %d more degradation records\n", len(g.ExtractionErrors)-10)
			break
		}
		fmt.Fprintf(&b, "\ndegraded: %s: %s: %s\n", e.Path, e.Stage, e.Message)
	}

	worst := slices.Clone(rows)
	sort.Slice(worst, func(i, j int) bool { return worst[i].Unresolved > worst[j].Unresolved })
	shown := 0
	for _, row := range worst {
		if row.Unresolved == 0 || shown == 10 {
			break
		}
		if shown == 0 {
			b.WriteString("\nlargest unresolved remainders:\n")
		}
		fmt.Fprintf(&b, "  %s — %d of %d sites unresolved (%s)\n",
			row.File, row.Unresolved, row.Sites, classList(row.Tail))
		shown++
	}
	if shown == 0 {
		b.WriteString("\nevery detected call site under this scope is accounted for.\n")
	}

	first = true
	for _, m := range tailMeanings {
		if !present[m.class] {
			continue
		}
		if first {
			b.WriteString("\nwhat each class means (an observation, never a guess):\n")
			first = false
		}
		fmt.Fprintf(&b, "  %s — %s\n", m.class, m.meaning)
	}
	return b.String(), nil
}

func sortedKeys[V any](m map[string]V) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}

// classesMissing names, in class order, the tail classes a language's
// providers could not have reported (C-32) — "" when the artifact does
// not carry the table or the language can report every class.
func classesMissing(lang string, available map[string][]string) string {
	classes, ok := available[lang]
	if !ok {
		return ""
	}
	can := map[string]bool{}
	for _, c := range classes {
		can[c] = true
	}
	var out []string
	for _, m := range tailMeanings {
		if !can[m.class] {
			out = append(out, m.class)
		}
	}
	return strings.Join(out, ", ")
}

// groupLine renders one rollup group of a tail, in class order.
func groupLine(tail map[string]int, wantNotModelled bool) string {
	total := 0
	var parts []string
	for _, m := range tailMeanings {
		n := tail[m.class]
		if n == 0 || notModelled[m.class] != wantNotModelled {
			continue
		}
		total += n
		parts = append(parts, fmt.Sprintf("%s %d", m.class, n))
	}
	if total == 0 {
		return ""
	}
	return fmt.Sprintf("%d (%s)", total, strings.Join(parts, ", "))
}

func classList(tail map[string]int) string {
	if len(tail) == 0 {
		return "unclassified — pre-ADR-045 artifact, re-run `hobbes ingest`"
	}
	var parts []string
	for _, m := range tailMeanings {
		if n := tail[m.class]; n > 0 {
			parts = append(parts, fmt.Sprintf("%s %d", m.class, n))
		}
	}
	return strings.Join(parts, ", ")
}

func scopeOverlaps(recordScope, query string) bool {
	record := strings.TrimSuffix(strings.TrimSpace(recordScope), "/")
	q := strings.TrimSuffix(strings.TrimSpace(query), "/")
	if record == "." || record == "" || q == "." || q == "" {
		return true
	}
	return record == q ||
		strings.HasPrefix(q, record+"/") ||
		strings.HasPrefix(record, q+"/")
}
