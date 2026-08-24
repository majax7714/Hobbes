package web

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"gopkg.in/yaml.v3"
)

// --- helpers ----------------------------------------------------------------

func (f *fixture) send(t *testing.T, method, target, body string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(method, target, strings.NewReader(body))
	req.Host = "127.0.0.1:7777"
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	f.srv.Handler().ServeHTTP(rec, req)
	return rec
}

const starterPolicy = `version: 1
scope: repo
default: escalate

rules:
  - pattern: "pytest*"
    decision: allow
`

func writePolicy(t *testing.T, repo, body string) {
	t.Helper()
	writeFile(t, filepath.Join(repo, policyPath), body)
}

// writeInferred drops an inferred-invariants artifact into derived/.
func writeInferred(t *testing.T, repo string, records []map[string]any) {
	t.Helper()
	doc := map[string]any{
		"schema_version": 1,
		"kind":           "inferred-invariants",
		"sha":            "abc",
		"dirty":          false,
		"invariants":     records,
	}
	data, err := yaml.Marshal(doc)
	if err != nil {
		t.Fatal(err)
	}
	writeFile(t, filepath.Join(repo, inferredPath), string(data))
}

func inferredRec(id, statement, scope string) map[string]any {
	return map[string]any{
		"id": id, "statement": statement, "scope": scope, "status": "inferred",
		"evidence":   []map[string]any{{"path": "src/a.py", "line": 1}},
		"guarded_by": []string{},
	}
}

// --- content key: the cross-language contract -------------------------------

func TestContentKeyMatchesThePythonVectors(t *testing.T) {
	// The ledger is written here and read by `hobbes up`. A disagreement
	// about this hash would silently lose every decision rather than
	// fail, so both sides assert the same fixture.
	data, err := os.ReadFile("../../../pipeline/tests/fixtures/decision-keys.json")
	if err != nil {
		t.Skipf("conformance vectors unavailable: %v", err)
	}
	var doc struct {
		Vectors []struct {
			Why       string `json:"why"`
			Statement string `json:"statement"`
			Scope     string `json:"scope"`
			Key       string `json:"key"`
		} `json:"vectors"`
	}
	if err := json.Unmarshal(data, &doc); err != nil {
		t.Fatal(err)
	}
	if len(doc.Vectors) == 0 {
		t.Fatal("no vectors to check against")
	}
	for _, v := range doc.Vectors {
		if got := contentKey(v.Statement, v.Scope); got != v.Key {
			t.Errorf("contentKey(%q, %q) = %s, python says %s (%s)",
				v.Statement, v.Scope, got, v.Key, v.Why)
		}
	}
}

func TestContentKeyIgnoresTheID(t *testing.T) {
	// INF-n is positional, so it says nothing about what was decided.
	a := contentKey("only core mints tokens", "src")
	b := contentKey("only core   mints\ntokens", "src")
	if a != b {
		t.Error("reflowed whitespace must be the same decision")
	}
	if a == contentKey("only core mints tokens", ".") {
		t.Error("scope is part of identity")
	}
}

// --- the pending queue ------------------------------------------------------

func TestDecisionsQueueStartsBlockedOnIntent(t *testing.T) {
	f := newFixture(t)
	body := f.getJSON(t, "/api/decisions")
	if body["ready"] != false || body["intent_confirmed"] != false {
		t.Fatalf("a fresh repo must not read as ready: %v", body)
	}
	blockers, _ := body["blockers"].([]any)
	if len(blockers) != 1 || !strings.Contains(blockers[0].(string), "intent") {
		t.Errorf("blockers = %v, want the intent one", blockers)
	}
}

