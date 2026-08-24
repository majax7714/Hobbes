package web

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/majax7714/Hobbes/go/internal/escalation"
	"github.com/majax7714/Hobbes/go/internal/recorder"
)

// flightLog writes a session's flight log, one Event per line.
func flightLog(t *testing.T, logDir, session string, events ...recorder.Event) {
	t.Helper()
	var b strings.Builder
	for _, ev := range events {
		line, err := json.Marshal(ev)
		if err != nil {
			t.Fatal(err)
		}
		b.Write(line)
		b.WriteByte('\n')
	}
	writeFile(t, filepath.Join(logDir, session, "flight.jsonl"), b.String())
}

func exitCode(n int) *int { return &n }

// park writes a pending escalation into a session's queue.
func park(t *testing.T, logDir, session, command string, timeout time.Duration) *escalation.Record {
	t.Helper()
	rec, err := escalation.NewRecord(session, "implementer", "/repo", command, "",
		"repo: "+command, "needs a human", time.Now(), timeout)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := escalation.Create(filepath.Join(logDir, session, "escalations"), rec); err != nil {
		t.Fatal(err)
	}
	return rec
}

func TestSessionsSummarizeTheFlightLog(t *testing.T) {
	f := newFixture(t)
	now := time.Now().UTC()
	flightLog(t, f.logDir, "S-1",
		recorder.Event{TS: now.Add(-2 * time.Minute).Format(time.RFC3339Nano), Session: "S-1",
			Role: "implementer", Tool: "exec", Argv: []string{"go", "test", "./..."},
			Decision: "allow", PolicyRule: "repo: go *", Exit: exitCode(0)},
		recorder.Event{TS: now.Add(-1 * time.Minute).Format(time.RFC3339Nano), Session: "S-1",
			Role: "implementer", Tool: "exec", Argv: []string{"curl", "evil.example"},
			Decision: "deny", PolicyRule: "box: curl *"},
	)
	// A stale session: last event well outside the active window.
	flightLog(t, f.logDir, "S-0",
		recorder.Event{TS: now.Add(-3 * time.Hour).Format(time.RFC3339Nano), Session: "S-0",
			Role: "reviewer", Tool: "exec", Argv: []string{"git", "log"}, Decision: "allow"},
	)
	park(t, f.logDir, "S-1", "terraform apply", time.Hour)

	body := f.getJSON(t, "/api/sessions")
	sessions, _ := body["sessions"].([]any)
	if len(sessions) != 2 {
		t.Fatalf("got %d sessions, want 2", len(sessions))
	}
	// Newest activity first.
	first := sessions[0].(map[string]any)
	if first["id"] != "S-1" {
		t.Fatalf("first session = %v, want S-1", first["id"])
	}
	if first["role"] != "implementer" {
		t.Errorf("role = %v", first["role"])
	}
	if first["allowed"] != float64(1) || first["denied"] != float64(1) {
		t.Errorf("decision counts = %v", first)
	}
	if first["pending"] != float64(1) {
		t.Errorf("pending = %v, want the parked command counted", first["pending"])
	}
	if first["active"] != true {
		t.Errorf("active = %v, want true for a session that just logged", first["active"])
	}
	if first["last_command"] != "curl evil.example" {
		t.Errorf("last_command = %v", first["last_command"])
	}
	if second := sessions[1].(map[string]any); second["active"] != false {
		t.Errorf("old session active = %v, want false", second["active"])
	}
}

func TestFlightTailUsesTheCursor(t *testing.T) {
	f := newFixture(t)
	base := time.Now().UTC()
	events := make([]recorder.Event, 3)
	for i := range events {
		events[i] = recorder.Event{
			TS:      base.Add(time.Duration(i) * time.Second).Format(time.RFC3339Nano),
			Session: "S-1", Role: "implementer", Tool: "exec",
			Argv: []string{"echo", string(rune('a' + i))}, Decision: "allow",
		}
	}
	flightLog(t, f.logDir, "S-1", events...)

	body := f.getJSON(t, "/api/sessions/S-1/flight")
	got, _ := body["events"].([]any)
	if len(got) != 3 || body["next"] != float64(3) {
		t.Fatalf("first page = %d events, next %v", len(got), body["next"])
	}

	// Nothing new: the same cursor returns an empty page, not a replay.
	body = f.getJSON(t, "/api/sessions/S-1/flight?after=3")
	if got, _ := body["events"].([]any); len(got) != 0 {
		t.Fatalf("second page = %d events, want 0", len(got))
	}

	// One more line appended: only the new one comes back.
	flightLog(t, f.logDir, "S-1", append(events, recorder.Event{
		TS: base.Add(9 * time.Second).Format(time.RFC3339Nano), Session: "S-1",
		Tool: "exec", Argv: []string{"echo", "d"}, Decision: "allow",
	})...)
	body = f.getJSON(t, "/api/sessions/S-1/flight?after=3")
	got, _ = body["events"].([]any)
	if len(got) != 1 {
		t.Fatalf("tail = %d events, want 1", len(got))
	}
	if argv := got[0].(map[string]any)["argv"].([]any); argv[1] != "d" {
		t.Errorf("tailed the wrong event: %v", argv)
	}
}

