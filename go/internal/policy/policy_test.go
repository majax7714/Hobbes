package policy

import (
	"strings"
	"testing"
)

func TestParseFileValid(t *testing.T) {
	data := []byte(`
version: 1
scope: repo
default: escalate
rules:
  - pattern: "git push --force*"
    decision: deny
    reason: "force-push forbidden"
  - pattern: "git status*"
    decision: allow
`)
	f, err := ParseFile(data, "test.policy")
	if err != nil {
		t.Fatalf("ParseFile: %v", err)
	}
	if f.Version != 1 || f.Scope != "repo" || f.Default != Escalate {
		t.Errorf("header mismatch: %+v", f)
	}
	if len(f.Rules) != 2 {
		t.Fatalf("got %d rules, want 2", len(f.Rules))
	}
	if f.Rules[0].Decision != Deny || f.Rules[0].Reason != "force-push forbidden" {
		t.Errorf("rule 0 mismatch: %+v", f.Rules[0])
	}
	if f.Source != "test.policy" {
		t.Errorf("Source = %q, want test.policy", f.Source)
	}
}

func TestParseFileErrors(t *testing.T) {
	tests := []struct {
		name    string
		data    string
		wantErr string
	}{
		{
			"unknown key is a loud error",
			"version: 1\nrules:\n  - pattern: \"x\"\n    descision: allow\n",
			"field descision not found",
		},
		{
			"missing version",
			"rules:\n  - pattern: \"x\"\n    decision: allow\n",
			"unsupported policy version 0",
		},
		{
			"future version",
			"version: 2\nrules: []\n",
			"unsupported policy version 2",
		},
		{
			"invalid decision",
			"version: 1\nrules:\n  - pattern: \"x\"\n    decision: maybe\n",
			`invalid decision "maybe"`,
		},
		{
			"empty pattern",
			"version: 1\nrules:\n  - pattern: \"\"\n    decision: allow\n",
			"pattern must not be empty",
		},
		{
			"invalid scope",
			"version: 1\nscope: galaxy\nrules: []\n",
			`invalid scope "galaxy"`,
		},
		{
			"invalid default",
			"version: 1\ndefault: yolo\nrules: []\n",
			`invalid default "yolo"`,
		},
		{
			"empty file",
			"",
			"policy file is empty",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := ParseFile([]byte(tt.data), "test.policy")
			if err == nil {
				t.Fatal("ParseFile succeeded, want error")
			}
			if !strings.Contains(err.Error(), tt.wantErr) {
				t.Errorf("error %q does not contain %q", err, tt.wantErr)
			}
		})
	}
}