func TestInferredInvariantsArrivePending(t *testing.T) {
	f := newFixture(t)
	writeInferred(t, f.repo, []map[string]any{
		inferredRec("INF-1", "only core mints tokens", "src"),
		inferredRec("INF-2", "tfstate is never read", "."),
	})
	body := f.getJSON(t, "/api/decisions")
	queue, _ := body["pending_invariants"].([]any)
	if len(queue) != 2 {
		t.Fatalf("pending = %d, want 2", len(queue))
	}
	first := queue[0].(map[string]any)
	if !strings.HasPrefix(first["key"].(string), "sha256:") {
		t.Errorf("pending item needs a content key: %v", first)
	}
	// Evidence travels with it, or the reviewer is judging blind.
	if ev, _ := first["evidence"].([]any); len(ev) != 1 {
		t.Errorf("evidence missing: %v", first)
	}
}

func TestApprovingWritesARealRecordAndClearsTheQueue(t *testing.T) {
	f := newFixture(t)
	writePolicy(t, f.repo, starterPolicy)
	writeInferred(t, f.repo, []map[string]any{
		inferredRec("INF-1", "only core mints tokens", "src"),
	})
	key := contentKey("only core mints tokens", "src")

	res := f.send(t, http.MethodPost, "/api/decisions/"+key, `{"verdict":"approved"}`)
	if res.Code != http.StatusOK {
		t.Fatalf("approve = %d (%s)", res.Code, res.Body)
	}

	// ADR-019's rationale survives ADR-026: promotion still writes a file.
	entries, err := os.ReadDir(filepath.Join(f.repo, invariantsDir))
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 1 {
		t.Fatalf("want one record written, got %d", len(entries))
	}
	body, err := os.ReadFile(filepath.Join(f.repo, invariantsDir, entries[0].Name()))
	if err != nil {
		t.Fatal(err)
	}
	var record map[string]any
	if err := yaml.Unmarshal(body, &record); err != nil {
		t.Fatalf("the written record is not valid YAML: %v\n%s", err, body)
	}
	if record["status"] != "confirmed" {
		t.Errorf("status = %v, want confirmed", record["status"])
	}
	if record["scope"] != "src" {
		t.Errorf("scope = %v", record["scope"])
	}
	// Soft is the honest default for an inferred record: it carries no
	// structured rule (check: soft, no compile block — ADR-039).
	if record["check"] != "soft" {
		t.Errorf("check = %v, want soft", record["check"])
	}
	if _, has := record["compile"]; has {
		t.Errorf("a soft record must carry no compile block: %v", record["compile"])
	}
	if !strings.Contains(record["statement"].(string), "only core mints tokens") {
		t.Errorf("statement = %v", record["statement"])
	}

	if queue, _ := f.getJSON(t, "/api/decisions")["pending_invariants"].([]any); len(queue) != 0 {
		t.Errorf("a decided invariant must leave the queue: %v", queue)
	}
}

func TestDenyingRecordsNoFileButStillDecides(t *testing.T) {
	f := newFixture(t)
	writeInferred(t, f.repo, []map[string]any{inferredRec("INF-1", "a claim", "src")})
	key := contentKey("a claim", "src")

	if res := f.send(t, http.MethodPost, "/api/decisions/"+key, `{"verdict":"denied"}`); res.Code != 200 {
		t.Fatalf("deny = %d (%s)", res.Code, res.Body)
	}
	if _, err := os.Stat(filepath.Join(f.repo, invariantsDir)); err == nil {
		entries, _ := os.ReadDir(filepath.Join(f.repo, invariantsDir))
		if len(entries) != 0 {
			t.Errorf("a denial must not promote a record: %v", entries)
		}
	}
	// Re-inference must not re-ask; a gate that repeats itself gets
	// clicked through.
	writeInferred(t, f.repo, []map[string]any{inferredRec("INF-9", "a claim", "src")})
	if queue, _ := f.getJSON(t, "/api/decisions")["pending_invariants"].([]any); len(queue) != 0 {
		t.Errorf("a denied claim came back: %v", queue)
	}
}

