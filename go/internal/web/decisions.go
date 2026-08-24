package web

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

// The two decision surfaces (ADR-026). Exactly two things need a human —
// intent (the repo policy) and invariants — and both are settled here.
// Everything else the surface does is a read.
//
// This file is the ledger's writer; `hobbes up` is its reader. The
// content-key spec below is therefore implemented twice, and pinned by
// shared vectors in pipeline/tests/fixtures/decision-keys.json: a
// mismatch would silently lose every decision instead of failing.

const (
	ledgerPath     = ".hobbes/decisions.yaml"
	policyPath     = ".hobbes/policies/repo.policy"
	invariantsDir  = ".hobbes/invariants"
	inferredPath   = ".hobbes/derived/docs/invariants.inferred.yaml"
	ledgerSchema   = 1
	verdictApprove = "approved"
	verdictDeny    = "denied"
	verdictEdit    = "edited"
)

// contentKey is the identity of one proposed invariant: a hash of its
// normalized statement and scope, never its id. Inferred ids are
// positional, so INF-3 names different text after the next narration and
// an id-keyed approval would silently bless it.
func contentKey(statement, scope string) string {
	normalized := strings.Join(strings.Fields(statement), " ") + "\n" + strings.TrimSpace(scope)
	sum := sha256.Sum256([]byte(normalized))
	return "sha256:" + hex.EncodeToString(sum[:])[:32]
}

type ledgerDecision struct {
	Key             string `yaml:"key" json:"key"`
	Verdict         string `yaml:"verdict" json:"verdict"`
	DecidedAt       string `yaml:"decided_at" json:"decided_at"`
	Record          string `yaml:"record,omitempty" json:"record,omitempty"`
	SourceStatement string `yaml:"source_statement" json:"source_statement"`
	SourceScope     string `yaml:"source_scope" json:"source_scope"`
}

type ledgerIntent struct {
	ConfirmedAt string `yaml:"confirmed_at" json:"confirmed_at"`
	PolicyBlob  string `yaml:"policy_blob" json:"policy_blob"`
}

type ledger struct {
	SchemaVersion int              `yaml:"schema_version" json:"schema_version"`
	Intent        ledgerIntent     `yaml:"intent" json:"intent"`
	Invariants    []ledgerDecision `yaml:"invariants" json:"invariants"`
}

func (l *ledger) byKey() map[string]ledgerDecision {
	out := make(map[string]ledgerDecision, len(l.Invariants))
	for _, d := range l.Invariants {
		// A row without a usable verdict is dropped rather than trusted:
		// an unreadable decision must re-ask, never auto-approve.
		if d.Key == "" {
			continue
		}
		switch d.Verdict {
		case verdictApprove, verdictDeny, verdictEdit:
			out[d.Key] = d
		}
	}
	return out
}

func (s *Server) readLedger() (*ledger, error) {
	l := &ledger{SchemaVersion: ledgerSchema}
	data, err := os.ReadFile(filepath.Join(s.cfg.RepoRoot, ledgerPath))
	if os.IsNotExist(err) {
		return l, nil
	}
	if err != nil {
		return nil, err
	}
	if err := yaml.Unmarshal(data, l); err != nil {
		return nil, fmt.Errorf("%s is not valid YAML: %w", ledgerPath, err)
	}
	return l, nil
}

const ledgerHeader = `# Decisions Max has made about this repo (ADR-026). Approvals,
# denials, and edits hold until changed here or in the UI; only
# invariants whose text is new get asked again.
`

func (s *Server) writeLedger(l *ledger) error {
	l.SchemaVersion = ledgerSchema
	sort.Slice(l.Invariants, func(i, j int) bool { return l.Invariants[i].Key < l.Invariants[j].Key })
	body, err := yaml.Marshal(l)
	if err != nil {
		return err
	}
	path := filepath.Join(s.cfg.RepoRoot, ledgerPath)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return atomicWrite(path, ledgerHeader+string(body))
}

// atomicWrite replaces a file in one step, so a torn write can never
// leave a half-parsed ledger or policy behind.
func atomicWrite(path, body string) error {
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, []byte(body), 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}

// --- the pending queue ------------------------------------------------------

