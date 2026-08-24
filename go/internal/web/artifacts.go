package web

import (
	"encoding/json"
	"fmt"
	"io/fs"
	"net/http"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"slices"
	"sort"
	"strings"

	"gopkg.in/yaml.v3"

	"github.com/majax7714/Hobbes/go/internal/derived"
	"github.com/majax7714/Hobbes/go/internal/knowledge"
)

// ingestHint is what a repo missing its skeleton needs.
const ingestHint = "run `hobbes ingest` in the repo"

// narrateHint is what a repo missing its narrative pass needs.
const narrateHint = "run `hobbes narrate` in the repo"

// artifactHandler serves one extractor artifact byte-for-byte. The
// pipeline owns the schema (ADR-006); re-declaring it here would be a
// second place to update on every bump (ADR-022).
func (s *Server) artifactHandler(name string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		data, err := os.ReadFile(s.derivedPath(name))
		if os.IsNotExist(err) {
			writeError(w, http.StatusNotFound, "no "+name+" — this repo has not been ingested", ingestHint)
			return
		}
		if err != nil {
			writeError(w, http.StatusInternalServerError, err.Error(), "")
			return
		}
		// The bytes pass through untouched (ADR-022), but the version does
		// not pass unchecked: the SPA restates this schema in types.ts, so
		// serving one it cannot read would surface as a blank tab rather
		// than as the mismatch it is.
		if err := derived.Unmarshal(name, data, derived.V3Compatible, nil); err != nil {
			writeError(w, http.StatusConflict, err.Error(), ingestHint)
			return
		}
		writeRawJSON(w, data)
	}
}

// stamp is the {sha, dirty} header every artifact carries (ADR-006), plus
// the counts the overview reports. Only the fields the server itself
// needs are declared — the rest passes through /api/graph untouched.
type graphStamp struct {
	SchemaVersion int      `json:"schema_version"`
	SHA           string   `json:"sha"`
	Dirty         bool     `json:"dirty"`
	Languages     []string `json:"languages"`
	// How many repos each language's accuracy was measured on (C-31);
	// passed through so the language badges say it. Raw: the server
	// neither interprets nor invents it.
	VerificationBase map[string]json.RawMessage `json:"verification_base"`
	Nodes            []struct {
		Kind string `json:"kind"`
	} `json:"nodes"`
	ModuleEdges      []json.RawMessage `json:"module_edges"`
	Symbols          []json.RawMessage `json:"symbols"`
	SymbolEdges      []json.RawMessage `json:"symbol_edges"`
	ExtractionErrors []json.RawMessage `json:"extraction_errors"`
}

type testsStamp struct {
	SHA   string            `json:"sha"`
	Dirty bool              `json:"dirty"`
	Tests []json.RawMessage `json:"tests"`
}

type interfacesStamp struct {
	Routes         []json.RawMessage `json:"routes"`
	CLIEntryPoints []json.RawMessage `json:"cli_entry_points"`
}

// overview is what the app needs before any tab renders: which repo,
// which commit, and which artifacts exist. A repo with no ingest is a
// state the UI shows, not an error it hits (ADR-022).
type overview struct {
	Repo      string   `json:"repo"`
	Root      string   `json:"root"`
	Head      string   `json:"head"`
	Branch    string   `json:"branch"`
	Ingested  bool     `json:"ingested"`
	Narrated  bool     `json:"narrated"`
	SHA       string   `json:"sha,omitempty"`
	Dirty     bool     `json:"dirty"`
	Behind    bool     `json:"behind"`
	Schema    int      `json:"schema_version,omitempty"`
	Languages []string `json:"languages"`
	// Per language, the §3.8 verification row ({repos, note, ...}) the
	// artifact carries (C-31); empty for pre-ADR-053 artifacts.
	VerificationBase map[string]json.RawMessage `json:"verification_base,omitempty"`
	Counts           map[string]int             `json:"counts"`
	Hint             string                     `json:"hint,omitempty"`
}