func TestEditingWritesTheHumansWordsNotTheModels(t *testing.T) {
	f := newFixture(t)
	writeInferred(t, f.repo, []map[string]any{inferredRec("INF-1", "roughly right", "src")})
	key := contentKey("roughly right", "src")

	res := f.send(t, http.MethodPost, "/api/decisions/"+key, `{
		"verdict": "edited",
		"statement": "exactly right, and narrower",
		"scope": "src/app",
		"target": "import-linter",
		"rule_yaml": "kind: forbidden-import\nimporters: [\"*\"]\nimported: [ext:requests]"
	}`)
	if res.Code != http.StatusOK {
		t.Fatalf("edit = %d (%s)", res.Code, res.Body)
	}
	entries, _ := os.ReadDir(filepath.Join(f.repo, invariantsDir))
	if len(entries) != 1 {
		t.Fatalf("want one record, got %d", len(entries))
	}
	body, _ := os.ReadFile(filepath.Join(f.repo, invariantsDir, entries[0].Name()))
	var record map[string]any
	if err := yaml.Unmarshal(body, &record); err != nil {
		t.Fatalf("edited record is not valid YAML: %v\n%s", err, body)
	}
	if !strings.Contains(record["statement"].(string), "exactly right") {
		t.Errorf("statement = %v", record["statement"])
	}
	if record["scope"] != "src/app" {
		t.Errorf("scope = %v", record["scope"])
	}
	// ADR-039 shape: check: emit, rule at the top level, compile holding
	// only the target.
	if record["check"] != "emit" {
		t.Errorf("check = %v", record["check"])
	}
	compile, _ := record["compile"].(map[string]any)
	if compile["target"] != "import-linter" {
		t.Errorf("target = %v", compile["target"])
	}
	rule, _ := record["rule"].(map[string]any)
	if rule["kind"] != "forbidden-import" {
		t.Errorf("the typed rule did not survive: %v", record)
	}

	// The ledger keys on what was *proposed*, so the same proposal is
	// not asked again even though the record says something else.
	if queue, _ := f.getJSON(t, "/api/decisions")["pending_invariants"].([]any); len(queue) != 0 {
		t.Errorf("an edited proposal came back: %v", queue)
	}
}

func TestRewordedInvariantsComeBackButRenumberedOnesDoNot(t *testing.T) {
	f := newFixture(t)
	writeInferred(t, f.repo, []map[string]any{inferredRec("INF-1", "a claim", "src")})
	f.send(t, http.MethodPost, "/api/decisions/"+contentKey("a claim", "src"),
		`{"verdict":"approved"}`)

	// Same text, new id — the decision stands.
	writeInferred(t, f.repo, []map[string]any{inferredRec("INF-5", "a claim", "src")})
	if q, _ := f.getJSON(t, "/api/decisions")["pending_invariants"].([]any); len(q) != 0 {
		t.Errorf("a renumbered record was re-asked: %v", q)
	}
	// New text — must be asked, even under the old id.
	writeInferred(t, f.repo, []map[string]any{inferredRec("INF-1", "a claim, but broader", "src")})
	if q, _ := f.getJSON(t, "/api/decisions")["pending_invariants"].([]any); len(q) != 1 {
		t.Errorf("reworded text must re-escalate: %v", q)
	}
}

func TestVerdictRejectsUnknownVerbsAndKeys(t *testing.T) {
	f := newFixture(t)
	writeInferred(t, f.repo, []map[string]any{inferredRec("INF-1", "a claim", "src")})
	key := contentKey("a claim", "src")

	if res := f.send(t, http.MethodPost, "/api/decisions/"+key, `{"verdict":"maybe"}`); res.Code != http.StatusBadRequest {
		t.Errorf("unknown verdict = %d, want 400", res.Code)
	}
	if res := f.send(t, http.MethodPost, "/api/decisions/sha256:nope", `{"verdict":"approved"}`); res.Code != http.StatusNotFound {
		t.Errorf("unknown key = %d, want 404", res.Code)
	}
	if res := f.send(t, http.MethodPost, "/api/decisions/"+key, `not json`); res.Code != http.StatusBadRequest {
		t.Errorf("bad body = %d, want 400", res.Code)
	}
}

