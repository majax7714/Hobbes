package clang

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/majax7714/Hobbes/bench/oracle/internal/contain"
	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

// Options is one C cell: a build root inside the repo (ADR-109's
// definition), mirroring rustmir's and javac's Options shape.
type Options struct {
	Repo   string // repo root
	Module string // repo-relative build root ("" or "." for the repo root)
	Compdb string // a compile database to use directly; skips ADR-109's search
	Clang  string // clang command name/path (default "clang")
	Out    string // cell directory: clang-shards/ and, when derived, the build's own scratch files
}

// clangArgs is the fixed prefix every unit's clang run carries: a
// syntax-only front-end pass that dumps the AST as JSON, quiet about
// diagnostics the entry's own flags might otherwise color or warn on.
var clangArgs = []string{"-fsyntax-only", "-Xclang", "-ast-dump=json", "-fno-color-diagnostics", "-Wno-everything"}

// Run runs one C cell as ADR-110 decision 3's single contained step: the
// oracle binary itself, mounted read-only at its own host path, invoked
// as the internal `c-clang-units` subcommand inside the sandbox image
// (deriving a database and every clang run share the step, since a
// build's generated headers exist only in its container's overlay).
// LoadShards and Merge then run on the host.
func Run(o Options) (*edges.OracleExport, error) {
	repo, err := filepath.Abs(o.Repo)
	if err != nil {
		return nil, err
	}
	module := o.Module
	if module == "." {
		module = ""
	}
	dir := filepath.Join(repo, module)
	outAbs, err := filepath.Abs(o.Out)
	if err != nil {
		return nil, err
	}
	exe, err := os.Executable()
	if err != nil {
		return nil, fmt.Errorf("clang: cannot find the oracle binary's own path: %w", err)
	}
	if resolved, err := filepath.EvalSymlinks(exe); err == nil {
		exe = resolved
	}
	cmd := []string{exe, "c-clang-units", "--repo", repo, "--module", module, "--out-dir", outAbs}
	if o.Compdb != "" {
		cmd = append(cmd, "--compdb", o.Compdb)
	}
	if o.Clang != "" {
		cmd = append(cmd, "--clang", o.Clang)
	}
	plan, err := contain.New("c-clang", cmd, dir, repo, []string{outAbs}, []string{filepath.Dir(exe)}, nil)
	if err != nil {
		return nil, err
	}
	outcome, err := contain.Run(plan)
	if err != nil {
		return nil, fmt.Errorf("clang: %s: %w", strings.Join(cmd, " "), err)
	}

	shardsDir := filepath.Join(outAbs, "clang-shards")
	shards, err := LoadShards(shardsDir)
	if err != nil {
		return nil, err
	}
	merged := Merge(shards, module)
	raw, err := os.ReadFile(filepath.Join(shardsDir, "roots.txt"))
	if err != nil {
		return nil, err
	}
	lines := strings.SplitN(strings.TrimRight(string(raw), "\n"), "\n", 2)
	merged.Roots = []string{lines[0]}
	version := ""
	if len(lines) > 1 {
		version = lines[1]
	}
	merged.Oracle = version + " -ast-dump=json"
	merged.Containment = outcome.Containment()
	return merged, nil
}

// RunUnits is the internal subcommand (`oracle c-clang-units`) ADR-110
// runs inside the sandbox image: derive the module's compile database
// (ADR-109's order — a carried compile_commands.json, else CMake's
// export, else bear over `make -k` — or --compdb directly), run clang
// over every entry, and write one shard per unit under
// <out>/clang-shards, plus roots.txt naming the database's source and
// unit count and clang's own version line. Deriving via CMake or bear
// runs the repo's own build logic, so this and every clang run happen
// here, in one step, offline.
func RunUnits(o Options) error {
	repo, err := filepath.Abs(o.Repo)
	if err != nil {
		return err
	}
	module := o.Module
	if module == "." {
		module = ""
	}
	root := filepath.Join(repo, module)
	shardsDir := filepath.Join(o.Out, "clang-shards")
	os.RemoveAll(shardsDir)
	if err := os.MkdirAll(shardsDir, 0o755); err != nil {
		return err
	}

	entries, source, err := resolveEntries(o, root)
	if err != nil {
		return fmt.Errorf("clang: %w", err)
	}

	clangBin := o.Clang
	if clangBin == "" {
		clangBin = "clang"
	}
	rootsLine := fmt.Sprintf("compile database: %s (%d units)", source, len(entries))
	versionLine := clangVersionFirst(clangBin)
	roots := rootsLine + "\n" + versionLine + "\n"
	if err := os.WriteFile(filepath.Join(shardsDir, "roots.txt"), []byte(roots), 0o644); err != nil {
		return err
	}

	for i, e := range entries {
		shard := runUnit(clangBin, e, repo)
		if err := shard.Save(filepath.Join(shardsDir, fmt.Sprintf("%d.json", i))); err != nil {
			return err
		}
	}
	return nil
}