func TestFlightSkipsTornLinesWithoutLosingTheCursor(t *testing.T) {
	f := newFixture(t)
	// A half-written last line is what a live proxy looks like mid-write.
	writeFile(t, filepath.Join(f.logDir, "S-1", "flight.jsonl"),
		`{"ts":"2026-08-11T00:00:00Z","session":"S-1","tool":"exec","argv":["ls"],"decision":"allow"}`+"\n"+
			`{"ts":"2026-08-11T00:00:01Z","sess`+"\n")
	body := f.getJSON(t, "/api/sessions/S-1/flight")
	if got, _ := body["events"].([]any); len(got) != 1 {
		t.Fatalf("events = %d, want the one whole line", len(got))
	}
	if body["torn"] != float64(1) {
		t.Errorf("torn = %v, want 1", body["torn"])
	}
	// The cursor counts the torn line too, so the next poll does not
	// re-read it forever.
	if body["next"] != float64(2) {
		t.Errorf("next = %v, want 2", body["next"])
	}
}

func TestFlightRejectsSessionPathEscapes(t *testing.T) {
	f := newFixture(t)
	for _, id := range []string{"..", ".hidden"} {
		rec := f.get(t, "/api/sessions/"+id+"/flight")
		if rec.Code == http.StatusOK {
			t.Errorf("GET flight for %q = 200, want refusal", id)
		}
	}
}

func TestEscalationsListPendingOnly(t *testing.T) {
	f := newFixture(t)
	park(t, f.logDir, "S-1", "terraform apply", time.Hour)
	expired := park(t, f.logDir, "S-1", "rm -rf /tmp/x", -time.Minute)

	body := f.getJSON(t, "/api/escalations")
	cards, _ := body["escalations"].([]any)
	if len(cards) != 1 {
		t.Fatalf("pending = %d, want 1 (the other is past its deadline)", len(cards))
	}
	card := cards[0].(map[string]any)
	if card["command"] != "terraform apply" || card["resolvable"] != true {
		t.Errorf("card = %v", card)
	}
	if card["seconds_left"].(float64) <= 0 {
		t.Errorf("seconds_left = %v, want a countdown", card["seconds_left"])
	}

	// ?all=1 shows the whole queue, with the clock's verdict applied.
	body = f.getJSON(t, "/api/escalations?all=1")
	cards, _ = body["escalations"].([]any)
	if len(cards) != 2 {
		t.Fatalf("all = %d, want 2", len(cards))
	}
	for _, c := range cards {
		m := c.(map[string]any)
		if m["id"] == expired.ID && m["effective_status"] != "expired" {
			t.Errorf("expired record reads as %v", m["effective_status"])
		}
	}
}