func (s *Server) handleOverview(w http.ResponseWriter, r *http.Request) {
	out := overview{
		Repo:      filepath.Base(s.cfg.RepoRoot),
		Root:      s.cfg.RepoRoot,
		Head:      s.gitOutput("rev-parse", "HEAD"),
		Branch:    s.gitOutput("rev-parse", "--abbrev-ref", "HEAD"),
		Languages: []string{},
		Counts:    map[string]int{},
	}

	var g graphStamp
	if err := s.readDerived("graph.json", &g); err != nil {
		out.Hint = ingestHint
		writeJSON(w, http.StatusOK, out)
		return
	}
	out.Ingested = true
	out.SHA, out.Dirty, out.Schema = g.SHA, g.Dirty, g.SchemaVersion
	if g.Languages != nil {
		out.Languages = g.Languages
	}
	out.VerificationBase = g.VerificationBase
	// The artifact's own SHA vs the repo's: a skeleton generated before
	// the current commit is stale, and saying so is P1.
	out.Behind = out.Head != "" && g.SHA != "" && out.Head != g.SHA

	byKind := map[string]int{}
	for _, n := range g.Nodes {
		byKind[n.Kind]++
	}
	out.Counts["nodes"] = len(g.Nodes)
	out.Counts["modules"] = byKind["module"]
	out.Counts["module_edges"] = len(g.ModuleEdges)
	out.Counts["symbols"] = len(g.Symbols)
	out.Counts["symbol_edges"] = len(g.SymbolEdges)
	out.Counts["extraction_errors"] = len(g.ExtractionErrors)

	var t testsStamp
	if err := s.readDerived("tests.json", &t); err == nil {
		out.Counts["tests"] = len(t.Tests)
	}
	var i interfacesStamp
	if err := s.readDerived("interfaces.json", &i); err == nil {
		out.Counts["routes"] = len(i.Routes)
		out.Counts["cli_entry_points"] = len(i.CLIEntryPoints)
	}

	docs, _ := s.docIndex()
	out.Counts["docs"] = len(docs)
	out.Counts["docs_stale"] = 0
	for _, d := range docs {
		if d.Status != "fresh" {
			out.Counts["docs_stale"]++
		}
	}
	out.Narrated = len(docs) > 0
	if !out.Narrated {
		out.Hint = narrateHint
	}
	writeJSON(w, http.StatusOK, out)
}

func (s *Server) readDerived(name string, v any) error {
	data, err := os.ReadFile(s.derivedPath(name))
	if err != nil {
		return err
	}
	// Version-gated (ADR-028). Every caller here reads only fields present
	// since v3, and v4 is additive, so both are accepted — but a version
	// this build does not know is refused rather than half-decoded into a
	// struct whose zero values would read as real counts.
	return derived.Unmarshal(name, data, derived.V3Compatible, v)
}

// gitOutput runs a read-only git command in the repo, returning "" on any
// failure — a repo without git still serves every artifact-backed tab.
func (s *Server) gitOutput(args ...string) string {
	cmd := exec.Command("git", append([]string{"-C", s.cfg.RepoRoot}, args...)...)
	out, err := cmd.Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(out))
}

// --- narrative artifacts (ADR-019) -----------------------------------------

// docEntry is one row of the docs index: what it covers and whether its
// pins still point at the code they were written against.
type docEntry struct {
	Kind    string   `json:"kind"` // module-doc | test-doc | inferred-invariants
	ID      string   `json:"id"`
	Path    string   `json:"path,omitempty"`
	SHA     string   `json:"sha,omitempty"`
	Status  string   `json:"status"` // fresh | stale | broken
	Changed []string `json:"changed"`
	Error   string   `json:"error,omitempty"`
}

// docArtifact is the shared head of every narrative artifact — enough to
// index and badge one without knowing its body.
type docArtifact struct {
	Kind    string             `json:"kind"`
	ID      string             `json:"id"`
	Path    string             `json:"path"`
	SHA     string             `json:"sha"`
	Dirty   bool               `json:"dirty"`
	Sources []knowledge.Source `json:"sources"`
}

