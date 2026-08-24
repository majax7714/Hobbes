package escalation

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

var t0 = time.Date(2026, 8, 11, 12, 0, 0, 0, time.UTC)

func pending(t *testing.T, dir string, now time.Time) (string, *Record) {
	t.Helper()
	r, err := NewRecord("S-1", "implementer", "/repo", "git push origin main",
		"", "repo.policy: git push*", "pushes need a human", now, 30*time.Minute)
	if err != nil {
		t.Fatal(err)
	}
	path, err := Create(dir, r)
	if err != nil {
		t.Fatal(err)
	}
	return path, r
}

func TestCreateLoadRoundTrip(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "S-1", "escalations")
	path, r := pending(t, dir, t0)

	got, err := Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if got.ID != r.ID || got.Command != "git push origin main" || got.Status != Pending {
		t.Errorf("round trip mangled: %+v", got)
	}
	if got.ExpiresAt != "2026-08-11T12:30:00Z" {
		t.Errorf("expires_at = %q, want requested+30m", got.ExpiresAt)
	}
	if !strings.HasPrefix(got.ID, "E-20260811T120000Z-") {
		t.Errorf("id = %q", got.ID)
	}
}

func TestApproveRecordsApprover(t *testing.T) {
	path, _ := pending(t, t.TempDir(), t0)
	r, err := Resolve(path, Approved, "max", t0.Add(time.Minute))
	if err != nil {
		t.Fatal(err)
	}
	if r.Status != Approved || r.Approver != "max" || r.ResolvedAt == "" {
		t.Errorf("resolved = %+v", r)
	}
	// And it persisted.
	if got, _ := Load(path); got.Status != Approved || got.Approver != "max" {
		t.Errorf("persisted = %+v", got)
	}
}

func TestResolveRefusesNonVerdicts(t *testing.T) {
	path, _ := pending(t, t.TempDir(), t0)
	if _, err := Resolve(path, Expired, "max", t0); err == nil {
		t.Error("resolving to expired must be refused — only the clock expires")
	}
	if _, err := Resolve(path, Pending, "max", t0); err == nil {
		t.Error("resolving to pending must be refused")
	}
}

func TestResolveRefusesAlreadyResolved(t *testing.T) {
	path, _ := pending(t, t.TempDir(), t0)
	if _, err := Resolve(path, Denied, "max", t0.Add(time.Minute)); err != nil {
		t.Fatal(err)
	}
	_, err := Resolve(path, Approved, "max", t0.Add(2*time.Minute))
	if err == nil || !strings.Contains(err.Error(), "already denied") {
		t.Errorf("err = %v, want already-denied refusal", err)
	}
}

func TestLateApprovalExpiresInstead(t *testing.T) {
	path, _ := pending(t, t.TempDir(), t0)
	late := t0.Add(31 * time.Minute)
	_, err := Resolve(path, Approved, "max", late)
	if err == nil || !strings.Contains(err.Error(), "expired") {
		t.Errorf("err = %v, want expiry refusal", err)
	}
	// The refusal also settled the record.
	if got, _ := Load(path); got.Status != Expired || got.Approver != "" {
		t.Errorf("record after late approval = %+v", got)
	}
}

func TestEffectiveStatusExpiresByClock(t *testing.T) {
	_, r := pending(t, t.TempDir(), t0)
	if s := r.EffectiveStatus(t0.Add(time.Minute)); s != Pending {
		t.Errorf("fresh record reads %q", s)
	}
	if s := r.EffectiveStatus(t0.Add(time.Hour)); s != Expired {
		t.Errorf("stale pending record reads %q, want expired", s)
	}
}

func TestMarkExpiredKeepsExistingResolutions(t *testing.T) {
	path, _ := pending(t, t.TempDir(), t0)
	if _, err := Resolve(path, Approved, "max", t0.Add(time.Minute)); err != nil {
		t.Fatal(err)
	}
	r, err := MarkExpired(path, t0.Add(2*time.Minute))
	if err != nil {
		t.Fatal(err)
	}
	if r.Status != Approved {
		t.Errorf("MarkExpired overwrote a resolution: %+v", r)
	}
}

func TestListSpansSessionsOldestFirstAndSkipsTorn(t *testing.T) {
	root := t.TempDir()
	pending(t, filepath.Join(root, "S-b", "escalations"), t0.Add(time.Minute))
	_, first := pending(t, filepath.Join(root, "S-a", "escalations"), t0)
	// A torn file must not break listing.
	torn := filepath.Join(root, "S-a", "escalations", "E-torn.json")
	if err := os.WriteFile(torn, []byte("{half"), 0o600); err != nil {
		t.Fatal(err)
	}

	items, err := List(root)
	if err != nil {
		t.Fatal(err)
	}
	if len(items) != 2 {
		t.Fatalf("got %d items, want 2", len(items))
	}
	if items[0].Record.ID != first.ID {
		t.Errorf("not oldest-first: %s before %s", items[0].Record.ID, items[1].Record.ID)
	}
}

func TestListMissingRootIsEmptyNotError(t *testing.T) {
	items, err := List(filepath.Join(t.TempDir(), "nope"))
	if err != nil || items != nil {
		t.Errorf("items=%v err=%v, want nil/nil", items, err)
	}
}

func TestFindByID(t *testing.T) {
	root := t.TempDir()
	_, r := pending(t, filepath.Join(root, "S-1", "escalations"), t0)
	item, err := FindByID(root, r.ID)
	if err != nil || item.Record.ID != r.ID {
		t.Errorf("item=%+v err=%v", item, err)
	}
	if _, err := FindByID(root, "E-nope"); err == nil {
		t.Error("unknown id must error")
	}
}