func TestRecordIDsDoNotCollide(t *testing.T) {
	f := newFixture(t)
	writeInferred(t, f.repo, []map[string]any{
		inferredRec("INF-1", "first claim", "src"),
		inferredRec("INF-2", "second claim", "lib"),
	})
	f.send(t, http.MethodPost, "/api/decisions/"+contentKey("first claim", "src"), `{"verdict":"approved"}`)
	f.send(t, http.MethodPost, "/api/decisions/"+contentKey("second claim", "lib"), `{"verdict":"approved"}`)

	entries, _ := os.ReadDir(filepath.Join(f.repo, invariantsDir))
	ids := map[string]bool{}
	for _, e := range entries {
		var doc struct {
			ID string `yaml:"id"`
		}
		data, _ := os.ReadFile(filepath.Join(f.repo, invariantsDir, e.Name()))
		_ = yaml.Unmarshal(data, &doc)
		if ids[doc.ID] {
			t.Fatalf("duplicate record id %s", doc.ID)
		}
		ids[doc.ID] = true
	}
	if len(ids) != 2 {
		t.Errorf("ids = %v, want two distinct", ids)
	}
}

// --- intent -----------------------------------------------------------------

func TestIntentServesThePolicyAndItsReviewState(t *testing.T) {
	f := newFixture(t)
	writePolicy(t, f.repo, starterPolicy)
	body := f.getJSON(t, "/api/intent")
	if body["path"] != policyPath {
		t.Errorf("path = %v", body["path"])
	}
	if !strings.Contains(body["text"].(string), "default: escalate") {
		t.Errorf("text did not come through: %v", body["text"])
	}
	if body["confirmed"] != false {
		t.Error("a policy nobody confirmed must not read as confirmed")
	}
}

func TestIntentIsAbsentBeforeInit(t *testing.T) {
	f := newFixture(t)
	rec := f.get(t, "/api/intent")
	if rec.Code != http.StatusNotFound {
		t.Fatalf("no policy = %d, want 404", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), "hobbes init") {
		t.Errorf("the 404 should name the fix: %s", rec.Body)
	}
}

func TestWritingIntentPersistsAndCanConfirm(t *testing.T) {
	f := newFixture(t)
	writePolicy(t, f.repo, starterPolicy)
	edited := strings.Replace(starterPolicy, `"pytest*"`, `"go test*"`, 1)

	res := f.send(t, http.MethodPut, "/api/intent",
		mustJSON(t, map[string]any{"text": edited, "confirm": true}))
	if res.Code != http.StatusOK {
		t.Fatalf("put = %d (%s)", res.Code, res.Body)
	}
	onDisk, _ := os.ReadFile(filepath.Join(f.repo, policyPath))
	if !strings.Contains(string(onDisk), "go test*") {
		t.Errorf("the edit did not land: %s", onDisk)
	}
	body := f.getJSON(t, "/api/intent")
	if body["confirmed"] != true || body["confirmed_at"] == "" {
		t.Errorf("confirmation not recorded: %v", body)
	}
	// The gate should now be clear of its intent blocker.
	decisions := f.getJSON(t, "/api/decisions")
	if decisions["intent_confirmed"] != true || decisions["ready"] != true {
		t.Errorf("decisions = %v, want ready", decisions)
	}
}

func TestConfirmingWithoutEditingIsAllowed(t *testing.T) {
	// Reading the starter policy and accepting it is a real decision.
	f := newFixture(t)
	writePolicy(t, f.repo, starterPolicy)
	res := f.send(t, http.MethodPut, "/api/intent", `{"confirm":true}`)
	if res.Code != http.StatusOK {
		t.Fatalf("confirm = %d (%s)", res.Code, res.Body)
	}
	if f.getJSON(t, "/api/intent")["confirmed"] != true {
		t.Error("confirming an unedited policy should count")
	}
}

