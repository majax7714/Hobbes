// Package knowledge answers the knowledge-layer queries (architecture
// §6, ADR-017) from a repo's derived artifacts: graph_neighborhood,
// who_calls, and tests_guarding over the extracted skeleton, and
// get_module_doc over the M5 narrative artifacts (ADR-019). Answers are
// agent-facing text with file:line provenance and a visible staleness
// header (P1) — this package never writes.
//
// The graph and the test map are decoded once and served until their
// file changes (ADR-118): every answer used to re-read and re-decode the
// whole artifact — 8 MB on this repo, 980 MB on ScummVM — and scan every
// edge. The store keeps the decoded document with the file's size and
// modification time, re-checks both on every call, and reloads when
// either moves; a missing file is reported, never served from memory.
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
	"sync"
	"time"

	"gopkg.in/yaml.v3"

	"github.com/majax7714/Hobbes/go/internal/derived"
)

// Store reads one repo's derived artifacts, decoding each once per
// version of its file (ADR-118).
type Store struct {
	repoRoot string

	mu    sync.Mutex
	graph *cachedGraph
	tests *cachedTests
}

// Open returns a Store for the repo. No I/O happens until a query.
func Open(repoRoot string) *Store { return &Store{repoRoot: repoRoot} }

// readArtifact reads an artifact's bytes; a test swaps it to count reads.
var readArtifact = os.ReadFile

// fileStamp is what decides whether a cached artifact is still the file
// on disk: an ingest rewrites the file, which moves its modification
// time and, almost always, its size. Both are compared on every call.
type fileStamp struct {
	modTime time.Time
	size    int64
}

type cachedGraph struct {
	stamp fileStamp
	doc   *graphDoc
	idx   *graphIndex
}

type cachedTests struct {
	stamp fileStamp
	doc   *testsDoc
}

// graphIndex is built once per decoded graph: edges by endpoint, as
// positions into the document's own slices so an answer lists them in
// the artifact's order, exactly as the scan it replaces did.
type graphIndex struct {
	nodeByID    map[string]int
	nodeIDs     []string
	symbolIDs   []string
	symbolKnown map[string]bool
	moduleFrom  map[string][]int
	moduleTo    map[string][]int
	symbolTo    map[string][]int
	// C-153's region as a set, so marking a caller costs one lookup.
	cppPattern map[string]bool
	// The symbols lane B declared (ADR-129), the same way. Empty on every
	// graph built before minting and on every repo without C or C++.
	laneBDeclared map[string]bool
	// Those among them whose extent was read (ADR-134): `extent: "braces"`.
	laneBExtent map[string]bool
}

// mintedNote marks a symbol whose definition lane A never parsed: lane B's
// index gave the file, line and kind, so the node exists and calls resolve
// to it (ADR-129). Whether it is also a scope depends on ADR-134: where the
// body's extent could be read from the file's own braces the symbol's
// outgoing calls are drawn from it, and where that read was refused (a
// preprocessor conditional in the body, another definition's line inside
// it) the node stays a target, its own calls attributed to whatever lane A
// did parse around them. A reader of who_calls is told which — said here
// rather than left to be discovered (P8, C-145). The mint marks a read
// extent on the symbol (`extent: "braces"`), because end_line alone cannot
// tell a body of one line from a refusal.
func (idx *graphIndex) mintedNote(symbolID string) string {
	if !idx.laneBDeclared[symbolID] {
		return ""
	}
	if idx.laneBExtent[symbolID] {
		return "  (definition read from the index: lane A's parse lost it to a macro, C-145 — its body's extent was read from the file's braces, ADR-134, so the calls written inside it are drawn from it; no key grades a C++ caller)\n"
	}
	return "  (definition read from the index: lane A's parse lost it to a macro, C-145 — a target only: its own calls are attributed to the enclosing symbol or the module)\n"
}

// templateNote marks a caller whose edge starts in a C++ template pattern
// (C-153, ADR-125 §4). It marks the region, not the wrong edge: a call in a
// pattern is usually resolved right, and the ones that are not cannot be
// told apart at the site. Only a semantic edge carries it — a syntactic one
// is lane A's own guess, which qualify() already says, and scip-clang had no
// answer there to be wrong.
func (idx *graphIndex) templateNote(e edge) string {
	if e.Tier != "semantic" || !idx.cppPattern[e.From] {
		return ""
	}
	return "  (C-153: from a C++ template pattern — scip-clang's one answer there can name another specialisation's declaration)"
}

