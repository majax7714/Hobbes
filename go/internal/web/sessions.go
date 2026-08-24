package web

import (
	"bufio"
	"encoding/json"
	"net/http"
	"os"
	"os/user"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/majax7714/Hobbes/go/internal/escalation"
	"github.com/majax7714/Hobbes/go/internal/recorder"
)

// maxFlightLines caps one flight-log page. The Sessions tab tails with a
// line cursor (ADR-022), so a long-running session pages instead of
// re-sending its whole history on every poll.
const maxFlightLines = 500

// sessionSummary is one card in the Sessions tab: who ran, against what,
// how it decided, and whether anything is waiting on a human.
type sessionSummary struct {
	ID          string `json:"id"`
	Role        string `json:"role"`
	Repo        string `json:"repo"`
	Events      int    `json:"events"`
	Allowed     int    `json:"allowed"`
	Denied      int    `json:"denied"`
	Escalated   int    `json:"escalated"`
	Pending     int    `json:"pending"`
	FirstSeen   string `json:"first_seen,omitempty"`
	LastSeen    string `json:"last_seen,omitempty"`
	LastCommand string `json:"last_command,omitempty"`
	Active      bool   `json:"active"`
}

// activeWindow is how recently a session must have logged to read as
// live. The proxy writes an event per tool call, so a session that has
// been quiet longer than this is between tasks or gone; nothing in the
// flight log records an exit (ADR-015 logs calls, not lifecycle).
const activeWindow = 5 * time.Minute

func (s *Server) handleSessions(w http.ResponseWriter, r *http.Request) {
	entries, err := os.ReadDir(s.cfg.LogDir)
	if os.IsNotExist(err) {
		writeJSON(w, http.StatusOK, map[string]any{"sessions": []sessionSummary{}, "log_dir": s.cfg.LogDir})
		return
	}
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "")
		return
	}

	pending := map[string]int{}
	if items, listErr := escalation.List(s.cfg.LogDir); listErr == nil {
		now := time.Now()
		for _, it := range items {
			if it.Record.EffectiveStatus(now) == escalation.Pending {
				pending[it.Record.Session]++
			}
		}
	}

	sessions := []sessionSummary{}
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		sum := s.summarize(e.Name())
		sum.Pending = pending[e.Name()]
		sessions = append(sessions, sum)
	}
	// Newest activity first: the session you care about is the one that
	// just did something.
	sort.Slice(sessions, func(i, j int) bool {
		if sessions[i].LastSeen != sessions[j].LastSeen {
			return sessions[i].LastSeen > sessions[j].LastSeen
		}
		return sessions[i].ID < sessions[j].ID
	})
	writeJSON(w, http.StatusOK, map[string]any{"sessions": sessions, "log_dir": s.cfg.LogDir})
}

// summarize folds one session's flight log into a card. A torn last line
// (the proxy writing as we read) is skipped, not an error.
func (s *Server) summarize(id string) sessionSummary {
	sum := sessionSummary{ID: id}
	events, _, err := s.readFlight(id, 0, -1)
	if err != nil {
		return sum
	}
	sum.Events = len(events)
	for _, ev := range events {
		if ev.Role != "" {
			sum.Role = ev.Role
		}
		switch ev.Decision {
		case "allow":
			sum.Allowed++
		case "deny":
			sum.Denied++
		case "escalate":
			sum.Escalated++
		}
		if sum.FirstSeen == "" {
			sum.FirstSeen = ev.TS
		}
		sum.LastSeen = ev.TS
		if len(ev.Argv) > 0 {
			sum.LastCommand = strings.Join(ev.Argv, " ")
		}
	}
	if t, parseErr := time.Parse(time.RFC3339Nano, sum.LastSeen); parseErr == nil {
		sum.Active = time.Since(t) < activeWindow
	}
	return sum
}

// flightPage is one page of a session's flight log plus the cursor to
// ask for the next.
type flightPage struct {
	Session string           `json:"session"`
	Events  []recorder.Event `json:"events"`
	// After is the cursor this page was read from. Echoed so a client
	// can tell whether a page it is holding still starts where it is —
	// without it, a re-render can append the same page twice.
	After int `json:"after"`
	// Next is the line cursor to pass as ?after= on the next poll.
	Next int `json:"next"`
	// Torn counts unparseable lines skipped in this page — usually the
	// proxy writing the last line as it was read.
	Torn int `json:"torn"`
	// More is set when the page hit the cap and another awaits.
	More bool `json:"more"`
}

