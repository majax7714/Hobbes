package clang

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"testing"

	"github.com/majax7714/Hobbes/bench/oracle/internal/contain"
	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

// haveTool reports whether name is on PATH, so these tests skip
// gracefully wherever the toolchain (clang, cmake, bear) is missing —
// hermetic in the sense the pipeline venv tests are: they run for real
// wherever the tool is installed, and skip rather than fail otherwise.
// None of this needs podman or the sandbox image; RunUnits itself knows
// nothing about containment.
func haveTool(name string) bool {
	_, err := exec.LookPath(name)
	return err == nil
}

func writeCompdb(t *testing.T, path string, entries []CompdbEntry) {
	t.Helper()
	raw, err := json.Marshal(entries)
	if err != nil {
		t.Fatal(err)
	}
	writeFile(t, path, string(raw))
}

// readRoots splits a written roots.txt into its two lines.
func readRoots(t *testing.T, shardsDir string) (rootsLine, versionLine string) {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join(shardsDir, "roots.txt"))
	if err != nil {
		t.Fatal(err)
	}
	lines := splitLines(string(raw))
	if len(lines) < 1 {
		t.Fatalf("roots.txt is empty")
	}
	if len(lines) > 1 {
		return lines[0], lines[1]
	}
	return lines[0], ""
}

func splitLines(s string) []string {
	var out []string
	cur := ""
	for _, r := range s {
		if r == '\n' {
			out = append(out, cur)
			cur = ""
			continue
		}
		cur += string(r)
	}
	if cur != "" {
		out = append(out, cur)
	}
	return out
}

// TestRunUnitsWithExplicitCompdb covers --compdb: it names a database
// directly and skips ADR-109's search entirely (source "given").
func TestRunUnitsWithExplicitCompdb(t *testing.T) {
	if !haveTool("clang") {
		t.Skip("clang not on PATH")
	}
	repo := t.TempDir()
	writeFile(t, filepath.Join(repo, "a.c"), "int f(void) { return 1; }\nint g(void) { return f(); }\n")
	compdb := filepath.Join(repo, "custom-compdb.json")
	writeCompdb(t, compdb, []CompdbEntry{
		{Directory: repo, File: "a.c", Arguments: []string{"clang", "-c", "a.c", "-o", "a.o"}},
	})
	out := t.TempDir()
	if err := RunUnits(Options{Repo: repo, Module: "", Compdb: compdb, Out: out}); err != nil {
		t.Fatalf("RunUnits: %v", err)
	}
	shardsDir := filepath.Join(out, "clang-shards")
	rootsLine, versionLine := readRoots(t, shardsDir)
	if rootsLine != "compile database: given (1 units)" {
		t.Errorf("roots line: %q", rootsLine)
	}
	if versionLine == "" {
		t.Errorf("want clang's version line, got empty")
	}
	shards, err := LoadShards(shardsDir)
	if err != nil {
		t.Fatal(err)
	}
	if len(shards) != 1 || shards[0].Failed {
		t.Fatalf("shards: %+v", shards)
	}
	out2 := Merge(shards, "")
	if len(out2.Sites) != 1 || out2.Sites[0].Mode != "static" {
		t.Errorf("expected one static call to f: %+v", out2.Sites)
	}
}

// TestRunUnitsFailedUnitIsKept covers the failed-unit rule: a non-zero
// clang exit still keeps the shard the dump read, marked Failed with
// stderr's tail.
func TestRunUnitsFailedUnitIsKept(t *testing.T) {
	if !haveTool("clang") {
		t.Skip("clang not on PATH")
	}
	repo := t.TempDir()
	writeFile(t, filepath.Join(repo, "bad.c"), "int f(void) { return undeclared_name; }\n")
	compdb := filepath.Join(repo, "compdb.json")
	writeCompdb(t, compdb, []CompdbEntry{
		{Directory: repo, File: "bad.c", Arguments: []string{"clang", "-c", "bad.c", "-o", "bad.o"}},
	})
	out := t.TempDir()
	if err := RunUnits(Options{Repo: repo, Compdb: compdb, Out: out}); err != nil {
		t.Fatalf("RunUnits: %v", err)
	}
	shards, err := LoadShards(filepath.Join(out, "clang-shards"))
	if err != nil {
		t.Fatal(err)
	}
	if len(shards) != 1 {
		t.Fatalf("want 1 shard, got %d", len(shards))
	}
	if !shards[0].Failed || shards[0].Stderr == "" {
		t.Errorf("a unit clang rejects must be kept, Failed with its stderr: %+v", shards[0])
	}
}

// TestRunUnitsDerivesFromCMake covers ADR-109's second source: no
// carried compile_commands.json, so a CMakeLists.txt at the root drives
// CMake's own export.
func TestRunUnitsDerivesFromCMake(t *testing.T) {
	if !haveTool("clang") || !haveTool("cmake") {
		t.Skip("clang or cmake not on PATH")
	}
	repo := t.TempDir()
	writeFile(t, filepath.Join(repo, "CMakeLists.txt"), "cmake_minimum_required(VERSION 3.10)\nproject(probe C)\nadd_executable(probe main.c)\n")
	writeFile(t, filepath.Join(repo, "main.c"), "int helper(void) { return 1; }\nint main(void) { return helper(); }\n")
	out := t.TempDir()
	if err := RunUnits(Options{Repo: repo, Out: out}); err != nil {
		t.Fatalf("RunUnits: %v", err)
	}
	shardsDir := filepath.Join(out, "clang-shards")
	rootsLine, _ := readRoots(t, shardsDir)
	if got, want := rootsLine, "compile database: cmake (1 units)"; got != want {
		t.Errorf("roots line: %q, want %q", got, want)
	}
	shards, err := LoadShards(shardsDir)
	if err != nil {
		t.Fatal(err)
	}
	merged := Merge(shards, "")
	if !equalStrings(merged.Files, []string{"main.c"}) {
		t.Errorf("files: %v", merged.Files)
	}
}