// docIndex badges every narrative artifact on disk. Blob hashing is
// batched into one git call (ADR-022) — the index is read on every load
// of the Docs tab.
func (s *Server) docIndex() ([]docEntry, error) {
	root := s.derivedPath("docs")
	type found struct {
		entry docEntry
		src   []knowledge.Source
	}
	var all []found

	for _, group := range []struct{ dir, kind string }{
		{"modules", "module-doc"},
		{"tests", "test-doc"},
	} {
		dir := filepath.Join(root, group.dir)
		_ = filepath.WalkDir(dir, func(p string, d fs.DirEntry, err error) error {
			if err != nil || d.IsDir() || !strings.HasSuffix(p, ".json") {
				return nil
			}
			rel, relErr := filepath.Rel(dir, p)
			if relErr != nil {
				return nil
			}
			id := strings.TrimSuffix(filepath.ToSlash(rel), ".json")
			entry := docEntry{Kind: group.kind, ID: id, Changed: []string{}}
			var a docArtifact
			data, readErr := os.ReadFile(p)
			if readErr != nil {
				entry.Status, entry.Error = "broken", readErr.Error()
				all = append(all, found{entry: entry})
				return nil
			}
			if jsonErr := json.Unmarshal(data, &a); jsonErr != nil {
				entry.Status, entry.Error = "broken", jsonErr.Error()
				all = append(all, found{entry: entry})
				return nil
			}
			if a.Kind != "" {
				entry.Kind = a.Kind
			}
			entry.Path, entry.SHA = a.Path, a.SHA
			all = append(all, found{entry: entry, src: a.Sources})
			return nil
		})
	}

	// The inferred invariants file is YAML (ADR-019) but stamps sources
	// the same way, so it badges like any other artifact.
	if inv, err := s.readInvariants(); err == nil {
		all = append(all, found{
			entry: docEntry{
				Kind: "inferred-invariants", ID: invariantsID,
				SHA: inv.SHA, Changed: []string{},
			},
			src: inv.Sources,
		})
	}

	groups := make(map[string][]knowledge.Source, len(all))
	for i, f := range all {
		groups[fmt.Sprint(i)] = f.src
	}
	changed := knowledge.ChangedSourcesMulti(s.cfg.RepoRoot, groups)

	entries := make([]docEntry, 0, len(all))
	for i, f := range all {
		e := f.entry
		if e.Status != "broken" {
			e.Changed = changed[fmt.Sprint(i)]
			if e.Changed == nil {
				e.Changed = []string{}
			}
			e.Status = "fresh"
			if len(e.Changed) > 0 {
				e.Status = "stale"
			}
		}
		entries = append(entries, e)
	}
	sort.Slice(entries, func(i, j int) bool {
		if entries[i].Kind != entries[j].Kind {
			return entries[i].Kind < entries[j].Kind
		}
		return entries[i].ID < entries[j].ID
	})
	return entries, nil
}

func (s *Server) handleDocsIndex(w http.ResponseWriter, r *http.Request) {
	entries, err := s.docIndex()
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"artifacts": entries})
}

// docID rejects anything that is not a narrative artifact id. TS/JS ids
// are repo-relative paths (ADR-021) so "/" is legal; traversal is not —
// the same guard the Python writer and the MCP reader apply.
func docID(id string) bool {
	return id != "" && !strings.HasPrefix(id, "/") && !strings.Contains(id, "\\") &&
		path.Clean(id) == id && !slices.Contains(strings.Split(id, "/"), "..")
}

// serveDoc returns one narrative artifact with its badge attached. The
// body is passed through as decoded JSON so the app sees the artifact
// exactly as ADR-019 defines it.
func (s *Server) serveDoc(w http.ResponseWriter, dir, id string) {
	if !docID(id) {
		writeError(w, http.StatusBadRequest, fmt.Sprintf("%q is not an artifact id", id), "")
		return
	}
	full := filepath.Join(s.derivedPath("docs", dir), filepath.FromSlash(id)+".json")
	data, err := os.ReadFile(full)
	if os.IsNotExist(err) {
		writeError(w, http.StatusNotFound, "no "+dir+" doc for "+id, narrateHint)
		return
	}
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "")
		return
	}
	var body map[string]any
	if err := json.Unmarshal(data, &body); err != nil {
		writeError(w, http.StatusInternalServerError, "artifact is not valid JSON: "+err.Error(), narrateHint)
		return
	}
	var a docArtifact
	_ = json.Unmarshal(data, &a)
	changed := knowledge.ChangedSources(s.cfg.RepoRoot, a.Sources)
	if changed == nil {
		changed = []string{}
	}
	status := "fresh"
	if len(changed) > 0 {
		status = "stale"
	}
	body["status"] = status
	body["changed"] = changed
	writeJSON(w, http.StatusOK, body)
}

func (s *Server) handleModuleDoc(w http.ResponseWriter, r *http.Request) {
	s.serveDoc(w, "modules", r.PathValue("id"))
}

func (s *Server) handleTestDoc(w http.ResponseWriter, r *http.Request) {
	s.serveDoc(w, "tests", r.PathValue("id"))
}

// behavior is one test's one-line summary of what it pins down (§4.2 q1),
// carrying the badge of the artifact it came from.
type behavior struct {
	Test string `json:"test"`
	Text string `json:"text"`
	Pins []struct {
		Path string `json:"path"`
		Line int    `json:"line"`
	} `json:"pins"`
	DocID  string `json:"doc_id"`
	Status string `json:"status"`
}