type inferredRecord struct {
	ID        string   `yaml:"id" json:"id"`
	Statement string   `yaml:"statement" json:"statement"`
	Scope     string   `yaml:"scope" json:"scope"`
	Status    string   `yaml:"status" json:"status"`
	GuardedBy []string `yaml:"guarded_by" json:"guarded_by"`
	Evidence  []struct {
		Path string `yaml:"path" json:"path"`
		Line int    `yaml:"line" json:"line"`
	} `yaml:"evidence" json:"evidence"`
}

type pendingInvariant struct {
	Key string `json:"key"`
	inferredRecord
	// NearestConfirmed is the confirmed record this proposal most
	// resembles, when the resemblance is strong enough to matter
	// (C-21). Narration is told about the repo but not about
	// `.hobbes/invariants/`, so it re-proposes settled records in fresh
	// words — and a reword does not match the content key. On
	// 2026-08-15 that approved I-9 carrying a claim I-3 had been
	// corrected to remove: the reviewer could see the queue was noisy,
	// but not that *this* reword reversed a correction. Showing the
	// neighbour is the fix the C-21 entry named.
	NearestConfirmed *confirmedNeighbour `json:"nearest_confirmed,omitempty"`
}

// confirmedNeighbour is a confirmed record surfaced beside a proposal.
type confirmedNeighbour struct {
	ID        string  `json:"id"`
	Statement string  `json:"statement"`
	Score     float64 `json:"score"`
}

// confirmedStatements reads id/statement/scope from every confirmed
// record under .hobbes/invariants/. Deliberately minimal and local: the
// queue needs the prose to show, not the rule to check, and a file this
// cannot parse simply is not offered as a neighbour.
func (s *Server) confirmedStatements() []confirmedNeighbour {
	dir := filepath.Join(s.cfg.RepoRoot, ".hobbes", "invariants")
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil
	}
	var out []confirmedNeighbour
	for _, entry := range entries {
		if entry.IsDir() || filepath.Ext(entry.Name()) != ".yaml" {
			continue
		}
		data, readErr := os.ReadFile(filepath.Join(dir, entry.Name()))
		if readErr != nil {
			continue
		}
		var record struct {
			ID        string `yaml:"id"`
			Statement string `yaml:"statement"`
			Status    string `yaml:"status"`
		}
		if yaml.Unmarshal(data, &record) != nil || record.ID == "" {
			continue
		}
		if record.Status != "confirmed" {
			continue
		}
		record.Statement = strings.Join(strings.Fields(record.Statement), " ")
		out = append(out, confirmedNeighbour{ID: record.ID, Statement: record.Statement})
	}
	return out
}

// statementTokens normalises a statement for overlap comparison:
// lowercased words of three letters or more. Determinism is the point —
// no model judges similarity, the same pair scores the same forever.
var tokenPattern = regexp.MustCompile(`[a-z0-9]+`)

func statementTokens(statement string) map[string]bool {
	tokens := map[string]bool{}
	for _, token := range tokenPattern.FindAllString(strings.ToLower(statement), -1) {
		if len(token) >= 3 {
			tokens[token] = true
		}
	}
	return tokens
}

// neighbourThreshold is the Jaccard overlap below which a confirmed
// record is not offered as a neighbour. Tuned on the observed failure:
// I-9's inferred wording against the confirmed I-3 scores well above
// this; unrelated records score near zero. Low on purpose — a wrongly
// offered neighbour costs a glance, a missed one re-approves a
// corrected-away claim.
const neighbourThreshold = 0.2

// nearestConfirmed returns the best-overlapping confirmed record, or
// nil when nothing crosses the threshold.
func nearestConfirmed(statement string, confirmed []confirmedNeighbour) *confirmedNeighbour {
	proposal := statementTokens(statement)
	if len(proposal) == 0 {
		return nil
	}
	var best *confirmedNeighbour
	bestScore := 0.0
	for i := range confirmed {
		candidate := statementTokens(confirmed[i].Statement)
		if len(candidate) == 0 {
			continue
		}
		shared := 0
		for token := range proposal {
			if candidate[token] {
				shared++
			}
		}
		union := len(proposal) + len(candidate) - shared
		score := float64(shared) / float64(union)
		if score > bestScore {
			bestScore = score
			best = &confirmed[i]
		}
	}
	if best == nil || bestScore < neighbourThreshold {
		return nil
	}
	return &confirmedNeighbour{
		ID:        best.ID,
		Statement: best.Statement,
		Score:     float64(int(bestScore*100)) / 100,
	}
}

