package clang

import (
	"os"
	"path/filepath"
	"testing"
)

func writeFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}

// TestDatabaseSource covers ADR-109's order: a carried database that
// rebases wins; one that does not falls through to CMake, then Make,
// then nothing.
func TestDatabaseSource(t *testing.T) {
	t.Run("carried and usable", func(t *testing.T) {
		repo := t.TempDir()
		writeFile(t, filepath.Join(repo, "compile_commands.json"), `[{"directory": "src", "file": "a.c", "arguments": ["clang", "a.c"]}]`)
		writeFile(t, filepath.Join(repo, "CMakeLists.txt"), "") // present but the carried db wins
		source, rel := DatabaseSource(repo, "")
		if source != "repo" || rel != "compile_commands.json" {
			t.Errorf("got (%q, %q), want (repo, compile_commands.json)", source, rel)
		}
	})

	t.Run("carried in build/", func(t *testing.T) {
		repo := t.TempDir()
		writeFile(t, filepath.Join(repo, "build", "compile_commands.json"), `[{"directory": "src", "arguments": ["clang"]}]`)
		source, rel := DatabaseSource(repo, "")
		if source != "repo" || rel != filepath.Join("build", "compile_commands.json") {
			t.Errorf("got (%q, %q)", source, rel)
		}
	})

	t.Run("carried and not rebasing", func(t *testing.T) {
		repo := t.TempDir()
		writeFile(t, filepath.Join(repo, "compile_commands.json"), `[{"directory": "/somewhere/else", "arguments": ["clang"]}]`)
		writeFile(t, filepath.Join(repo, "CMakeLists.txt"), "")
		source, _ := DatabaseSource(repo, "")
		if source != "cmake" {
			t.Errorf("an unusable carried db must fall through to cmake, got %q", source)
		}
	})

	t.Run("cmake", func(t *testing.T) {
		repo := t.TempDir()
		writeFile(t, filepath.Join(repo, "CMakeLists.txt"), "")
		source, _ := DatabaseSource(repo, "")
		if source != "cmake" {
			t.Errorf("got %q, want cmake", source)
		}
	})

	t.Run("make", func(t *testing.T) {
		repo := t.TempDir()
		writeFile(t, filepath.Join(repo, "Makefile"), "")
		source, _ := DatabaseSource(repo, "")
		if source != "make" {
			t.Errorf("got %q, want make", source)
		}
	})

	t.Run("nothing", func(t *testing.T) {
		repo := t.TempDir()
		source, _ := DatabaseSource(repo, "")
		if source != "" {
			t.Errorf("got %q, want none", source)
		}
	})

	t.Run("module subdirectory", func(t *testing.T) {
		repo := t.TempDir()
		writeFile(t, filepath.Join(repo, "sub", "Makefile"), "")
		source, _ := DatabaseSource(repo, "sub")
		if source != "make" {
			t.Errorf("got %q, want make under the module root", source)
		}
	})
}

// TestFilterArgs covers the argv filter: argv[0] and the output and
// dependency flags are dropped, everything else survives.
func TestFilterArgs(t *testing.T) {
	argv := []string{"cc", "-Wall", "-c", "a.c", "-o", "a.o", "-DFOO=1", "-oa.o2", "-MD", "-MF", "a.d", "-MT", "a.o", "-MQ", "a.o", "-MMD", "-MP", "-Iinclude"}
	got := FilterArgs(argv)
	want := []string{"-Wall", "a.c", "-DFOO=1", "-Iinclude"}
	if len(got) != len(want) {
		t.Fatalf("got %v, want %v", got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("got %v, want %v", got, want)
			break
		}
	}
}

// TestCompdbEntryArgv covers both entry shapes: a pre-split Arguments
// list, and a shell-quoted Command string (quotes and backslashes).
func TestCompdbEntryArgv(t *testing.T) {
	e1 := CompdbEntry{Arguments: []string{"clang", "-c", "a.c"}}
	if got := e1.Argv(); len(got) != 3 || got[2] != "a.c" {
		t.Errorf("Arguments form: %v", got)
	}

	e2 := CompdbEntry{Command: `clang -DMSG="hello world" -I'my inc' a.c\ b.c`}
	got := e2.Argv()
	want := []string{"clang", "-DMSG=hello world", "-Imy inc", "a.c b.c"}
	if len(got) != len(want) {
		t.Fatalf("Command form: got %v, want %v", got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("Command form: got %v, want %v", got, want)
			break
		}
	}
}