func TestAHandEditAfterConfirmationIsVisible(t *testing.T) {
	f := newFixture(t)
	writePolicy(t, f.repo, starterPolicy)
	gitIn(t, f.repo, "add", "-A")
	gitIn(t, f.repo, "commit", "-qm", "policy")
	f.send(t, http.MethodPut, "/api/intent", `{"confirm":true}`)

	// Someone edits repo.policy outside the UI.
	writePolicy(t, f.repo, strings.Replace(starterPolicy, "escalate", "allow", 1))
	body := f.getJSON(t, "/api/intent")
	if body["changed_since_confirm"] != true {
		t.Errorf("an out-of-band edit must be visible: %v", body)
	}
}

func TestAMalformedPolicyIsRefusedNotWritten(t *testing.T) {
	f := newFixture(t)
	writePolicy(t, f.repo, starterPolicy)
	for _, bad := range []string{
		"version: 1\nscope: repo\ndefault: sure\n",
		"version: 1\ndefault: escalate\n",
		"scope: repo\ndefault: escalate\n",
		"version: 1\nscope: repo\ndefault: escalate\nrules:\n  - pattern: \"\"\n    decision: allow\n",
		"version: 1\nscope: repo\ndefault: escalate\nrules:\n  - pattern: \"x\"\n    decision: perhaps\n",
		": not yaml at all\n  - [",
	} {
		res := f.send(t, http.MethodPut, "/api/intent", mustJSON(t, map[string]any{"text": bad}))
		if res.Code != http.StatusBadRequest {
			t.Errorf("policy %q = %d, want 400", bad, res.Code)
		}
	}
	onDisk, _ := os.ReadFile(filepath.Join(f.repo, policyPath))
	if string(onDisk) != starterPolicy {
		t.Error("a refused policy must not have been written")
	}
}

// --- the ledger -------------------------------------------------------------

func TestLedgerIsReadableYAMLOutsideDerived(t *testing.T) {
	f := newFixture(t)
	writeInferred(t, f.repo, []map[string]any{inferredRec("INF-1", "a claim", "src")})
	f.send(t, http.MethodPost, "/api/decisions/"+contentKey("a claim", "src"), `{"verdict":"denied"}`)

	path := filepath.Join(f.repo, ledgerPath)
	if strings.Contains(path, "derived") {
		t.Fatal("human judgement must not live where a regeneration wipes it")
	}
	body, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasPrefix(string(body), "#") {
		t.Error("the ledger should explain itself to whoever opens it")
	}
	var doc map[string]any
	if err := yaml.Unmarshal(body, &doc); err != nil {
		t.Fatalf("ledger is not valid YAML: %v", err)
	}
	if !strings.Contains(string(body), "a claim") {
		t.Error("the ledger should record what was decided, not just its hash")
	}
}

func TestAMangledLedgerRowReAsksRatherThanApproving(t *testing.T) {
	f := newFixture(t)
	writeInferred(t, f.repo, []map[string]any{inferredRec("INF-1", "a claim", "src")})
	key := contentKey("a claim", "src")
	writeFile(t, filepath.Join(f.repo, ledgerPath),
		"schema_version: 1\nintent: {}\ninvariants:\n  - key: "+key+"\n    verdict: sure-why-not\n")

	queue, _ := f.getJSON(t, "/api/decisions")["pending_invariants"].([]any)
	if len(queue) != 1 {
		t.Errorf("an unreadable verdict must re-ask, not auto-approve: %v", queue)
	}
}

func mustJSON(t *testing.T, v any) string {
	t.Helper()
	data, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	return string(data)
}

// --- C-21: the queue shows the record a proposal restates -------------------