func (s *Server) inferred() ([]inferredRecord, error) {
	data, err := os.ReadFile(filepath.Join(s.cfg.RepoRoot, inferredPath))
	if os.IsNotExist(err) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var doc struct {
		Invariants []inferredRecord `yaml:"invariants"`
	}
	if err := yaml.Unmarshal(data, &doc); err != nil {
		return nil, fmt.Errorf("%s is not valid YAML: %w", inferredPath, err)
	}
	return doc.Invariants, nil
}

// pending lists inferred invariants with no recorded verdict, in file
// order. A record whose text changed since it was decided reappears —
// that is the point of hashing content rather than trusting the id.
func (s *Server) pending(l *ledger) ([]pendingInvariant, error) {
	records, err := s.inferred()
	if err != nil {
		return nil, err
	}
	decided := l.byKey()
	confirmed := s.confirmedStatements()
	out := []pendingInvariant{}
	for _, r := range records {
		key := contentKey(r.Statement, r.Scope)
		if _, done := decided[key]; done {
			continue
		}
		r.Statement = strings.Join(strings.Fields(r.Statement), " ")
		out = append(out, pendingInvariant{
			Key:              key,
			inferredRecord:   r,
			NearestConfirmed: nearestConfirmed(r.Statement, confirmed),
		})
	}
	return out, nil
}

func (s *Server) handleDecisions(w http.ResponseWriter, r *http.Request) {
	l, err := s.readLedger()
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "")
		return
	}
	queue, err := s.pending(l)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "")
		return
	}
	blockers := []string{}
	if l.Intent.ConfirmedAt == "" {
		blockers = append(blockers, "intent: the repo policy has not been confirmed")
	}
	if len(queue) > 0 {
		blockers = append(blockers,
			fmt.Sprintf("invariants: %d awaiting approve / deny / edit", len(queue)))
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"ready":               len(blockers) == 0,
		"intent_confirmed":    l.Intent.ConfirmedAt != "",
		"intent_confirmed_at": l.Intent.ConfirmedAt,
		"pending_invariants":  queue,
		"decided":             l.Invariants,
		"blockers":            blockers,
	})
}

// --- verdicts ---------------------------------------------------------------

type verdictRequest struct {
	Verdict string `json:"verdict"`
	// For an edit: the human's revised text. Empty fields keep the
	// inferred wording.
	Statement string `json:"statement"`
	Scope     string `json:"scope"`
	Target    string `json:"target"`
	// RuleYAML is the record's rule block for a structured target, as
	// typed (top-level since ADR-039). Left to the schema validator
	// rather than parsed here.
	RuleYAML string `json:"rule_yaml"`
}

func (s *Server) handleVerdict(w http.ResponseWriter, r *http.Request) {
	key := r.PathValue("key")
	var req verdictRequest
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<20)).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "body must be JSON: "+err.Error(), "")
		return
	}
	switch req.Verdict {
	case verdictApprove, verdictDeny, verdictEdit:
	default:
		writeError(w, http.StatusBadRequest,
			"verdict must be approved, denied, or edited", "")
		return
	}

	l, err := s.readLedger()
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "")
		return
	}
	queue, err := s.pending(l)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "")
		return
	}
	var subject *pendingInvariant
	for i := range queue {
		if queue[i].Key == key {
			subject = &queue[i]
			break
		}
	}
	if subject == nil {
		writeError(w, http.StatusNotFound,
			"no invariant awaiting a verdict under that key", "")
		return
	}

	decision := ledgerDecision{
		Key:             key,
		Verdict:         req.Verdict,
		DecidedAt:       time.Now().UTC().Format(time.RFC3339),
		SourceStatement: subject.Statement,
		SourceScope:     subject.Scope,
	}

	if req.Verdict != verdictDeny {
		statement := strings.TrimSpace(req.Statement)
		if statement == "" {
			statement = subject.Statement
		}
		scope := strings.TrimSpace(req.Scope)
		if scope == "" {
			scope = subject.Scope
		}
		target := strings.TrimSpace(req.Target)
		if target == "" {
			// Soft is the honest default: an inferred record carries no
			// structured rule, and ADR-024 makes soft the right home for
			// anything not mechanically checkable.
			target = "soft"
		}
		recordID, writeErr := s.writeInvariantRecord(
			statement, scope, target, req.RuleYAML, subject.GuardedBy)
		if writeErr != nil {
			writeError(w, http.StatusInternalServerError, writeErr.Error(), "")
			return
		}
		decision.Record = recordID
	}

	l.Invariants = append(l.Invariants, decision)
	if err := s.writeLedger(l); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"decision": decision})
}