// resolveEntries picks the compile database (ADR-109's order, or
// --compdb) and loads its entries, naming the source for the roots
// line.
func resolveEntries(o Options, root string) (entries []CompdbEntry, source string, err error) {
	if o.Compdb != "" {
		entries, err = LoadCompdb(o.Compdb)
		return entries, "given", err
	}
	repo, err := filepath.Abs(o.Repo)
	if err != nil {
		return nil, "", err
	}
	module := o.Module
	if module == "." {
		module = ""
	}
	var rel string
	source, rel = DatabaseSource(repo, module)
	switch source {
	case "repo":
		entries, err = LoadCompdb(filepath.Join(root, rel))
	case "cmake":
		var compdb string
		if compdb, err = deriveCMake(root, o.Out); err == nil {
			entries, err = LoadCompdb(compdb)
		}
	case "make":
		var compdb string
		if compdb, err = deriveMake(root, o.Out); err == nil {
			entries, err = LoadCompdb(compdb)
		}
	default:
		err = fmt.Errorf("no compile database can be derived for %s (no compile_commands.json, CMakeLists.txt or Makefile)", root)
	}
	return entries, source, err
}

// deriveCMake runs CMake's configure step to export a compile database
// under out/cmake-build, the way the ingest derives it (ADR-109).
func deriveCMake(root, out string) (string, error) {
	buildDir := filepath.Join(out, "cmake-build")
	cmd := exec.Command("cmake", "-S", root, "-B", buildDir, "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON")
	output, _ := cmd.CombinedOutput()
	compdb := filepath.Join(buildDir, "compile_commands.json")
	if !hasEntries(compdb) {
		return "", fmt.Errorf("cmake produced no compile database for %s: %s", root, lastBytes(output, 600))
	}
	return compdb, nil
}

// deriveMake runs `make -k` under bear to record a compile database at
// out/compile_commands.json, the way the ingest derives it (ADR-109).
// make's own exit status decides nothing — bear -k keeps going past a
// failing target and records every compile it saw — so only the
// database having entries is checked.
func deriveMake(root, out string) (string, error) {
	compdb := filepath.Join(out, "compile_commands.json")
	cmd := exec.Command("bear", "--output", compdb, "--", "make", "-k")
	cmd.Dir = root
	output, _ := cmd.CombinedOutput()
	if !hasEntries(compdb) {
		return "", fmt.Errorf("bear over make produced no compile database for %s: %s", root, lastBytes(output, 600))
	}
	return compdb, nil
}

func hasEntries(path string) bool {
	entries, err := LoadCompdb(path)
	return err == nil && len(entries) > 0
}

// runUnit runs one compile database entry's clang: a syntax-only,
// AST-dumping pass streamed straight into ReadDump — never a whole dump
// buffered to disk, a real one is 25-35 MB. A non-zero exit still keeps
// the shard ReadDump built, marked Failed with the last 400 bytes of
// stderr; a dump that does not parse at all is a failed shard with no
// files.
func runUnit(clangBin string, e CompdbEntry, repo string) *Shard {
	args := append(append([]string{}, clangArgs...), FilterArgs(e.Argv())...)
	cmd := exec.Command(clangBin, args...)
	cmd.Dir = e.Directory
	var stderrBuf bytes.Buffer
	cmd.Stderr = &stderrBuf

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return &Shard{Failed: true, Stderr: err.Error(), Files: []string{}, Decls: []Decl{}, Calls: []Call{}}
	}
	if err := cmd.Start(); err != nil {
		return &Shard{Failed: true, Stderr: err.Error(), Files: []string{}, Decls: []Decl{}, Calls: []Call{}}
	}
	shard, dumpErr := ReadDump(stdout, e.Directory, repo)
	waitErr := cmd.Wait()
	tail := lastBytes(stderrBuf.Bytes(), 400)
	if dumpErr != nil {
		return &Shard{Failed: true, Stderr: tail, Files: []string{}, Decls: []Decl{}, Calls: []Call{}}
	}
	if waitErr != nil {
		shard.Failed = true
		shard.Stderr = tail
	}
	return shard
}

// clangVersionFirst runs `clang --version` and returns its first line,
// or "" if clang cannot run.
func clangVersionFirst(clangBin string) string {
	out, err := exec.Command(clangBin, "--version").Output()
	if err != nil {
		return ""
	}
	line, _, _ := strings.Cut(string(out), "\n")
	return strings.TrimSpace(line)
}

func lastBytes(b []byte, n int) string {
	if len(b) > n {
		b = b[len(b)-n:]
	}
	return string(b)
}