func TestApproveResolvesTheRecordOnDisk(t *testing.T) {
	f := newFixture(t)
	rec := park(t, f.logDir, "S-1", "terraform apply", time.Hour)

	res := f.do(t, http.MethodPost, "/api/escalations/"+rec.ID+"/approve")
	if res.Code != http.StatusOK {
		t.Fatalf("approve = %d (%s)", res.Code, res.Body)
	}
	var body struct {
		Escalation struct {
			Status   string `json:"status"`
			Approver string `json:"approver"`
		} `json:"escalation"`
	}
	if err := json.Unmarshal(res.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body.Escalation.Status != string(escalation.Approved) {
		t.Errorf("status = %q, want approved", body.Escalation.Status)
	}
	if body.Escalation.Approver == "" {
		t.Error("approver not recorded (ADR-016: approvals log the approver)")
	}

	// The verdict must be on disk, where the proxy polls for it.
	item, err := escalation.FindByID(f.logDir, rec.ID)
	if err != nil {
		t.Fatal(err)
	}
	if item.Record.Status != escalation.Approved {
		t.Fatalf("on-disk status = %q, want approved", item.Record.Status)
	}
}

func TestDenyAndDoubleResolveConflict(t *testing.T) {
	f := newFixture(t)
	rec := park(t, f.logDir, "S-1", "npm publish", time.Hour)

	if res := f.do(t, http.MethodPost, "/api/escalations/"+rec.ID+"/deny"); res.Code != http.StatusOK {
		t.Fatalf("deny = %d (%s)", res.Code, res.Body)
	}
	// A second verdict on the same record is a conflict, and the answer
	// says what the record actually is now.
	res := f.do(t, http.MethodPost, "/api/escalations/"+rec.ID+"/approve")
	if res.Code != http.StatusConflict {
		t.Fatalf("second verdict = %d, want 409", res.Code)
	}
	if !strings.Contains(res.Body.String(), "denied") {
		t.Errorf("conflict body = %s, want it to name the standing verdict", res.Body)
	}
}

func TestExpiredEscalationCannotBeApproved(t *testing.T) {
	f := newFixture(t)
	rec := park(t, f.logDir, "S-1", "terraform apply", -time.Minute)

	res := f.do(t, http.MethodPost, "/api/escalations/"+rec.ID+"/approve")
	if res.Code != http.StatusConflict {
		t.Fatalf("late approve = %d, want 409 — the clock outranks the browser", res.Code)
	}
	item, err := escalation.FindByID(f.logDir, rec.ID)
	if err != nil {
		t.Fatal(err)
	}
	if item.Record.Status != escalation.Expired {
		t.Errorf("status = %q, want expired", item.Record.Status)
	}
	if item.Record.Approver != "" {
		t.Errorf("approver = %q, want none on an expiry", item.Record.Approver)
	}
}

func TestUnknownEscalationIs404(t *testing.T) {
	f := newFixture(t)
	if res := f.do(t, http.MethodPost, "/api/escalations/nope/approve"); res.Code != http.StatusNotFound {
		t.Fatalf("unknown id = %d, want 404", res.Code)
	}
	if res := f.do(t, http.MethodPost, "/api/escalations/nope/maybe"); res.Code != http.StatusNotFound {
		t.Fatalf("unknown verdict = %d, want 404", res.Code)
	}
}

func TestEscalationsAreReadOnlyToGET(t *testing.T) {
	f := newFixture(t)
	rec := park(t, f.logDir, "S-1", "terraform apply", time.Hour)
	// The mutation is POST-only; a GET must not resolve anything.
	if res := f.get(t, "/api/escalations/"+rec.ID+"/approve"); res.Code == http.StatusOK {
		t.Fatalf("GET on the resolve route = 200, want refusal")
	}
	item, err := escalation.FindByID(f.logDir, rec.ID)
	if err != nil {
		t.Fatal(err)
	}
	if item.Record.Status != escalation.Pending {
		t.Fatalf("status = %q, want still pending", item.Record.Status)
	}
}

func TestSessionsWithNoLogDir(t *testing.T) {
	repo := t.TempDir()
	gitIn(t, repo, "init", "-q")
	srv, err := New(Config{RepoRoot: repo, LogDir: filepath.Join(t.TempDir(), "absent")})
	if err != nil {
		t.Fatal(err)
	}
	f := &fixture{repo: repo, srv: srv}
	body := f.getJSON(t, "/api/sessions")
	if sessions, _ := body["sessions"].([]any); len(sessions) != 0 {
		t.Fatalf("sessions = %v, want an empty list, not an error", sessions)
	}
	if _, err := os.Stat(filepath.Join(t.TempDir(), "absent")); !os.IsNotExist(err) {
		t.Error("the server must not create the session root")
	}
}

func TestFlightPageEchoesItsCursor(t *testing.T) {
	f := newFixture(t)
	flightLog(t, f.logDir, "S-1", recorder.Event{
		TS: time.Now().UTC().Format(time.RFC3339Nano), Session: "S-1",
		Tool: "exec", Argv: []string{"ls"}, Decision: "allow",
	})
	// The tail applies a page only if it starts where the client is; the
	// echoed cursor is what makes that check possible, and without it a
	// re-render appends the same page twice.
	first := f.getJSON(t, "/api/sessions/S-1/flight")
	if first["after"] != float64(0) {
		t.Errorf("after = %v, want 0", first["after"])
	}
	second := f.getJSON(t, "/api/sessions/S-1/flight?after=1")
	if second["after"] != float64(1) || second["next"] != float64(1) {
		t.Errorf("after=%v next=%v, want 1 and 1", second["after"], second["next"])
	}
}
