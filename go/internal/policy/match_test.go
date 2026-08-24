package policy

import "testing"

func TestMatchGlob(t *testing.T) {
	tests := []struct {
		name    string
		pattern string
		s       string
		want    bool
	}{
		{"exact match", "git status", "git status", true},
		{"anchored: no implicit suffix", "git push", "git push --force", false},
		{"anchored: no implicit prefix", "push*", "git push", false},
		{"trailing star", "git push*", "git push --force origin main", true},
		{"trailing star matches empty", "git push*", "git push", true},
		{"star crosses spaces and slashes", "git add *", "git add src/auth/token.py tests/", true},
		{"inner star", "terraform * -auto-approve", "terraform apply -auto-approve", true},
		{"multiple stars", "*--force*", "git push --force-with-lease origin", true},
		{"star alone", "*", "anything at all", true},
		{"star alone matches empty", "*", "", true},
		{"question mark", "git ????", "git push", true},
		{"question mark needs a rune", "git push?", "git push", false},
		{"question mark is rune-wise", "echo ?", "echo é", true},
		{"substring containment", "*.tfstate*", "cat terraform.tfstate.backup", true},
		{"no match", "rm -rf*", "git status", false},
		{"empty pattern vs empty string", "", "", true},
		{"empty pattern vs non-empty", "", "x", false},
		{"backtracking star", "a*bc", "axbxbc", true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := matchGlob(tt.pattern, tt.s); got != tt.want {
				t.Errorf("matchGlob(%q, %q) = %v, want %v", tt.pattern, tt.s, got, tt.want)
			}
		})
	}
}

func TestNormalize(t *testing.T) {
	tests := []struct {
		in, want string
	}{
		{"git push", "git push"},
		{"  git   push  --force  ", "git push --force"},
		{"git\tpush\n--force", "git push --force"},
		{"", ""},
	}
	for _, tt := range tests {
		if got := normalize(tt.in); got != tt.want {
			t.Errorf("normalize(%q) = %q, want %q", tt.in, got, tt.want)
		}
	}
}