var slugUnsafe = regexp.MustCompile(`[^a-z0-9]+`)

func slugify(statement string) string {
	words := strings.Fields(strings.ToLower(statement))
	if len(words) > 6 {
		words = words[:6]
	}
	slug := slugUnsafe.ReplaceAllString(strings.Join(words, "-"), "-")
	return strings.Trim(slug, "-")
}

// nextInvariantID is the lowest unused I-n in the versioned directory.
func (s *Server) nextInvariantID() string {
	used := map[int]bool{}
	entries, _ := os.ReadDir(filepath.Join(s.cfg.RepoRoot, invariantsDir))
	for _, e := range entries {
		if e.IsDir() || filepath.Ext(e.Name()) != ".yaml" {
			continue
		}
		var doc struct {
			ID string `yaml:"id"`
		}
		data, err := os.ReadFile(filepath.Join(s.cfg.RepoRoot, invariantsDir, e.Name()))
		if err != nil || yaml.Unmarshal(data, &doc) != nil {
			continue
		}
		if n, err := strconv.Atoi(strings.TrimPrefix(doc.ID, "I-")); err == nil {
			used[n] = true
		}
	}
	for n := 1; ; n++ {
		if !used[n] {
			return "I-" + strconv.Itoa(n)
		}
	}
}

// writeInvariantRecord promotes an approved invariant into the versioned
// directory. ADR-019 made promotion physical so it could not decay into
// a status flag; ADR-026 keeps the file, and changes only what triggers
// the write.
func (s *Server) writeInvariantRecord(
	statement, scope, target, ruleYAML string, guardedBy []string,
) (string, error) {
	id := s.nextInvariantID()
	var b strings.Builder
	fmt.Fprintf(&b, "# Promoted from the inferred set through the Hobbes surface\n")
	fmt.Fprintf(&b, "# on %s (ADR-026). Edit freely — this file is the record.\n",
		time.Now().UTC().Format("2006-01-02"))
	fmt.Fprintf(&b, "id: %s\n", id)
	fmt.Fprintf(&b, "statement: >-\n")
	for _, line := range wrapText(statement, 68) {
		fmt.Fprintf(&b, "  %s\n", line)
	}
	fmt.Fprintf(&b, "scope: %s\n", yamlScalar(scope))
	fmt.Fprintf(&b, "status: confirmed\n")
	// ADR-039 shape: check decides the rest. An approval with no
	// structured rule is check: soft; one with a rule and a CI target is
	// check: emit, rule at the top level, compile holding only the target.
	if target == "soft" || strings.TrimSpace(ruleYAML) == "" {
		fmt.Fprintf(&b, "check: soft\n")
	} else {
		fmt.Fprintf(&b, "check: emit\n")
		fmt.Fprintf(&b, "rule:\n")
		for _, line := range strings.Split(strings.TrimRight(ruleYAML, "\n"), "\n") {
			fmt.Fprintf(&b, "  %s\n", line)
		}
		fmt.Fprintf(&b, "compile:\n  target: %s\n", target)
	}
	if len(guardedBy) == 0 {
		fmt.Fprintf(&b, "guarded_by: []\n")
	} else {
		fmt.Fprintf(&b, "guarded_by:\n")
		for _, g := range guardedBy {
			fmt.Fprintf(&b, "  - %s\n", g)
		}
	}

	dir := filepath.Join(s.cfg.RepoRoot, invariantsDir)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", err
	}
	name := id
	if slug := slugify(statement); slug != "" {
		name = id + "-" + slug
	}
	return id, atomicWrite(filepath.Join(dir, name+".yaml"), b.String())
}

// yamlScalar quotes a scalar when YAML would otherwise misread it.
func yamlScalar(value string) string {
	if value == "" || strings.ContainsAny(value, ":#{}[],&*?|-<>=!%@`\"' ") {
		return strconv.Quote(value)
	}
	return value
}