func indexGraph(g *graphDoc) *graphIndex {
	idx := &graphIndex{
		nodeByID:    make(map[string]int, len(g.Nodes)),
		nodeIDs:     make([]string, len(g.Nodes)),
		symbolIDs:   make([]string, len(g.Symbols)),
		symbolKnown: make(map[string]bool, len(g.Symbols)),
		moduleFrom:  map[string][]int{},
		moduleTo:    map[string][]int{},
		symbolTo:    map[string][]int{},
		cppPattern:  make(map[string]bool, len(g.CppTemplatePatterns)),

		laneBDeclared: map[string]bool{},
		laneBExtent:   map[string]bool{},
	}
	for _, id := range g.CppTemplatePatterns {
		idx.cppPattern[id] = true
	}
	for i := range g.Nodes {
		idx.nodeByID[g.Nodes[i].ID] = i
		idx.nodeIDs[i] = g.Nodes[i].ID
	}
	for i := range g.Symbols {
		idx.symbolIDs[i] = g.Symbols[i].ID
		idx.symbolKnown[g.Symbols[i].ID] = true
		if g.Symbols[i].DeclaredBy == "scip" {
			idx.laneBDeclared[g.Symbols[i].ID] = true
			if g.Symbols[i].Extent == "braces" {
				idx.laneBExtent[g.Symbols[i].ID] = true
			}
		}
	}
	for i := range g.ModuleEdges {
		e := &g.ModuleEdges[i]
		idx.moduleFrom[e.From] = append(idx.moduleFrom[e.From], i)
		idx.moduleTo[e.To] = append(idx.moduleTo[e.To], i)
	}
	for i := range g.SymbolEdges {
		e := &g.SymbolEdges[i]
		idx.symbolTo[e.To] = append(idx.symbolTo[e.To], i)
	}
	return idx
}

// artifactStamp stats one artifact; a missing file is the one error
// agents can fix themselves, so say how — and it is never served from
// memory: an artifact that has gone is gone.
func (s *Store) artifactStamp(name string) (fileStamp, error) {
	path := filepath.Join(s.repoRoot, ".hobbes", "derived", name)
	info, err := os.Stat(path)
	if os.IsNotExist(err) {
		return fileStamp{}, fmt.Errorf("%s not found — run `hobbes ingest` first", path)
	}
	if err != nil {
		return fileStamp{}, err
	}
	return fileStamp{modTime: info.ModTime(), size: info.Size()}, nil
}

// loadGraph returns the decoded graph and its index, decoding only when
// graph.json has changed since the last call.
func (s *Store) loadGraph() (*graphDoc, *graphIndex, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	stamp, err := s.artifactStamp("graph.json")
	if err != nil {
		s.graph = nil
		return nil, nil, err
	}
	if s.graph != nil && s.graph.stamp == stamp {
		return s.graph.doc, s.graph.idx, nil
	}
	var g graphDoc
	if err := s.loadInto("graph.json", &g); err != nil {
		s.graph = nil
		return nil, nil, err
	}
	s.graph = &cachedGraph{stamp: stamp, doc: &g, idx: indexGraph(&g)}
	return s.graph.doc, s.graph.idx, nil
}

// loadTests is loadGraph for tests.json.
func (s *Store) loadTests() (*testsDoc, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	stamp, err := s.artifactStamp("tests.json")
	if err != nil {
		s.tests = nil
		return nil, err
	}
	if s.tests != nil && s.tests.stamp == stamp {
		return s.tests.doc, nil
	}
	var t testsDoc
	if err := s.loadInto("tests.json", &t); err != nil {
		s.tests = nil
		return nil, err
	}
	s.tests = &cachedTests{stamp: stamp, doc: &t}
	return s.tests.doc, nil
}

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
	// "braces" on a symbol lane B declared whose body's extent the mint
	// read from the file's own text (ADR-134); empty on every other symbol
	// and on every artifact written before it.
	Extent string `json:"extent"`
	// Which lane spelled this definition (ADR-129). Empty on every lane A
	// symbol and on every artifact written before minting existed;
	// "scip" on a definition lane A's parse lost and lane B's index gave
	// back, which who_calls says out loud.
	DeclaredBy string `json:"declared_by"`
}