// handleBehaviors joins every test doc into one index keyed by test id.
// The Tests tab needs all of them at once to answer "what behavior does
// this test guard"; fetching each artifact separately would be one
// request per test file on every tab open.
func (s *Server) handleBehaviors(w http.ResponseWriter, r *http.Request) {
	dir := s.derivedPath("docs", "tests")
	entries, err := os.ReadDir(dir)
	if os.IsNotExist(err) {
		writeJSON(w, http.StatusOK, map[string]any{"behaviors": []behavior{}, "hint": narrateHint})
		return
	}
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "")
		return
	}

	type loaded struct {
		id        string
		sources   []knowledge.Source
		behaviors []behavior
	}
	var docs []loaded
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".json") {
			continue
		}
		data, readErr := os.ReadFile(filepath.Join(dir, e.Name()))
		if readErr != nil {
			continue
		}
		var doc struct {
			ID        string             `json:"id"`
			Sources   []knowledge.Source `json:"sources"`
			Behaviors []behavior         `json:"behaviors"`
		}
		if json.Unmarshal(data, &doc) != nil {
			continue
		}
		docs = append(docs, loaded{id: doc.ID, sources: doc.Sources, behaviors: doc.Behaviors})
	}

	groups := make(map[string][]knowledge.Source, len(docs))
	for _, d := range docs {
		groups[d.id] = d.sources
	}
	changed := knowledge.ChangedSourcesMulti(s.cfg.RepoRoot, groups)

	out := []behavior{}
	for _, d := range docs {
		status := "fresh"
		if len(changed[d.id]) > 0 {
			status = "stale"
		}
		for _, b := range d.behaviors {
			b.DocID, b.Status = d.id, status
			out = append(out, b)
		}
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Test < out[j].Test })
	writeJSON(w, http.StatusOK, map[string]any{"behaviors": out})
}

// invariantsID is the docs-index id of the inferred-invariants artifact,
// which has no module of its own.
const invariantsID = "invariants.inferred"

// inferredInvariants is the ADR-019 YAML artifact. Invariants stay
// yaml.Node-free by decoding into plain maps: the record shape is §10's,
// and the surface renders it, never edits it (confirmation is Max moving
// the record into .hobbes/invariants/).
type inferredInvariants struct {
	SchemaVersion int                `yaml:"schema_version" json:"schema_version"`
	Kind          string             `yaml:"kind" json:"kind"`
	SHA           string             `yaml:"sha" json:"sha"`
	Dirty         bool               `yaml:"dirty" json:"dirty"`
	Sources       []knowledge.Source `yaml:"sources" json:"sources"`
	Invariants    []struct {
		ID        string   `yaml:"id" json:"id"`
		Statement string   `yaml:"statement" json:"statement"`
		Scope     string   `yaml:"scope" json:"scope"`
		Status    string   `yaml:"status" json:"status"`
		GuardedBy []string `yaml:"guarded_by" json:"guarded_by,omitempty"`
		Evidence  []struct {
			Path string `yaml:"path" json:"path"`
			Line int    `yaml:"line" json:"line"`
		} `yaml:"evidence" json:"evidence"`
	} `yaml:"invariants" json:"invariants"`
}

func (s *Server) readInvariants() (*inferredInvariants, error) {
	data, err := os.ReadFile(s.derivedPath("docs", "invariants.inferred.yaml"))
	if err != nil {
		return nil, err
	}
	var inv inferredInvariants
	if err := yaml.Unmarshal(data, &inv); err != nil {
		return nil, err
	}
	// knowledge.Source carries json tags; yaml.v3 lowercases field names,
	// so blob_sha needs the explicit mapping done here.
	var raw struct {
		Sources []struct {
			Path    string `yaml:"path"`
			BlobSHA string `yaml:"blob_sha"`
		} `yaml:"sources"`
	}
	if err := yaml.Unmarshal(data, &raw); err == nil {
		inv.Sources = make([]knowledge.Source, 0, len(raw.Sources))
		for _, src := range raw.Sources {
			inv.Sources = append(inv.Sources, knowledge.Source{Path: src.Path, BlobSHA: src.BlobSHA})
		}
	}
	return &inv, nil
}

func (s *Server) handleInvariants(w http.ResponseWriter, r *http.Request) {
	inv, err := s.readInvariants()
	if os.IsNotExist(err) {
		writeError(w, http.StatusNotFound, "no inferred invariants", narrateHint)
		return
	}
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "")
		return
	}
	changed := knowledge.ChangedSources(s.cfg.RepoRoot, inv.Sources)
	if changed == nil {
		changed = []string{}
	}
	status := "fresh"
	if len(changed) > 0 {
		status = "stale"
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"id": invariantsID, "kind": "inferred-invariants",
		"sha": inv.SHA, "dirty": inv.Dirty,
		"invariants": inv.Invariants,
		"status":     status, "changed": changed,
	})
}
