package contain

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestProfilesStateWhatExecutes(t *testing.T) {
	if !Profiles["py-trace"].Executes || !Profiles["rust-mir"].Executes {
		t.Fatal("O6 and O7 execute repo code")
	}
	if Profiles["fetch-rust"].Executes || Profiles["fetch-rust"].Network == "none" {
		t.Fatal("the fetch step executes nothing and is the only networked one")
	}
	for _, s := range []string{"py-trace", "rust-mir"} {
		if Profiles[s].Network != "none" {
			t.Errorf("%s must run without a network", s)
		}
	}
}

func TestPlanIsTheVerifierShape(t *testing.T) {
	tmp := t.TempDir()
	tree := filepath.Join(tmp, "repo")
	out := filepath.Join(tmp, "cell")
	tool := filepath.Join(tmp, "tools", "nightly")
	os.MkdirAll(tree, 0o755)
	os.MkdirAll(tool, 0o755)
	t.Setenv(cacheEnv, filepath.Join(tmp, "cache"))
	p, err := New("rust-mir", []string{"cargo", "check"}, tree, tree, []string{out}, []string{tool, filepath.Join(tree, "inside"), "/usr/lib"}, []string{"X=1"})
	if err != nil {
		t.Fatal(err)
	}
	m := p.Mounts()
	if m[0] != tree+":"+tree+":O" {
		t.Fatalf("the tree is an overlay at its host path, got %s", m[0])
	}
	want := []string{filepath.Join(tmp, "cache") + ":" + filepath.Join(tmp, "cache") + ":rw", out + ":" + out + ":rw", tool + ":" + tool + ":ro"}
	if strings.Join(m[1:], " ") != strings.Join(want, " ") {
		t.Fatalf("mounts %v, want %v", m[1:], want)
	}
	args := strings.Join(p.PodmanArgs(), " ")
	for _, s := range []string{"--network none", "--pull=never", "label=disable", "X=1", "CARGO_HOME=" + filepath.Join(tmp, "cache", "cargo"), DefaultImage + " cargo check"} {
		if !strings.Contains(args, s) {
			t.Errorf("argv lacks %q: %s", s, args)
		}
	}
}

func TestFetchGetsTheDefaultNetwork(t *testing.T) {
	p, _ := New("fetch-rust", []string{"cargo", "fetch"}, t.TempDir(), "", nil, nil, nil)
	if strings.Contains(strings.Join(p.PodmanArgs(), " "), "--network") {
		t.Fatal("a fetch step takes podman's default network")
	}
}

func TestInterpreterMountsFollowEveryHopUnresolved(t *testing.T) {
	tmp := t.TempDir()
	real := filepath.Join(tmp, "pythons", "cpython-3.12.13")
	os.MkdirAll(filepath.Join(real, "bin"), 0o755)
	os.WriteFile(filepath.Join(real, "bin", "python3.12"), nil, 0o755)
	alias := filepath.Join(tmp, "pythons", "cpython-3.12")
	os.Symlink(real, alias)
	base := filepath.Join(tmp, "base", ".venv")
	os.MkdirAll(filepath.Join(base, "bin"), 0o755)
	os.Symlink(filepath.Join(alias, "bin", "python3.12"), filepath.Join(base, "bin", "python"))
	venv := filepath.Join(tmp, "repo", ".venv")
	os.MkdirAll(filepath.Join(venv, "bin"), 0o755)
	os.Symlink(filepath.Join(base, "bin", "python"), filepath.Join(venv, "bin", "python"))
	got := InterpreterMounts(filepath.Join(venv, "bin", "python"))
	if strings.Join(got, " ") != base+" "+alias {
		t.Fatalf("hops %v, want [%s %s] (unresolved alias, not %s)", got, base, alias, real)
	}
	if len(InterpreterMounts("/usr/bin/python3")) != 0 {
		t.Fatal("a system python is the image's")
	}
}

func TestRefusalIsATypeNotAString(t *testing.T) {
	err := error(&Refusal{Step: "rust-mir", Reason: "podman is not installed"})
	if !IsRefusal(err) || !strings.Contains(err.Error(), "never executes on the host") {
		t.Fatal(err)
	}
}