// builtBy is the pipeline's provenance stamp (ADR-094): which checkout
// and commit produced the artifact, and since ADR-103 which Hobbes
// version. Absent on artifacts older than it; Version empty on those
// between.
type builtBy struct {
	Version  string `json:"version"`
	Checkout string `json:"checkout"`
	SHA      string `json:"sha"`
	Dirty    bool   `json:"dirty"`
}

type graphDoc struct {
	SHA         string   `json:"sha"`
	Dirty       bool     `json:"dirty"`
	BuiltBy     *builtBy `json:"built_by"`
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
	// C-153's region (ADR-125 §4): the ids of the C++ symbols that are a
	// template pattern and call something semantically. scip-clang indexes
	// a pattern once, so its one answer at a call inside one can name
	// another specialisation's declaration — who_calls says so on the
	// lines that come from here. Absent in pre-ADR-125 artifacts and in
	// every repo without C++, which then render exactly as before.
	CppTemplatePatterns []string `json:"cpp_template_patterns"`
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
	File string `json:"file"`
	// The language the provider that owns the file claimed, when the
	// extension cannot say: a `.h` the C++ walk claimed is C++, not C
	// (ADR-113 §1). Absent on every other row, and on every artifact
	// written before it.
	Language   string         `json:"language,omitempty"`
	Sites      int            `json:"sites"`
	Resolved   int            `json:"resolved"`
	External   int            `json:"external"`
	Unresolved int            `json:"unresolved"`
	Tail       map[string]int `json:"tail"`
}