// TestRunUnitsDerivesFromMake covers ADR-109's third source: no CMake,
// so a Makefile at the root drives bear over `make -k`.
func TestRunUnitsDerivesFromMake(t *testing.T) {
	if !haveTool("clang") || !haveTool("bear") || !haveTool("make") {
		t.Skip("clang, bear or make not on PATH")
	}
	repo := t.TempDir()
	writeFile(t, filepath.Join(repo, "main.c"), "int helper(void) { return 1; }\nint main(void) { return helper(); }\n")
	writeFile(t, filepath.Join(repo, "Makefile"), "probe.o: main.c\n\tclang -c -o probe.o main.c\n")
	out := t.TempDir()
	if err := RunUnits(Options{Repo: repo, Out: out}); err != nil {
		t.Fatalf("RunUnits: %v", err)
	}
	shardsDir := filepath.Join(out, "clang-shards")
	rootsLine, _ := readRoots(t, shardsDir)
	if got, want := rootsLine, "compile database: make (1 units)"; got != want {
		t.Errorf("roots line: %q, want %q", got, want)
	}
	shards, err := LoadShards(shardsDir)
	if err != nil {
		t.Fatal(err)
	}
	merged := Merge(shards, "")
	if !equalStrings(merged.Files, []string{"main.c"}) {
		t.Errorf("files: %v", merged.Files)
	}
}

// TestOracleCClangEndToEnd builds the real `oracle` binary (static, as
// run-cell.sh does) and runs its `c-clang` command against the cclang
// fixture — bear over `make -k` derives the database, real clang runs
// per unit, all inside the sandbox image — asserting unit A's fixture
// truth (oracle-grading.md P17) holds end to end. Skips without
// containment, as it will in this session; the developer runs it on the
// host, image built (sandbox/README.md).
func TestOracleCClangEndToEnd(t *testing.T) {
	if why := contain.UnavailableReason(); why != "" && !contain.Uncontained() {
		t.Skip("containment unavailable: " + why)
	}
	// The binary is built inside the cell dir, as run-cell.sh builds it:
	// the dir is then both the rw cell mount and the binary's own ro
	// mount, the layout the first real cell refused as a duplicate mount
	// destination (ADR-110) and a test binary built elsewhere never hit.
	outDir := t.TempDir()
	bin := filepath.Join(outDir, "oracle")
	build := exec.Command("go", "build", "-o", bin, "../../cmd/oracle")
	build.Env = append(os.Environ(), "CGO_ENABLED=0")
	build.Dir = "."
	if out, err := build.CombinedOutput(); err != nil {
		t.Fatalf("go build oracle: %v\n%s", err, out)
	}
	repo, err := filepath.Abs("../../testdata/cclang")
	if err != nil {
		t.Fatal(err)
	}
	oracleJSON := filepath.Join(outDir, "oracle.json")
	run := exec.Command(bin, "c-clang", "--repo", repo, "--module", "", "--out-dir", outDir, "--out", oracleJSON)
	if out, err := run.CombinedOutput(); err != nil {
		t.Fatalf("oracle c-clang: %v\n%s", err, out)
	}
	raw, err := os.ReadFile(oracleJSON)
	if err != nil {
		t.Fatal(err)
	}
	var out edges.OracleExport
	if err := json.Unmarshal(raw, &out); err != nil {
		t.Fatal(err)
	}
	if got, want := out.Files, []string{"api.h", "lib.c", "main.c", "pick.h", "tool.c"}; !equalStrings(got, want) {
		t.Errorf("files: %v, want %v (orphan.c must stay not-loaded)", got, want)
	}
	wantCoverage := map[string]int{
		"units": 4, "units_failed": 0,
		"sites_static": 14, "sites_macro": 1, "sites_dynamic": 3,
		"sites_external": 1, "sites_link_ambiguous": 1, "sites_undefined": 1, "sites_tu_split": 1,
	}
	for k, v := range wantCoverage {
		if out.Coverage[k] != v {
			t.Errorf("coverage[%s] = %d, want %d (full: %v)", k, out.Coverage[k], v, out.Coverage)
		}
	}
	if len(out.Sites) != 22 {
		t.Errorf("total distinct sites: %d, want 22", len(out.Sites))
	}
	if out.Containment != "contained" {
		t.Errorf("containment: %q, want contained", out.Containment)
	}
}

// TestRunUnitsNoDatabase covers ADR-109's last source: nothing to
// derive from is an error naming why.
func TestRunUnitsNoDatabase(t *testing.T) {
	repo := t.TempDir()
	out := t.TempDir()
	err := RunUnits(Options{Repo: repo, Out: out})
	if err == nil {
		t.Fatal("want an error when no compile database can be derived")
	}
}
