// Package escalation implements the M4 escalation queue (architecture §9,
// ADR-016): commands the policy chain neither allows nor denies park as
// JSON records under ~/.hobbes/sessions/<session>/escalations/, wait for a
// human approve/deny (the hobbes-proxy escalations CLI), and expire to
// deny after a timeout. The proxy polls records; this package owns their
// format and lifecycle. All writes are atomic (temp + rename).
package escalation

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"time"
)

// Status is an escalation record's lifecycle state.
type Status string

const (
	Pending  Status = "pending"
	Approved Status = "approved"
	Denied   Status = "denied"
	Expired  Status = "expired"
)

// Record is one parked command. The file is the card the M7 Sessions tab
// will render; keep it self-describing.
type Record struct {
	ID      string `json:"id"`
	Session string `json:"session"`
	Role    string `json:"role"`
	Repo    string `json:"repo"`
	// Command and Dir are exactly what exec was asked to run and where
	// (dir relative to the repo root) — replayability (§9).
	Command string `json:"command"`
	Dir     string `json:"dir,omitempty"`
	// PolicyRule and Reason echo the decisive escalating rule.
	PolicyRule  string `json:"policy_rule"`
	Reason      string `json:"reason,omitempty"`
	RequestedAt string `json:"requested_at"`
	ExpiresAt   string `json:"expires_at"`
	Status      Status `json:"status"`
	ResolvedAt  string `json:"resolved_at,omitempty"`
	// Approver is the OS user who resolved the record (empty on expiry).
	Approver string `json:"approver,omitempty"`
}

// stamp formats queue timestamps (UTC, second precision is plenty).
func stamp(t time.Time) string { return t.UTC().Format(time.RFC3339) }

// parseStamp is the inverse of stamp; zero time on garbage.
func parseStamp(s string) time.Time {
	t, err := time.Parse(time.RFC3339, s)
	if err != nil {
		return time.Time{}
	}
	return t
}

// Deadline returns the record's expiry instant.
func (r *Record) Deadline() time.Time { return parseStamp(r.ExpiresAt) }

// EffectiveStatus is the record's status as of now: a pending record past
// its deadline reads as expired even before anything rewrites the file —
// a dead proxy must not leave commands looking approvable forever.
func (r *Record) EffectiveStatus(now time.Time) Status {
	if r.Status == Pending && now.After(r.Deadline()) {
		return Expired
	}
	return r.Status
}

// NewRecord builds a pending record with a fresh id.
func NewRecord(session, role, repo, command, dir, policyRule, reason string, now time.Time, timeout time.Duration) (*Record, error) {
	var b [2]byte
	if _, err := rand.Read(b[:]); err != nil {
		return nil, fmt.Errorf("escalation: %w", err)
	}
	return &Record{
		ID: fmt.Sprintf("E-%s-%s",
			now.UTC().Format("20060102T150405Z"), hex.EncodeToString(b[:])),
		Session:     session,
		Role:        role,
		Repo:        repo,
		Command:     command,
		Dir:         dir,
		PolicyRule:  policyRule,
		Reason:      reason,
		RequestedAt: stamp(now),
		ExpiresAt:   stamp(now.Add(timeout)),
		Status:      Pending,
	}, nil
}

// write stores the record atomically at path.
func write(path string, r *Record) error {
	data, err := json.MarshalIndent(r, "", "  ")
	if err != nil {
		return fmt.Errorf("escalation: %w", err)
	}
	tmp, err := os.CreateTemp(filepath.Dir(path), ".tmp-escalation-*")
	if err != nil {
		return fmt.Errorf("escalation: %w", err)
	}
	if _, err := tmp.Write(append(data, '\n')); err != nil {
		tmp.Close()
		os.Remove(tmp.Name())
		return fmt.Errorf("escalation: %w", err)
	}
	if err := tmp.Close(); err != nil {
		os.Remove(tmp.Name())
		return fmt.Errorf("escalation: %w", err)
	}
	if err := os.Rename(tmp.Name(), path); err != nil {
		os.Remove(tmp.Name())
		return fmt.Errorf("escalation: %w", err)
	}
	return nil
}