// language buckets a coverage row for the tail view: the row's own
// language when its provider stamped one, else its extension's. Mirrors
// the pipeline's tail.language_of, whose second argument is this same
// row field.
func (row coverageRow) language() (string, bool) {
	if row.Language != "" {
		return row.Language, true
	}
	lang, ok := langByExt[path.Ext(row.File)]
	return lang, ok
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
	// ThroughFixtures are the reached modules a pytest test reaches only by
	// way of a fixture injection (ADR-137): pytest calls the fixture on the
	// test's behalf, so the step is real, and it is not a call the test
	// wrote. Absent on other frameworks' records and on older artifacts.
	ThroughFixtures []string `json:"through_fixtures"`
	// ThroughAutouse maps each module the test reaches only through an
	// autouse fixture — one nothing on the test names — to the fixtures
	// that got it there (ADR-139). A module is never in both lists.
	ThroughAutouse map[string][]string `json:"through_autouse"`
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
	data, err := readArtifact(path)
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
func (s *Store) header(sha string, dirty bool, built *builtBy) string {
	h := fmt.Sprintf("knowledge from ingest @ %.12s", sha)
	if dirty {
		h += " (dirty tree)"
	}
	if built != nil {
		// Which Hobbes made the artifact (ADR-094): a stale install on
		// PATH once ingested with pre-containment code and nothing said
		// so. Stated on every answer, beside the repo commit it maps.
		rev := built.SHA
		if rev == "" {
			rev = "no git commit"
		}
		h += "; built by hobbes"
		if built.Version != "" {
			h += " " + built.Version
		}
		h += fmt.Sprintf(" @ %.12s", rev)
		if built.Dirty {
			h += " (dirty)"
		}
		h += " from " + built.Checkout
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
	g, idx, err := s.loadGraph()
	if err != nil {
		return "", err
	}
	var b strings.Builder
	b.WriteString(s.header(g.SHA, g.Dirty, g.BuiltBy))

	var found *node
	ids := idx.nodeIDs
	if i, ok := idx.nodeByID[nodeID]; ok {
		found = &g.Nodes[i]
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
	for _, i := range idx.moduleFrom[nodeID] {
		e := g.ModuleEdges[i]
		if out == 0 {
			b.WriteString("outgoing:\n")
		}
		out++
		b.WriteString(fmt.Sprintf("  -%s-> %s%s\n", e.Type, e.To, e.cite()))
	}
	for _, i := range idx.moduleTo[nodeID] {
		e := g.ModuleEdges[i]
		if in == 0 {
			b.WriteString("incoming:\n")
		}
		in++
		b.WriteString(fmt.Sprintf("  <-%s- %s%s\n", e.Type, e.From, e.cite()))
	}
	if out+in == 0 {
		b.WriteString("no module edges touch this node\n")
	}
	return b.String(), nil
}

// WhoCalls answers who_calls(symbol): every call edge into the symbol,
// with provenance and tier — and, under their own headings, the `uses`
// and `implements` edges into it.
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
	g, idx, err := s.loadGraph()
	if err != nil {
		return "", err
	}
	var b strings.Builder
	b.WriteString(s.header(g.SHA, g.Dirty, g.BuiltBy))
	// Before any caller: what the symbol itself is (ADR-129 §5). It
	// qualifies every line below it, including "no recorded callers".
	b.WriteString(idx.mintedNote(symbolID))

	callers, users, implementors := 0, 0, 0
	var uses, implemented strings.Builder
	for _, i := range idx.symbolTo[symbolID] {
		e := g.SymbolEdges[i]
		switch e.Type {
		case "calls":
			if callers == 0 {
				b.WriteString(fmt.Sprintf("callers of %s:\n", symbolID))
			}
			callers++
			b.WriteString(fmt.Sprintf("  %s%s%s%s\n", e.From, e.cite(), e.qualify(), idx.templateNote(e)))
		case "uses":
			users++
			uses.WriteString(fmt.Sprintf("  %s%s\n", e.From, e.cite()))
		case "implements":
			implementors++
			implemented.WriteString(fmt.Sprintf("  %s%s\n", e.From, e.cite()))
		}
	}
	if users > 0 || implementors > 0 {
		if callers == 0 {
			b.WriteString(fmt.Sprintf("no callers of %s\n", symbolID))
		}
	}
	if users > 0 {
		// A `uses` edge is a resolution no detected call site claimed
		// (ADR-029): a type annotation, an except clause, a value passed
		// by name — or a call through a receiver lane A could not see
		// (C-1). Worded as what is known, not as "not a call" (C-80).
		b.WriteString(fmt.Sprintf("references %s where no call site was detected (type annotations, except clauses, values passed by name; a call through a receiver lane A cannot see, C-1):\n", symbolID))
		b.WriteString(uses.String())
	}
	if implementors > 0 {
		// The override set (ADR-120): what the index states implements or
		// overrides this symbol. A call to an interface method reaches one
		// of these at run time — which one, the graph does not say (C-58).
		b.WriteString(fmt.Sprintf("implemented or overridden by (a call to %s may reach any of these; which one is not traced, C-58):\n", symbolID))
		b.WriteString(implemented.String())
	}
	if callers > 0 || users > 0 || implementors > 0 {
		return b.String(), nil
	}

	ids := idx.symbolIDs
	if idx.symbolKnown[symbolID] {
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
	g, _, err := s.loadGraph()
	if err != nil {
		return "", err
	}
	t, err := s.loadTests()
	if err != nil {
		return "", err
	}
	var b strings.Builder
	b.WriteString(s.header(t.SHA, t.Dirty, nil))

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
	// An autouse fixture runs before every test in its scope, so a module
	// it reaches is "guarded" by all of them at once. That is true, and a
	// list of every test in the suite answers no question a reader has:
	// those tests are counted and said once, with the fixtures, below the
	// list (ADR-139). A test that also reaches the target any other way
	// is listed as it always was.
	blanket := 0
	blanketFixtures := map[string]bool{}
	for _, tc := range t.Tests {
		hit, direct, named := false, false, false
		viaFixture := map[string]bool{}
		for _, m := range tc.ThroughFixtures {
			viaFixture[m] = true
		}
		var autouse []string
		for _, m := range tc.ReachesModules {
			if !modules[m] {
				continue
			}
			hit = true
			switch fixtures, only := tc.ThroughAutouse[m]; {
			case only:
				autouse = append(autouse, fixtures...)
			case viaFixture[m]:
				named = true
			default:
				direct = true
			}
		}
		if !hit {
			continue
		}
		if !direct && !named {
			blanket++
			for _, fixture := range autouse {
				blanketFixtures[fixture] = true
			}
			continue
		}
		if guarded == 0 {
			b.WriteString(fmt.Sprintf("tests statically reaching %s:\n", target))
		}
		guarded++
		// Said on the line, never folded away: a test that reaches the
		// target only through a fixture still guards it, and a reader
		// deciding which tests to run should know which kind of reach
		// it is (ADR-137, C-4).
		note := ""
		if !direct {
			note = "  — only through a pytest fixture (ADR-137)"
		}
		b.WriteString(fmt.Sprintf("  %s  [%s:%d]%s\n", tc.ID, tc.File, tc.Line, note))
	}
	if blanket > 0 {
		names := make([]string, 0, len(blanketFixtures))
		for fixture := range blanketFixtures {
			names = append(names, fixture)
		}
		sort.Strings(names)
		lead := "and "
		if guarded == 0 {
			lead = ""
			b.WriteString(fmt.Sprintf("no test reaches %s by a call or a fixture it names.\n", target))
		}
		b.WriteString(fmt.Sprintf(
			"%s%d test(s) reach it only through an autouse fixture — %s — which pytest runs before every test in its scope; "+
				"said once, not listed (ADR-139). It is reach, and it is not a test written for this code.\n",
			lead, blanket, strings.Join(names, ", ")))
	}
	if guarded == 0 && blanket == 0 {
		b.WriteString(fmt.Sprintf("no tests statically reach %s — changes there are unguarded\n", target))
		for _, m := range valueOnly(g, modules) {
			b.WriteString(fmt.Sprintf("  %s declares no function and no call targets it; reach follows calls only, so no test can be seen guarding it (C-156)\n", m))
		}
	}
	return b.String(), nil
}

// callableKinds are the symbol kinds a `calls` edge can target; the
// pipeline's testmap.CALLABLE_KINDS is the same set.
var callableKinds = map[string]bool{"function": true, "method": true, "class": true, "type": true, "macro": true}

// valueOnly returns, sorted, the modules among want that no `calls` edge
// could reach: no symbol of a callable kind and no recorded call into any
// symbol they declare (C-156). The pipeline's value_only_modules is the
// same rule; a const a call targets (a TS arrow) is callable.
func valueOnly(g *graphDoc, want map[string]bool) []string {
	reachable := map[string]bool{}
	moduleOf := map[string]string{}
	for _, sym := range g.Symbols {
		moduleOf[sym.ID] = sym.Module
		if callableKinds[sym.Kind] {
			reachable[sym.Module] = true
		}
	}
	for _, e := range g.SymbolEdges {
		if m, ok := moduleOf[e.To]; ok && e.Type == "calls" {
			reachable[m] = true
		}
	}
	var out []string
	for m := range want {
		if !reachable[m] {
			out = append(out, m)
		}
	}
	sort.Strings(out)
	return out
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
	{"expr-callee", "the callee is itself an expression — a subscript (handlers[k]()), a call's result (f()()), a parenthesised value — so there is no name for either lane to resolve (C-63); the site is counted and nothing can draw it: trace the value's origin yourself"},
	{"union-member", "a member call on a union-typed receiver whose members do not share one declaration of that member (n: A | B, both overriding); the checker and the index would name the first member's, which is one possible dispatch, so lane A abstained and lane B's pick was vetoed (ADR-104, C-97) — read the union's members to see what can run"},
	{"path-call", "a ::-qualified call the index left dark"},
	{"overload-set", "a Java name with more than one declaration fitting the call; lane A abstained rather than pick an overload (ADR-096) — lane B decides, or nobody has"},
	{"inherited-member", "a bare Java call in a type with supertypes and no fitting declaration of its own — the callee is inherited, which only lane B's hierarchy can name (ADR-096)"},
	{"build-tag-set", "a Go name declared more than once in its package under build constraints the caller's configuration does not single out; lane A abstained rather than pick a file (ADR-098, C-71) — the semantic index answers for one configuration only"},
	{"unclassified", "no observation applies — genuinely unknown; read this code yourself"},
	{"qualifier-mismatch", "a C++ call written through one specialisation (X<A>::f) that the index resolved to a different explicit specialisation's member (X<B>::f); the source text contradicts the index, so no edge is drawn (ADR-125, C-153) — read the call's qualifier to see the target"},
	{"arity-mismatch", "a C++ call written with more arguments than the declaration the index resolved it to can take — scip-clang's one answer at a call in a template can be the wrong overload (C-153), so no edge is drawn (ADR-130)"},
	// Last, as in tail.py's ALL_CLASSES: not an unresolved site but a
	// resolved one lane A keeps no symbol for (an interface method, a
	// closure, a nested function below C-9's floor) — the call graph's
	// known hole, per file (C-58). Missing from this table until
	// 2026-09-03 (C-77): the proxy printed the by-design rollup without it.
	{"below-floor", "resolved by the semantic lane to a declaration below the symbol floor — an interface method, a closure, a nested function — so no edge is drawn (C-58); the callee is known to the index and not to the graph"},
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
// sites under a scope. hcl has no call sites and maps to nothing. This
// table and langByExt below both mirror the pipeline's
// tail._LANG_BY_EXT and are held to it by a drift test
// (pipeline/tests/test_tail.py) — a new language must widen both here
// too, or it goes missing from this tool rather than failing loudly.
var artifactLangBucket = map[string]string{
	"python": "python", "typescript": "ts/js", "javascript": "ts/js",
	"go": "go", "rust": "rust", "java": "java", "c": "c", "cpp": "cpp",
}

// langByExt buckets a file by name alone. `.h` is the one extension two
// languages share: it is C here, and a row whose provider claimed it for
// C++ overrides this table (coverageRow.language, ADR-113 §1).
var langByExt = map[string]string{
	".py": "python", ".ts": "ts/js", ".tsx": "ts/js", ".mts": "ts/js",
	".cts": "ts/js", ".js": "ts/js", ".jsx": "ts/js", ".mjs": "ts/js",
	".cjs": "ts/js", ".go": "go", ".rs": "rust", ".java": "java",
	".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
	".hpp": "cpp", ".hh": "cpp", ".hxx": "cpp",
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
	g, _, err := s.loadGraph()
	if err != nil {
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
	b.WriteString(s.header(g.SHA, g.Dirty, g.BuiltBy))
	fmt.Fprintf(&b, "what Hobbes cannot see under %s — the work to verify yourself:\n\n", scope)
	b.WriteString("never in any count below, because it is not detected at all: dynamic\n" +
		"dispatch and calls through values (C-1), test reach through the value a\n" +
		"pytest fixture returns unless the fixture constructs it (ADR-145), or\n" +
		"through a fixture its lookup by name cannot\n" +
		"place — a plugin's or a base class's (C-4), computed\n" +
		"route paths (C-5). Every percentage here is a floor over DETECTED call\n" +
		"sites, not over the repo.\n")
	// Languages with detected call sites under the scope, by tail bucket
	// — the scoped verification line names only these (whole-repo scope
	// names every language the artifact lists, call sites or not).
	inScope := map[string]bool{}
	for _, row := range rows {
		if lang, ok := row.language(); ok {
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
		lang, ok := row.language()
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

	writeDirectoryRollup(&b, rows)

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

// dirLangKey is a rollupDirectories key: a depth-2 directory bucket
// paired with the language whose detected call sites it aggregates.
type dirLangKey struct {
	dir, lang string
}

// dirLangAgg is one rollupDirectories aggregate — the same shape as
// ListBlindSpots' own per-language agg, kept apart by directory too.
type dirLangAgg struct {
	sites, unresolved int
	tail              map[string]int
}

// directoryOf is the pipeline's tail.directory_of(file, depth=2): the
// first two segments of file's containing directory, slash-joined, or
// "." for a root-level file.
func directoryOf(file string) string {
	dir := path.Dir(file)
	if dir == "." {
		return "."
	}
	parts := strings.Split(dir, "/")
	if len(parts) > 2 {
		parts = parts[:2]
	}
	return strings.Join(parts, "/")
}

// rollupDirectories ports the pipeline's tail.rollup_directories: the
// per-(directory, language) tail totals over resolution_coverage rows,
// keyed apart by language for the same reason ListBlindSpots' own
// per-language rollup is — a capture statement's denominator is one
// language's detected call sites. The two functions must stay in step;
// a change to one without the other lets the ingest summary and this
// tool disagree over the same rows.
func rollupDirectories(rows []coverageRow) map[dirLangKey]*dirLangAgg {
	dirs := map[dirLangKey]*dirLangAgg{}
	for _, row := range rows {
		lang, ok := row.language()
		if !ok {
			continue
		}
		key := dirLangKey{dir: directoryOf(row.File), lang: lang}
		a := dirs[key]
		if a == nil {
			a = &dirLangAgg{tail: map[string]int{}}
			dirs[key] = a
		}
		a.sites += row.Sites
		a.unresolved += row.Unresolved
		for class, n := range row.Tail {
			a.tail[class] += n
		}
	}
	return dirs
}

// cannotResolve is a tail's classes minus notModelled's — the group
// rollupDirectories and the per-language rollup both rank on, since a
// directory full of by-design absences is accounted for, not missing.
func cannotResolve(tail map[string]int) map[string]int {
	out := map[string]int{}
	for class, n := range tail {
		if !notModelled[class] {
			out[class] = n
		}
	}
	return out
}

// dirRow is one ranked rollupDirectories entry, carrying the cannot-
// resolve group and its sum so writeDirectoryRollup sorts and prints
// without recomputing either.
type dirRow struct {
	key    dirLangKey
	agg    *dirLangAgg
	cannot map[string]int
	sum    int
}

// writeDirectoryRollup ports cli.py's _print_directory_view onto the
// same rollupDirectories rows: the per-language capture statement, one
// directory at a time, worst first. A directory whose tail is entirely
// by design is summarised, not listed — the view exists to point at
// what is missing, not to restate what already resolved.
func writeDirectoryRollup(b *strings.Builder, rows []coverageRow) {
	dirs := rollupDirectories(rows)
	var ranked []dirRow
	for key, a := range dirs {
		cannot := cannotResolve(a.tail)
		if len(cannot) == 0 {
			continue
		}
		sum := 0
		for _, n := range cannot {
			sum += n
		}
		ranked = append(ranked, dirRow{key: key, agg: a, cannot: cannot, sum: sum})
	}
	if len(ranked) == 0 {
		return
	}
	sort.Slice(ranked, func(i, j int) bool {
		if ranked[i].sum != ranked[j].sum {
			return ranked[i].sum > ranked[j].sum
		}
		if ranked[i].key.dir != ranked[j].key.dir {
			return ranked[i].key.dir < ranked[j].key.dir
		}
		return ranked[i].key.lang < ranked[j].key.lang
	})
	shown := len(ranked)
	if shown > 10 {
		shown = 10
	}
	fmt.Fprintf(b, "\nby directory (depth 2, worst %d of %d with unresolvable sites; %d without):\n",
		shown, len(ranked), len(dirs)-len(ranked))
	for _, r := range ranked[:shown] {
		accounted := float64(r.agg.sites-r.agg.unresolved) / float64(r.agg.sites) * 100
		classes := make([]string, 0, len(r.cannot))
		for c := range r.cannot {
			classes = append(classes, c)
		}
		sort.Strings(classes)
		named := make([]string, len(classes))
		for i, c := range classes {
			named[i] = fmt.Sprintf("%s %d", c, r.cannot[c])
		}
		byDesign := r.agg.unresolved - r.sum
		fmt.Fprintf(b, "  %s [%s]: %.1f%% of %d sites", r.key.dir, r.key.lang, accounted, r.agg.sites)
		if byDesign != 0 {
			fmt.Fprintf(b, ", %d by design", byDesign)
		}
		fmt.Fprintf(b, " — cannot resolve %d (%s)\n", r.sum, strings.Join(named, ", "))
	}
	if rest := ranked[shown:]; len(rest) > 0 {
		held := 0
		for _, r := range rest {
			held += r.sum
		}
		fmt.Fprintf(b, "  … and %d more directories (%d unresolvable) — per-file rows in graph.json resolution_coverage\n",
			len(rest), held)
	}
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
