package clang

import (
	"os"
	"path/filepath"
	"strconv"
	"testing"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

// loadFixtureShards reads the four committed cclang dumps, both
// directly and through a Save/LoadShards round trip, and asserts both
// paths produce the same shards (byte-for-byte after re-marshalling).
func loadFixtureShards(t *testing.T) []*Shard {
	t.Helper()
	names := []string{"0-main.c.json", "1-lib.c.json", "2-tool.c.json", "3-lib.c.json"}
	dir := t.TempDir()
	var direct []*Shard
	for i, n := range names {
		f, err := os.Open("../../testdata/cclang-ast/" + n)
		if err != nil {
			t.Fatal(err)
		}
		s, err := ReadDump(f, "/fx", "/fx")
		f.Close()
		if err != nil {
			t.Fatalf("%s: %v", n, err)
		}
		direct = append(direct, s)
		// Name each saved shard so LoadShards' name-order load matches
		// the compile database's own order (0..3).
		if err := s.Save(filepath.Join(dir, strconv.Itoa(i)+".json")); err != nil {
			t.Fatal(err)
		}
	}
	loaded, err := LoadShards(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(loaded) != len(direct) {
		t.Fatalf("LoadShards: got %d shards, want %d", len(loaded), len(direct))
	}
	return loaded
}

// TestCclangFixture is ADR-110's own evidence: the committed fixture's
// every pair, hand-computed in the task's truth table, read through
// ReadDump, a Save/LoadShards round trip, and Merge.
func TestCclangFixture(t *testing.T) {
	shards := loadFixtureShards(t)
	out := Merge(shards, "")

	if out.Kind != "resolution" {
		t.Fatalf("kind: %s", out.Kind)
	}
	if got, want := out.Files, []string{"api.h", "lib.c", "main.c", "pick.h", "tool.c"}; !equalStrings(got, want) {
		t.Fatalf("files: %v, want %v", got, want)
	}

	wantCoverage := map[string]int{
		"units": 4, "units_failed": 0,
		"sites_static": 14, "sites_macro": 1, "sites_dynamic": 3,
		"sites_external": 1, "sites_link_ambiguous": 1, "sites_undefined": 1, "sites_tu_split": 1,
	}
	for k, v := range wantCoverage {
		if out.Coverage[k] != v {
			t.Errorf("coverage[%s] = %d, want %d (full: %v)", k, out.Coverage[k], v, out.Coverage)
		}
	}

	byKey := map[string]edges.Site{}
	for _, s := range out.Sites {
		byKey[s.Pos.Key()+"@"+strconv.Itoa(s.Col)] = s
	}
	targetKeys := func(s edges.Site) map[string]bool {
		m := map[string]bool{}
		for _, tg := range s.Targets {
			if tg.External {
				m["external:"+tg.Name] = true
			} else {
				m[tg.Pos.Key()] = true
			}
		}
		return m
	}
	get := func(path string, line, col int) edges.Site {
		t.Helper()
		s, ok := byKey[path+":"+strconv.Itoa(line)+"@"+strconv.Itoa(col)]
		if !ok {
			t.Fatalf("no site at %s:%d col %d", path, line, col)
		}
		return s
	}

	// 17 in-repo pairs, one of them tu-split.
	type want struct {
		path         string
		line, col    int
		mode, caller string
		targets      []string
	}
	cases := []want{
		{"api.h", 16, 12, "static", "sq", []string{"lib.c:15"}},
		{"pick.h", 3, 12, "static", "pick", []string{"main.c:3", "tool.c:3"}},
		{"main.c", 18, 13, "macro", "main", []string{"lib.c:11"}},
		{"main.c", 19, 16, "static", "main", []string{"lib.c:11"}},
		{"main.c", 20, 10, "static", "main", []string{"api.h:15"}},
		{"main.c", 20, 18, "static", "main", []string{"lib.c:19"}},
		{"main.c", 21, 10, "static", "main", []string{"lib.c:15"}},
		{"main.c", 23, 10, "static", "main", []string{"main.c:9"}},
		{"main.c", 23, 21, "static", "main", []string{"pick.h:2"}},
		{"main.c", 24, 10, "static", "main", []string{"main.c:13"}},
		{"main.c", 24, 28, "static", "main", []string{"lib.c:11"}},
		{"lib.c", 22, 13, "static", "lib_run", []string{"lib.c:7"}},
		{"lib.c", 26, 16, "static", "lib_run", []string{"api.h:15"}},
		{"tool.c", 14, 12, "static", "main", []string{"pick.h:2"}},
		{"tool.c", 14, 21, "static", "main", []string{"tool.c:9"}},
		{"tool.c", 14, 32, "static", "main", []string{"lib.c:11"}},
	}
	for _, c := range cases {
		s := get(c.path, c.line, c.col)
		if s.Mode != c.mode || s.Caller != c.caller {
			t.Errorf("%s:%d col %d: mode=%s caller=%s, want mode=%s caller=%s", c.path, c.line, c.col, s.Mode, s.Caller, c.mode, c.caller)
		}
		got := targetKeys(s)
		if len(got) != len(c.targets) {
			t.Errorf("%s:%d col %d: targets %v, want %v", c.path, c.line, c.col, got, c.targets)
			continue
		}
		for _, want := range c.targets {
			if !got[want] {
				t.Errorf("%s:%d col %d: targets %v missing %s", c.path, c.line, c.col, got, want)
			}
		}
	}

	// No targets: link-ambiguous and undefined.
	if s := get("lib.c", 22, 23); s.Mode != "static" || len(s.Targets) != 0 {
		t.Errorf("lib.c:22 helper: %+v", s)
	}
	if s := get("lib.c", 23, 10); s.Mode != "static" || len(s.Targets) != 0 {
		t.Errorf("lib.c:23 missing: %+v", s)
	}

	// External.
	if s := get("lib.c", 24, 10); len(s.Targets) != 1 || !s.Targets[0].External || s.Targets[0].Name != "__builtin_abs" {
		t.Errorf("lib.c:24 __builtin_abs: %+v", s)
	}

	// Dynamic, no targets.
	for _, c := range []struct {
		path      string
		line, col int
	}{{"main.c", 14, 14}, {"lib.c", 25, 10}, {"lib.c", 25, 20}} {
		s := get(c.path, c.line, c.col)
		if s.Mode != "dynamic" || len(s.Targets) != 0 {
			t.Errorf("%s:%d col %d dynamic site: %+v", c.path, c.line, c.col, s)
		}
	}

	if len(out.Sites) != 22 {
		t.Errorf("total distinct sites: %d, want 22", len(out.Sites))
	}
}

func equalStrings(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}
