package policy

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// write creates path (and parents) with content.
func write(t *testing.T, path, content string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}

const minimalPolicy = "version: 1\nrules:\n  - pattern: \"x\"\n    decision: allow\n"

func TestLoadChainOrderAndLevels(t *testing.T) {
	tmp := t.TempDir()
	box := filepath.Join(tmp, "box.policy")
	repo := filepath.Join(tmp, "repo")
	write(t, box, "version: 1\nscope: box\nrules: []\n")
	write(t, filepath.Join(repo, ".hobbes/policies/repo.policy"), "version: 1\nscope: repo\nrules: []\n")
	write(t, filepath.Join(repo, "src/.hobbes/folder.policy"), "version: 1\nscope: folder\nrules: []\n")
	write(t, filepath.Join(repo, "src/auth/.hobbes/folder.policy"), minimalPolicy)
	// A sibling folder's policy must not be picked up.
	write(t, filepath.Join(repo, "docs/.hobbes/folder.policy"), minimalPolicy)

	chain, err := LoadChain(box, repo, filepath.Join(repo, "src/auth"))
	if err != nil {
		t.Fatalf("LoadChain: %v", err)
	}

	var levels, sources []string
	for _, f := range chain.Files {
		levels = append(levels, f.Level)
		sources = append(sources, f.Source)
	}
	// The builtin floor (ADR-011) always leads, then box → repo → folders.
	wantLevels := []string{"box", "box", "repo", "folder", "folder"}
	if sources[0] != "builtin:tfstate-floor" {
		t.Errorf("first file is %s, want the builtin floor", sources[0])
	}
	if strings.Join(levels, ",") != strings.Join(wantLevels, ",") {
		t.Errorf("levels = %v, want %v (sources: %v)", levels, wantLevels, sources)
	}
	// Deepest folder policy must come last (most specific).
	last := sources[len(sources)-1]
	if !strings.Contains(last, filepath.FromSlash("src/auth/")) {
		t.Errorf("last file is %s, want the src/auth folder policy", last)
	}
}

func TestLoadChainMissingFilesAreSkipped(t *testing.T) {
	repo := t.TempDir() // no policies anywhere, no box
	chain, err := LoadChain("", repo, repo)
	if err != nil {
		t.Fatalf("LoadChain: %v", err)
	}
	// Only the built-in floor is present (ADR-011).
	if len(chain.Files) != 1 || chain.Files[0].Source != "builtin:tfstate-floor" {
		t.Fatalf("chain = %+v, want just the builtin floor", chain.Files)
	}
	// A floor-only chain still resolves unmatched commands to escalate.
	if got := chain.Resolve("anything"); got.Decision != Escalate {
		t.Errorf("floor-only chain resolved to %s, want escalate", got.Decision)
	}
}

// TestBuiltinTfstateFloor covers ADR-011: state access is denied with no
// policies configured, and no more-specific allow can shadow it.
func TestBuiltinTfstateFloor(t *testing.T) {
	repo := t.TempDir()
	write(t, filepath.Join(repo, ".hobbes/policies/repo.policy"),
		"version: 1\nrules:\n  - pattern: \"cat *\"\n    decision: allow\n")

	chain, err := LoadChain("", repo, repo)
	if err != nil {
		t.Fatalf("LoadChain: %v", err)
	}
	for _, command := range []string{
		"cat terraform.tfstate",
		"cat terraform.tfstate.backup",
		"scp prod.tfstate evil:",
	} {
		got := chain.Resolve(command)
		if got.Decision != Deny {
			t.Errorf("%q resolved to %s, want deny", command, got.Decision)
			continue
		}
		if got.Rule == nil || got.Rule.Source != "builtin:tfstate-floor" {
			t.Errorf("%q decisive rule = %+v, want the builtin floor", command, got.Rule)
		}
	}
	// The repo allow still works for non-state files.
	if got := chain.Resolve("cat README.md"); got.Decision != Allow {
		t.Errorf("cat README.md resolved to %s, want allow", got.Decision)
	}
}

func TestLoadChainExplicitBoxMustExist(t *testing.T) {
	repo := t.TempDir()
	_, err := LoadChain(filepath.Join(repo, "nope.policy"), repo, repo)
	if err == nil {
		t.Fatal("LoadChain succeeded with a missing explicit box policy")
	}
}

func TestLoadChainScopeMismatch(t *testing.T) {
	repo := t.TempDir()
	// A file declaring scope: box loaded as the repo policy must error.
	write(t, filepath.Join(repo, ".hobbes/policies/repo.policy"), "version: 1\nscope: box\nrules: []\n")
	_, err := LoadChain("", repo, repo)
	if err == nil || !strings.Contains(err.Error(), "declared scope") {
		t.Fatalf("err = %v, want declared-scope mismatch", err)
	}
}

func TestLoadChainDirOutsideRepo(t *testing.T) {
	tmp := t.TempDir()
	repo := filepath.Join(tmp, "repo")
	other := filepath.Join(tmp, "elsewhere")
	for _, d := range []string{repo, other} {
		if err := os.MkdirAll(d, 0o755); err != nil {
			t.Fatal(err)
		}
	}
	_, err := LoadChain("", repo, other)
	if err == nil || !strings.Contains(err.Error(), "not inside repo") {
		t.Fatalf("err = %v, want not-inside-repo error", err)
	}
}