// Create parks the record in dir (creating it), returning the file path.
func Create(dir string, r *Record) (string, error) {
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return "", fmt.Errorf("escalation: %w", err)
	}
	path := filepath.Join(dir, r.ID+".json")
	if err := write(path, r); err != nil {
		return "", err
	}
	return path, nil
}

// Load reads the record at path.
func Load(path string) (*Record, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("escalation: %w", err)
	}
	var r Record
	if err := json.Unmarshal(data, &r); err != nil {
		return nil, fmt.Errorf("escalation: %s: %w", path, err)
	}
	return &r, nil
}

// Resolve applies a human verdict (Approved or Denied) to the pending
// record at path. Only pending records resolve; a pending record past its
// deadline is marked expired instead and the resolution is refused — the
// clock outranks a late approval (ADR-016).
func Resolve(path string, verdict Status, approver string, now time.Time) (*Record, error) {
	if verdict != Approved && verdict != Denied {
		return nil, fmt.Errorf("escalation: cannot resolve to %q", verdict)
	}
	r, err := Load(path)
	if err != nil {
		return nil, err
	}
	if r.Status != Pending {
		return nil, fmt.Errorf("escalation %s is already %s", r.ID, r.Status)
	}
	if now.After(r.Deadline()) {
		_, _ = MarkExpired(path, now) // best effort; the refusal stands
		return nil, fmt.Errorf("escalation %s expired %s ago",
			r.ID, now.Sub(r.Deadline()).Round(time.Second))
	}
	r.Status = verdict
	r.Approver = approver
	r.ResolvedAt = stamp(now)
	if err := write(path, r); err != nil {
		return nil, err
	}
	return r, nil
}

// MarkExpired rewrites a pending record as expired (no approver). Called
// by the proxy at deadline or disconnect, and by Resolve on late verdicts.
func MarkExpired(path string, now time.Time) (*Record, error) {
	r, err := Load(path)
	if err != nil {
		return nil, err
	}
	if r.Status != Pending {
		return r, nil // someone already resolved it; keep their answer
	}
	r.Status = Expired
	r.ResolvedAt = stamp(now)
	if err := write(path, r); err != nil {
		return nil, err
	}
	return r, nil
}

// Item is a queue entry found by List or FindByID.
type Item struct {
	Path   string
	Record *Record
}

// List scans every session under root for escalation records, oldest
// first. Unreadable files are skipped — the queue must list even if one
// record is torn.
func List(root string) ([]Item, error) {
	sessions, err := os.ReadDir(root)
	if os.IsNotExist(err) {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("escalation: %w", err)
	}
	var items []Item
	for _, s := range sessions {
		if !s.IsDir() {
			continue
		}
		dir := filepath.Join(root, s.Name(), "escalations")
		files, err := os.ReadDir(dir)
		if err != nil {
			continue
		}
		for _, f := range files {
			if f.IsDir() || filepath.Ext(f.Name()) != ".json" {
				continue
			}
			path := filepath.Join(dir, f.Name())
			r, err := Load(path)
			if err != nil {
				continue
			}
			items = append(items, Item{Path: path, Record: r})
		}
	}
	sort.Slice(items, func(i, j int) bool {
		return items[i].Record.RequestedAt < items[j].Record.RequestedAt
	})
	return items, nil
}

// FindByID locates one record by id anywhere under root.
func FindByID(root, id string) (Item, error) {
	items, err := List(root)
	if err != nil {
		return Item{}, err
	}
	for _, it := range items {
		if it.Record.ID == id {
			return it, nil
		}
	}
	return Item{}, fmt.Errorf("no escalation %s under %s", id, root)
}
