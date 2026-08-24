package policy

import "testing"

func TestResolveAllows(t *testing.T) {
	rules := []Rule{{Pattern: "ls", Decision: "allow"}}
	if Resolve(rules, "ls -la") != "allow" {
		t.Fatal("expected allow")
	}
}

func TestDefaultEscalates(t *testing.T) {
	if Resolve(nil, "rm -rf /") != "escalate" {
		t.Fatal("expected escalate")
	}
}