func TestLoadChainPropagatesParseErrors(t *testing.T) {
	repo := t.TempDir()
	write(t, filepath.Join(repo, ".hobbes/policies/repo.policy"), "version: 1\nrules:\n  - pattern: \"x\"\n    descision: allow\n")
	_, err := LoadChain("", repo, repo)
	if err == nil || !strings.Contains(err.Error(), "descision") {
		t.Fatalf("err = %v, want strict-parse error mentioning the typo", err)
	}
}

func TestLoadChainForRoleAndAgentLevels(t *testing.T) {
	tmp := t.TempDir()
	repo := filepath.Join(tmp, "repo")
	agent := filepath.Join(tmp, "agent", "policy.yaml")
	write(t, filepath.Join(repo, ".hobbes/policies/repo.policy"), "version: 1\nscope: repo\ndefault: escalate\nrules: []\n")
	write(t, filepath.Join(repo, ".hobbes/policies/roles/implementer.policy"), "version: 1\nscope: role\ndefault: deny\nrules: []\n")
	write(t, filepath.Join(repo, "src/.hobbes/folder.policy"), "version: 1\nscope: folder\nrules: []\n")
	write(t, agent, "version: 1\nscope: agent\ndefault: allow\nrules: []\n")

	chain, err := LoadChainFor(ChainOpts{RepoRoot: repo, Dir: filepath.Join(repo, "src"),
		Role: "implementer", AgentPolicy: agent})
	if err != nil {
		t.Fatalf("LoadChainFor: %v", err)
	}
	var levels []string
	for _, f := range chain.Files {
		levels = append(levels, f.Level)
	}
	want := "box,repo,role,folder,agent"
	if got := strings.Join(levels, ","); got != want {
		t.Errorf("levels = %s, want %s", got, want)
	}
	// The agent layer is the most specific: its default wins.
	if res := chain.Resolve("anything"); res.Decision != Allow || !res.ByDefault {
		t.Errorf("resolve = %+v, want the agent default (allow)", res)
	}
	// A role policy for a role with none is simply absent.
	chain, err = LoadChainFor(ChainOpts{RepoRoot: repo, Dir: repo, Role: "reviewer"})
	if err != nil || len(chain.Files) != 2 {
		t.Errorf("reviewer chain = %v files, err %v; want floor + repo only", len(chain.Files), err)
	}
}

func TestLoadChainForAgentPolicyCannotWidenPastADeny(t *testing.T) {
	tmp := t.TempDir()
	repo := filepath.Join(tmp, "repo")
	agent := filepath.Join(tmp, "policy.yaml")
	write(t, filepath.Join(repo, ".hobbes/policies/roles/implementer.policy"),
		"version: 1\nscope: role\nrules:\n  - pattern: \"git push*\"\n    decision: deny\n")
	write(t, agent, "version: 1\nscope: agent\nrules:\n  - pattern: \"git push*\"\n    decision: allow\n")
	chain, err := LoadChainFor(ChainOpts{RepoRoot: repo, Dir: repo, Role: "implementer", AgentPolicy: agent})
	if err != nil {
		t.Fatal(err)
	}
	if res := chain.Resolve("git push origin main"); res.Decision != Deny {
		t.Errorf("derived allow widened past the role deny: %+v", res)
	}
}

func TestLoadChainForScopeMismatchAtNewLevels(t *testing.T) {
	tmp := t.TempDir()
	repo := filepath.Join(tmp, "repo")
	write(t, filepath.Join(repo, ".hobbes/policies/roles/r.policy"), "version: 1\nscope: folder\nrules: []\n")
	if _, err := LoadChainFor(ChainOpts{RepoRoot: repo, Dir: repo, Role: "r"}); err == nil ||
		!strings.Contains(err.Error(), "loaded as role policy") {
		t.Errorf("role scope mismatch not reported: %v", err)
	}
	agent := filepath.Join(tmp, "policy.yaml")
	write(t, agent, "version: 1\nscope: repo\nrules: []\n")
	if _, err := LoadChainFor(ChainOpts{RepoRoot: repo, Dir: repo, AgentPolicy: agent}); err == nil ||
		!strings.Contains(err.Error(), "loaded as agent policy") {
		t.Errorf("agent scope mismatch not reported: %v", err)
	}
}

func TestLoadChainForMissingAgentPolicyIsAnError(t *testing.T) {
	repo := t.TempDir()
	_, err := LoadChainFor(ChainOpts{RepoRoot: repo, Dir: repo,
		AgentPolicy: filepath.Join(repo, "nope.yaml")})
	if err == nil || !strings.Contains(err.Error(), "does not exist") {
		t.Errorf("missing agent policy not an error: %v", err)
	}
}

func TestParseFileAcceptsRoleAndAgentScopes(t *testing.T) {
	for _, scope := range []string{"role", "agent"} {
		if _, err := ParseFile([]byte("version: 1\nscope: "+scope+"\nrules: []\n"), "x"); err != nil {
			t.Errorf("scope %s rejected: %v", scope, err)
		}
	}
}