// sessionID rejects anything that is not a bare directory name, so a
// cursor cannot walk out of the session root.
func sessionID(id string) bool {
	return id != "" && id != "." && id != ".." &&
		!strings.ContainsAny(id, `/\`) && !strings.HasPrefix(id, ".")
}

func (s *Server) handleFlight(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	if !sessionID(id) {
		writeError(w, http.StatusBadRequest, "bad session id", "")
		return
	}
	after, _ := strconv.Atoi(r.URL.Query().Get("after"))
	if after < 0 {
		after = 0
	}
	events, torn, err := s.readFlight(id, after, maxFlightLines)
	if os.IsNotExist(err) {
		writeError(w, http.StatusNotFound, "no flight log for session "+id, "")
		return
	}
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "")
		return
	}
	writeJSON(w, http.StatusOK, flightPage{
		Session: id,
		Events:  events,
		After:   after,
		Next:    after + len(events) + torn,
		Torn:    torn,
		More:    len(events)+torn >= maxFlightLines,
	})
}

// readFlight reads a session's JSONL log from line `after`, returning at
// most `limit` events (-1 for all) and the count of lines skipped as
// unparseable. Unparseable lines are counted, never dropped silently:
// the cursor must stay aligned with the file.
func (s *Server) readFlight(id string, after, limit int) ([]recorder.Event, int, error) {
	path := filepath.Join(s.cfg.LogDir, id, "flight.jsonl")
	f, err := os.Open(path)
	if err != nil {
		return nil, 0, err
	}
	defer f.Close()

	events := []recorder.Event{}
	torn := 0
	scanner := bufio.NewScanner(f)
	scanner.Buffer(make([]byte, 0, 64*1024), 4*1024*1024)
	line := 0
	for scanner.Scan() {
		line++
		if line <= after {
			continue
		}
		if limit >= 0 && len(events)+torn >= limit {
			break
		}
		var ev recorder.Event
		if err := json.Unmarshal(scanner.Bytes(), &ev); err != nil {
			torn++
			continue
		}
		events = append(events, ev)
	}
	if err := scanner.Err(); err != nil {
		return nil, 0, err
	}
	return events, torn, nil
}

// --- escalation queue (ADR-016) ---------------------------------------------

// escalationCard is one parked command as the UI shows it: the record,
// plus the status the clock says it has right now.
type escalationCard struct {
	*escalation.Record
	Effective   escalation.Status `json:"effective_status"`
	SecondsLeft int               `json:"seconds_left"`
	Resolvable  bool              `json:"resolvable"`
}

func card(r *escalation.Record, now time.Time) escalationCard {
	eff := r.EffectiveStatus(now)
	c := escalationCard{Record: r, Effective: eff, Resolvable: eff == escalation.Pending}
	if left := int(r.Deadline().Sub(now).Seconds()); eff == escalation.Pending && left > 0 {
		c.SecondsLeft = left
	}
	return c
}

func (s *Server) handleEscalations(w http.ResponseWriter, r *http.Request) {
	all := r.URL.Query().Get("all") == "1"
	items, err := escalation.List(s.cfg.LogDir)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "")
		return
	}
	now := time.Now()
	cards := []escalationCard{}
	for _, it := range items {
		c := card(it.Record, now)
		if !all && c.Effective != escalation.Pending {
			continue
		}
		cards = append(cards, c)
	}
	writeJSON(w, http.StatusOK, map[string]any{"escalations": cards})
}

// handleResolveEscalation is the surface's only mutation. It delegates to
// escalation.Resolve, so a verdict from the browser obeys the same rules
// as one from the CLI — including the deadline outranking a late approval.
func (s *Server) handleResolveEscalation(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	var verdict escalation.Status
	switch r.PathValue("verdict") {
	case "approve":
		verdict = escalation.Approved
	case "deny":
		verdict = escalation.Denied
	default:
		writeError(w, http.StatusNotFound, "verdict must be approve or deny", "")
		return
	}
	item, err := escalation.FindByID(s.cfg.LogDir, id)
	if err != nil {
		writeError(w, http.StatusNotFound, err.Error(), "")
		return
	}
	rec, err := escalation.Resolve(item.Path, verdict, approverName(), time.Now())
	if err != nil {
		// A record that expired or was already resolved is a conflict,
		// not a server fault: the queue moved under the tab. Re-read it
		// so the answer shows what it actually is now.
		body := map[string]any{"error": err.Error()}
		if current, loadErr := escalation.Load(item.Path); loadErr == nil {
			body["escalation"] = card(current, time.Now())
		}
		writeJSON(w, http.StatusConflict, body)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"escalation": card(rec, time.Now())})
}

// approverName is the OS user recorded on a verdict, matching the CLI's
// behaviour (ADR-016: approvals log the approver).
func approverName() string {
	if u, err := user.Current(); err == nil && u.Username != "" {
		return u.Username
	}
	if n := os.Getenv("USER"); n != "" {
		return n
	}
	return "unknown"
}
