package policy

import (
	"reflect"
	"testing"
)

// boxLike mirrors the benchmark box policy shape (ADR-057): a deny floor
// plus anchored allow rules for the tests-and-commit a solo agent needs,
// over a default of escalate.
func boxLike() *Chain {
	return &Chain{Files: []*File{
		mkFile("box", "bench.box.policy", Escalate,
			"git push*", "deny",
			"*.tfstate*", "deny",
			"python -m pytest*", "allow",
			"pytest*", "allow",
			"git status*", "allow",
			"git add*", "allow",
			"git commit*", "allow",
			"python -c *", "allow",
			"ls*", "allow",
			"tail*", "allow",
			"cat*", "allow",
		),
	}}
}

func TestResolveCommandCompound(t *testing.T) {
	c := boxLike()
	tests := []struct {
		name string
		cmd  string
		want Decision
	}{
		// The five-fresh-27b defect: a redundant cd prefix must not
		// escalate a command that is itself allowed (C-54).
		{"cd prefix then allowed test", "cd /work && python -m pytest xarray/tests/test_dataset.py", Allow},
		{"env prefix then allowed test", "PYTHONDONTWRITEBYTECODE=1 python -m pytest x.py", Allow},
		{"two allowed segments chained", "git add -A && git commit -m x", Allow},
		{"allowed piped into allowed", "python -m pytest x.py | tail -5", Allow},
		{"lone cd is neutral -> allow", "cd /work", Allow},
		// Deny survives anywhere in a chain (deny-overrides across the
		// whole command) — the hole the old single-string match left open.
		{"deny hidden after an allow", "git status && git push origin", Deny},
		{"deny hidden after cd", "cd /work && git push", Deny},
		{"tfstate deny in a pipe", "cat prod.tfstate | grep secret", Deny},
		// An unmatched segment escalates the whole command, even chained
		// behind an allowed one — the old accidental `*`-swallow allowed it.
		{"unknown segment after allowed", "git status && rm -rf /", Escalate},
		{"unknown command alone", "curl http://x", Escalate},
		// A single allowed command is unchanged.
		{"single allowed", "python -m pytest x.py", Allow},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := c.ResolveCommand(tt.cmd)
			if got.Decision != tt.want {
				t.Errorf("ResolveCommand(%q) = %s, want %s (rule %q)", tt.cmd, got.Decision, tt.want, policyRule(got))
			}
			if got.Command == "" {
				t.Errorf("Command not set for %q", tt.cmd)
			}
		})
	}
}

func policyRule(r Result) string {
	if r.Rule != nil {
		return r.Rule.Pattern
	}
	return "default"
}

func TestSplitTopLevel(t *testing.T) {
	tests := []struct {
		in   string
		want []string
		ok   bool
	}{
		{"a && b", []string{"a", "b"}, true},
		{"a; b ; c", []string{"a", "b", "c"}, true},
		{"a | b", []string{"a", "b"}, true},
		{"a || b", []string{"a", "b"}, true},
		{`echo "a && b"`, []string{`echo "a && b"`}, true}, // operator inside quotes
		{`echo 'a; b'`, []string{`echo 'a; b'`}, true},
		{`echo a\&\& b`, []string{`echo a\&\& b`}, true}, // escaped
		{"a &&", []string{"a"}, true},                    // trailing operator
		{`echo "unbalanced`, nil, false},                 // unbalanced quote -> not ok
	}
	for _, tt := range tests {
		got, ok := splitTopLevel(tt.in)
		if ok != tt.ok || (ok && !reflect.DeepEqual(got, tt.want)) {
			t.Errorf("splitTopLevel(%q) = %v,%v; want %v,%v", tt.in, got, ok, tt.want, tt.ok)
		}
	}
}

func TestStripEnvAssignments(t *testing.T) {
	tests := [][2]string{
		{"FOO=1 python x", "python x"},
		{"A=1 B=2 pytest", "pytest"},
		{`X="a b" cmd`, "cmd"},
		{"python x", "python x"},     // no assignment
		{"1BAD=x cmd", "1BAD=x cmd"}, // invalid name, not stripped
		{"cd /work", "cd /work"},     // not an assignment
	}
	for _, tt := range tests {
		if got := stripEnvAssignments(tt[0]); got != tt[1] {
			t.Errorf("stripEnvAssignments(%q) = %q, want %q", tt[0], got, tt[1])
		}
	}
}