// The observed failure this guards against: narration re-proposed I-3's
// uncorrected wording, nothing showed the reviewer the corrected record
// sitting in .hobbes/invariants/, and the approval versioned a false
// claim as I-9 (2026-08-15). The texts below are the real pair.
const confirmedI3 = `id: I-3
statement: >-
  A session can commit but cannot publish. Every push, forced or not, is
  denied outright, and any command the repo policy does not match escalates
  to a human rather than running — the default is a question, never a yes.
scope: .
status: confirmed
check: soft
guarded_by: []
`

const rewordedI9 = "Any command not explicitly matched by a repo policy rule escalates " +
	"to a human by default — the default is a question, never a yes. Pushes " +
	"are the exception in the other direction: every push, forced or not, is " +
	"denied outright rather than escalated."

func writeConfirmed(t *testing.T, repo, name, body string) {
	t.Helper()
	writeFile(t, filepath.Join(repo, ".hobbes", "invariants", name), body)
}

func queueOf(t *testing.T, f *fixture) []pendingInvariant {
	t.Helper()
	rec := f.send(t, http.MethodGet, "/api/decisions", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("decisions: %d %s", rec.Code, rec.Body.String())
	}
	var payload struct {
		Pending []pendingInvariant `json:"pending_invariants"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &payload); err != nil {
		t.Fatal(err)
	}
	return payload.Pending
}

func TestARewordedProposalNamesItsConfirmedNeighbour(t *testing.T) {
	f := newFixture(t)
	writePolicy(t, f.repo, starterPolicy)
	writeConfirmed(t, f.repo, "I-3.yaml", confirmedI3)
	writeInferred(t, f.repo, []map[string]any{
		inferredRec("INF-1", rewordedI9, "."),
	})

	queue := queueOf(t, f)
	if len(queue) != 1 {
		t.Fatalf("want 1 pending, got %d", len(queue))
	}
	neighbour := queue[0].NearestConfirmed
	if neighbour == nil {
		t.Fatal("the reworded proposal must name its confirmed neighbour (C-21)")
	}
	if neighbour.ID != "I-3" {
		t.Fatalf("neighbour = %q, want I-3", neighbour.ID)
	}
	if neighbour.Score < neighbourThreshold {
		t.Fatalf("score %v below threshold %v", neighbour.Score, neighbourThreshold)
	}
	if !strings.Contains(neighbour.Statement, "cannot publish") {
		t.Fatalf("the neighbour must carry the confirmed prose, got %q", neighbour.Statement)
	}
}

func TestAnUnrelatedProposalOffersNoNeighbour(t *testing.T) {
	// A wrongly offered neighbour costs a glance; offering one for every
	// proposal would train the reviewer to ignore the banner.
	f := newFixture(t)
	writePolicy(t, f.repo, starterPolicy)
	writeConfirmed(t, f.repo, "I-3.yaml", confirmedI3)
	writeInferred(t, f.repo, []map[string]any{
		inferredRec("INF-1", "Module docs cite file and line for every claim they make.", "."),
	})

	queue := queueOf(t, f)
	if len(queue) != 1 {
		t.Fatalf("want 1 pending, got %d", len(queue))
	}
	if queue[0].NearestConfirmed != nil {
		t.Fatalf("unrelated proposal must not name a neighbour, got %+v", queue[0].NearestConfirmed)
	}
}

func TestNonConfirmedRecordsAreNeverOfferedAsNeighbours(t *testing.T) {
	f := newFixture(t)
	writePolicy(t, f.repo, starterPolicy)
	writeConfirmed(t, f.repo, "I-9.yaml", strings.Replace(confirmedI3, "status: confirmed", "status: retired", 1))
	writeInferred(t, f.repo, []map[string]any{
		inferredRec("INF-1", rewordedI9, "."),
	})

	queue := queueOf(t, f)
	if queue[0].NearestConfirmed != nil {
		t.Fatal("a retired record is history, not a neighbour")
	}
}