// wrapText breaks a statement into lines for a readable YAML block.
func wrapText(text string, width int) []string {
	words := strings.Fields(text)
	if len(words) == 0 {
		return []string{""}
	}
	lines := []string{}
	current := words[0]
	for _, word := range words[1:] {
		if len(current)+1+len(word) > width {
			lines = append(lines, current)
			current = word
			continue
		}
		current += " " + word
	}
	return append(lines, current)
}

// --- intent (the repo policy) -----------------------------------------------

func (s *Server) handleIntent(w http.ResponseWriter, r *http.Request) {
	l, err := s.readLedger()
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "")
		return
	}
	full := filepath.Join(s.cfg.RepoRoot, policyPath)
	text, readErr := os.ReadFile(full)
	if os.IsNotExist(readErr) {
		writeError(w, http.StatusNotFound, "no repo policy", "run `hobbes init` in the repo")
		return
	}
	if readErr != nil {
		writeError(w, http.StatusInternalServerError, readErr.Error(), "")
		return
	}
	blob := s.gitOutput("hash-object", policyPath)
	writeJSON(w, http.StatusOK, map[string]any{
		"path":         policyPath,
		"text":         string(text),
		"blob":         blob,
		"confirmed":    l.Intent.ConfirmedAt != "",
		"confirmed_at": l.Intent.ConfirmedAt,
		// True when the file moved since it was confirmed — a hand edit
		// outside the UI is visible rather than silently blessed.
		"changed_since_confirm": l.Intent.ConfirmedAt != "" &&
			l.Intent.PolicyBlob != "" && blob != "" && blob != l.Intent.PolicyBlob,
	})
}

type intentRequest struct {
	Text string `json:"text"`
	// Confirm marks the policy reviewed in the same call, so saving an
	// edit you just read does not need a second click.
	Confirm bool `json:"confirm"`
}

func (s *Server) handleWriteIntent(w http.ResponseWriter, r *http.Request) {
	var req intentRequest
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<20)).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "body must be JSON: "+err.Error(), "")
		return
	}
	if strings.TrimSpace(req.Text) != "" {
		if err := checkPolicyShape(req.Text); err != nil {
			writeError(w, http.StatusBadRequest, err.Error(), "")
			return
		}
		full := filepath.Join(s.cfg.RepoRoot, policyPath)
		if err := os.MkdirAll(filepath.Dir(full), 0o755); err != nil {
			writeError(w, http.StatusInternalServerError, err.Error(), "")
			return
		}
		if err := atomicWrite(full, req.Text); err != nil {
			writeError(w, http.StatusInternalServerError, err.Error(), "")
			return
		}
	}
	if req.Confirm {
		l, err := s.readLedger()
		if err != nil {
			writeError(w, http.StatusInternalServerError, err.Error(), "")
			return
		}
		l.Intent.ConfirmedAt = time.Now().UTC().Format(time.RFC3339)
		l.Intent.PolicyBlob = s.gitOutput("hash-object", policyPath)
		if err := s.writeLedger(l); err != nil {
			writeError(w, http.StatusInternalServerError, err.Error(), "")
			return
		}
	}
	s.handleIntent(w, r)
}

// checkPolicyShape refuses a policy the engine could not load. It is a
// shape check, not a semantic one: `hobbes policy resolve` remains the
// way to find out what a rule actually decides.
func checkPolicyShape(text string) error {
	var doc struct {
		Version int    `yaml:"version"`
		Scope   string `yaml:"scope"`
		Default string `yaml:"default"`
		Rules   []struct {
			Pattern  string `yaml:"pattern"`
			Decision string `yaml:"decision"`
		} `yaml:"rules"`
	}
	if err := yaml.Unmarshal([]byte(text), &doc); err != nil {
		return fmt.Errorf("not valid YAML: %v", err)
	}
	if doc.Version == 0 {
		return fmt.Errorf("policy needs a version")
	}
	if doc.Scope == "" {
		return fmt.Errorf("policy needs a scope")
	}
	decisions := map[string]bool{"allow": true, "deny": true, "escalate": true}
	if !decisions[doc.Default] {
		return fmt.Errorf("default must be allow, deny, or escalate")
	}
	for i, rule := range doc.Rules {
		if strings.TrimSpace(rule.Pattern) == "" {
			return fmt.Errorf("rule %d has no pattern", i+1)
		}
		if !decisions[rule.Decision] {
			return fmt.Errorf("rule %d (%s): decision must be allow, deny, or escalate",
				i+1, rule.Pattern)
		}
	}
	return nil
}
