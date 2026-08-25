package lib

import "testing"

func TestGreet(t *testing.T) {
	if Greet("x") != "hi x" {
		t.Fatal("greet")
	}
}

func TestLookup(t *testing.T) {
	if Lookup(MemStore{}, "k") != "k" {
		t.Fatal("lookup")
	}
}
