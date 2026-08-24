package policy

import "testing"

// mkFile builds an in-memory policy file for chain tests. Rules come as
// (pattern, decision, pattern, decision, ...) pairs.
func mkFile(level, source string, def Decision, rules ...string) *File {
	f := &File{Version: 1, Default: def, Source: source, Level: level}
	for i := 0; i < len(rules); i += 2 {
		f.Rules = append(f.Rules, Rule{Pattern: rules[i], Decision: Decision(rules[i+1])})
	}
	return f
}

// TestResolve is the M0 battery: shadowing, deny-wins, folder-over-repo-
// over-box precedence, the escalate tier, and defaults, per ADR-002.
func TestResolve(t *testing.T) {
	tests := []struct {
		name       string
		chain      []*File
		command    string
		want       Decision
		wantScope  string // decisive rule's scope; "" = resolved by default
		wantSource string // decisive rule's source, or default_source
	}{
		{
			name: "deny-wins: box deny beats folder allow (the floor)",
			chain: []*File{
				mkFile("box", "box.policy", "", "git push --force*", "deny"),
				mkFile("folder", "src/.hobbes/folder.policy", "", "git push*", "allow"),
			},
			command:    "git push --force origin main",
			want:       Deny,
			wantScope:  "box",
			wantSource: "box.policy",
		},
		{
			name: "deny-wins: repo deny beats deeper folder allow",
			chain: []*File{
				mkFile("repo", "repo.policy", "", "*secrets*", "deny"),
				mkFile("folder", "src/.hobbes/folder.policy", "", "cat *", "allow"),
			},
			command:    "cat config/secrets.yaml",
			want:       Deny,
			wantScope:  "repo",
			wantSource: "repo.policy",
		},
		{
			name: "deny reported from most specific denying scope",
			chain: []*File{
				mkFile("box", "box.policy", "", "*tfstate*", "deny"),
				mkFile("repo", "repo.policy", "", "*tfstate*", "deny"),
			},
			command:    "cat terraform.tfstate",
			want:       Deny,
			wantScope:  "repo",
			wantSource: "repo.policy",
		},
		{
			name: "shadowing: folder allow shadows repo escalate",
			chain: []*File{
				mkFile("repo", "repo.policy", "", "terraform apply*", "escalate"),
				mkFile("folder", "infra/.hobbes/folder.policy", "", "terraform apply*", "allow"),
			},
			command:    "terraform apply -auto-approve",
			want:       Allow,
			wantScope:  "folder",
			wantSource: "infra/.hobbes/folder.policy",
		},
		{
			name: "shadowing: repo allow shadows box escalate",
			chain: []*File{
				mkFile("box", "box.policy", "", "go test*", "escalate"),
				mkFile("repo", "repo.policy", "", "go test*", "allow"),
			},
			command:    "go test ./...",
			want:       Allow,
			wantScope:  "repo",
			wantSource: "repo.policy",
		},
		{
			name: "escalate tier: folder escalate shadows repo allow",
			chain: []*File{
				mkFile("repo", "repo.policy", "", "rm *", "allow"),
				mkFile("folder", "src/auth/.hobbes/folder.policy", "", "rm *", "escalate"),
			},
			command:    "rm src/auth/token.py",
			want:       Escalate,
			wantScope:  "folder",
			wantSource: "src/auth/.hobbes/folder.policy",
		},
		{
			name: "escalate tier: plain escalate rule escalates",
			chain: []*File{
				mkFile("repo", "repo.policy", "", "git push*", "escalate"),
			},
			command:    "git push origin main",
			want:       Escalate,
			wantScope:  "repo",
			wantSource: "repo.policy",
		},
		{
			name: "within one scope, escalate beats allow",
			chain: []*File{
				mkFile("repo", "repo.policy", "", "git *", "allow", "git push*", "escalate"),
			},
			command:    "git push origin main",
			want:       Escalate,
			wantScope:  "repo",
			wantSource: "repo.policy",
		},
		{
			name: "deeper folder is more specific than shallower folder",
			chain: []*File{
				mkFile("folder", "src/.hobbes/folder.policy", "", "pytest*", "escalate"),
				mkFile("folder", "src/auth/.hobbes/folder.policy", "", "pytest*", "allow"),
			},
			command:    "pytest tests/",
			want:       Allow,
			wantScope:  "folder",
			wantSource: "src/auth/.hobbes/folder.policy",
		},
		{
			name: "specificity is by scope, not pattern length",
			chain: []*File{
				mkFile("box", "box.policy", "", "git push --force origin main", "escalate"),
				mkFile("repo", "repo.policy", "", "git *", "allow"),
			},
			command:    "git push --force origin main",
			want:       Allow,
			wantScope:  "repo",
			wantSource: "repo.policy",
		},
		{
			name: "no match: most specific file default wins",
			chain: []*File{
				mkFile("repo", "repo.policy", Escalate, "git *", "allow"),
				mkFile("folder", "docs/.hobbes/folder.policy", Allow),
			},
			command:    "make html",
			want:       Allow,
			wantSource: "docs/.hobbes/folder.policy",
		},
		{
			name: "no match, no defaults: engine fallback is escalate",
			chain: []*File{
				mkFile("box", "box.policy", "", "git *", "allow"),
			},
			command: "curl https://example.com",
			want:    Escalate,
		},
		{
			name:    "empty chain: engine fallback is escalate",
			chain:   nil,
			command: "anything",
			want:    Escalate,
		},
		{
			name: "whitespace cannot dodge a pattern",
			chain: []*File{
				mkFile("box", "box.policy", "", "git push --force*", "deny"),
			},
			command:    "git   push \t --force origin main",
			want:       Deny,
			wantScope:  "box",
			wantSource: "box.policy",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			c := &Chain{Files: tt.chain}
			got := c.Resolve(tt.command)

			if got.Decision != tt.want {
				t.Fatalf("decision = %q, want %q (result: %+v)", got.Decision, tt.want, got)
			}
			if tt.wantScope != "" {
				if got.ByDefault {
					t.Fatalf("resolved by default, want rule from scope %q", tt.wantScope)
				}
				if got.Rule == nil {
					t.Fatal("decisive rule is nil")
				}
				if got.Rule.Scope != tt.wantScope || got.Rule.Source != tt.wantSource {
					t.Errorf("decisive rule from %s (%s), want %s (%s)",
						got.Rule.Scope, got.Rule.Source, tt.wantScope, tt.wantSource)
				}
			} else {
				if !got.ByDefault {
					t.Fatalf("resolved by rule %+v, want default", got.Rule)
				}
				if got.Rule != nil {
					t.Errorf("default resolution carries a rule: %+v", got.Rule)
				}
				if got.DefaultSource != tt.wantSource {
					t.Errorf("default_source = %q, want %q", got.DefaultSource, tt.wantSource)
				}
			}
		})
	}
}

// TestResolveMatchList checks the transparency contract: every matching rule
// is reported, least specific first, and the command is normalized.
func TestResolveMatchList(t *testing.T) {
	c := &Chain{Files: []*File{
		mkFile("box", "box.policy", "", "git push*", "escalate"),
		mkFile("repo", "repo.policy", "", "git *", "allow"),
		mkFile("folder", "src/.hobbes/folder.policy", "", "make *", "allow"),
	}}
	got := c.Resolve("git   push origin")

	if got.Command != "git push origin" {
		t.Errorf("command not normalized: %q", got.Command)
	}
	if len(got.Matches) != 2 {
		t.Fatalf("got %d matches, want 2: %+v", len(got.Matches), got.Matches)
	}
	if got.Matches[0].Scope != "box" || got.Matches[1].Scope != "repo" {
		t.Errorf("matches out of order: %+v", got.Matches)
	}
	// Repo allow shadows box escalate.
	if got.Decision != Allow || got.Rule.Scope != "repo" {
		t.Errorf("decision = %s from %s, want allow from repo", got.Decision, got.Rule.Scope)
	}
}
