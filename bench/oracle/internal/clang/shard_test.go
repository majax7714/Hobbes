package clang

import (
	"path/filepath"
	"reflect"
	"testing"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

// TestSaveLoadShardsRoundTrip covers Save/LoadShards directly: a shard
// saved to disk and reloaded reads back identical, and shards load in
// name order.
func TestSaveLoadShardsRoundTrip(t *testing.T) {
	dir := t.TempDir()
	want := []*Shard{
		{
			File:  "b.c",
			Files: []string{"a.h", "b.c"},
			Decls: []Decl{{Name: "f", Body: true, Static: true, InRepo: true, Pos: edges.Pos{Path: "b.c", Line: 3}}},
			Calls: []Call{{Site: edges.Pos{Path: "b.c", Line: 4}, Col: 2, Spell: edges.Pos{Path: "b.c", Line: 4}, SpellCol: 2, Caller: "f", Mode: "static", Callee: "g"}},
		},
		{
			File:   "z.c",
			Files:  []string{"z.c"},
			Failed: true,
			Stderr: "z.c:1:1: error: ...",
		},
	}
	if err := want[0].Save(filepath.Join(dir, "0-b.c.json")); err != nil {
		t.Fatal(err)
	}
	if err := want[1].Save(filepath.Join(dir, "1-z.c.json")); err != nil {
		t.Fatal(err)
	}
	got, err := LoadShards(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 2 {
		t.Fatalf("want 2 shards, got %d", len(got))
	}
	if !reflect.DeepEqual(got[0], want[0]) {
		t.Errorf("shard 0: got %+v, want %+v", got[0], want[0])
	}
	if !reflect.DeepEqual(got[1], want[1]) {
		t.Errorf("shard 1: got %+v, want %+v", got[1], want[1])
	}
}
