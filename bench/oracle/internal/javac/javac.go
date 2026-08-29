// Package javac runs the Java resolution oracle (ADR-096, the lane's
// O8): the repo's own build — Maven or its Gradle wrapper — with the
// HobbesOracle javac plugin attached (bench/oracle/java), inside the
// sandbox image, then merges the plugin's per-compilation-unit shards
// into the lane's OracleExport (kind "resolution").
//
// What the compiler resolved is the site's declared target — the
// tsc-oracle's grain. For a virtual or interface call (mode "dynamic")
// the declared method rides as the site's Interface, so a Hobbes edge
// to it buckets abstract, and the targets are the CHA override set:
// every declaration in the compiled program with the same name and
// erased parameters whose owner is a subtype of the declared owner —
// computed here from the hierarchy the shards record. Java's dispatch
// hole (C-58's majority case) is therefore sized as recall against CHA,
// stated per cell.
//
// The build executes repo-authored logic and resolves its own
// dependencies, so the step keeps a network exactly as the ingest
// lane's index-java does (C-66); the container is the boundary.
package javac

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"

	"github.com/majax7714/Hobbes/bench/oracle/internal/contain"
	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

// Options is one Java cell: a build root inside the repo.
type Options struct {
	Repo   string // repo root
	Module string // repo-relative build root ("" or "." for the repo root)
	Tool   string // "maven" or "gradle"; "" derives it (pom.xml wins)
	Out    string // cell directory: shards, the plugin jar
	Plugin string // bench/oracle/java — the plugin's source, wrapper and init script
}

type shard struct {
	File         string `json:"file"`
	Generated    bool   `json:"generated"`
	JDK          string `json:"jdk"`
	Synthetic    int    `json:"synthetic"`
	Declarations []struct {
		Key  string `json:"key"`
		Kind string `json:"kind"`
		Line int    `json:"line"`
	} `json:"declarations"`
	Classes []struct {
		Binary string   `json:"binary"`
		Kind   string   `json:"kind"`
		Supers []string `json:"supers"`
	} `json:"classes"`
	Sites []struct {
		Line       int    `json:"line"`
		Col        int    `json:"col"`
		Caller     string `json:"caller"`
		Mode       string `json:"mode"`
		Key        string `json:"key"`
		TargetKind string `json:"target_kind"`
	} `json:"sites"`
}

// Run builds the plugin (once per cell dir), runs the build under it and
// merges the shards.
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
	tool := o.Tool
	if tool == "" {
		if _, err := os.Stat(filepath.Join(dir, "pom.xml")); err == nil {
			tool = "maven"
		} else {
			tool = "gradle"
		}
	}
	plugin, _ := filepath.Abs(o.Plugin)
	outAbs, _ := filepath.Abs(o.Out)
	jarDir := filepath.Join(outAbs, "plugin")
	jar := filepath.Join(jarDir, "hobbes-oracle.jar")
	if _, err := os.Stat(jar); err != nil {
		build, err := contain.New("java-build", []string{"sh", filepath.Join(plugin, "build.sh"), jarDir},
			repo, repo, []string{outAbs}, []string{plugin}, nil)
		if err != nil {
			return nil, err
		}
		if _, err := contain.Run(build); err != nil {
			return nil, fmt.Errorf("javac: building the plugin: %w", err)
		}
	}
	shards := filepath.Join(outAbs, "javac-shards")
	os.RemoveAll(shards)
	if err := os.MkdirAll(shards, 0o755); err != nil {
		return nil, err
	}
	cache := contain.CacheRoot()
	javaHome := JavaHome(dir)
	env := []string{
		"HOBBES_ORACLE_JAR=" + jar,
		"HOBBES_ORACLE_OUT=" + shards,
		"HOBBES_ORACLE_REPO=" + repo,
		"JAVA_HOME=" + javaHome,
		"PATH=" + javaHome + "/bin:" + contain.Path,
		"MAVEN_OPTS=-Dmaven.repo.local=" + filepath.Join(cache, "m2"),
		"GRADLE_USER_HOME=" + filepath.Join(cache, "gradle"),
	}
	var cmd []string
	switch tool {
	case "maven":
		cmd = []string{"mvn", "--batch-mode", "-DskipTests",
			"-Dmaven.compiler.fork=true", "-Dmaven.compiler.compilerId=javac",
			"-Dmaven.compiler.useIncrementalCompilation=false",
			"-Dmaven.compiler.executable=" + filepath.Join(plugin, "javac-oracle.py"),
			"clean", "test-compile"}
	case "gradle":
		wrapper := filepath.Join(dir, "gradlew")
		if _, err := os.Stat(wrapper); err != nil {
			return nil, fmt.Errorf("javac: %s has no gradlew (the image carries no Gradle)", dir)
		}
		cmd = []string{"sh", wrapper, "--init-script", filepath.Join(plugin, "hobbes-oracle.gradle"),
			"clean", "compileTestJava"}
	default:
		return nil, fmt.Errorf("javac: unknown build tool %q", tool)
	}
	plan, err := contain.New("java-javac", cmd, dir, repo, []string{outAbs}, []string{plugin}, env)
	if err != nil {
		return nil, err
	}
	outcome, err := contain.Run(plan)
	if err != nil {
		return nil, fmt.Errorf("javac: %s in %s: %w", strings.Join(cmd, " "), dir, err)
	}
	merged, err := Merge(shards, module)
	if err != nil {
		return nil, err
	}
	merged.Containment = outcome.Containment()
	merged.Roots = []string{tool}
	return merged, nil
}

// javaLevel matches the source/release level a build file spells —
// the same observation the ingest lane's `java_home_for` makes.
var javaLevel = regexp.MustCompile(`(?:VERSION_|JavaLanguageVersion\.of\(|languageVersion\s*=\s*|sourceCompatibility\s*=\s*|targetCompatibility\s*=\s*|release\s*=\s*|<release>|<maven\.compiler\.release>|<maven\.compiler\.source>|<java\.version>|<javaVersion>)\s*['"]?(\d{1,2})`)

// JavaHome derives the image JDK the build runs on from the build files
// under dir (poms, Gradle scripts): 25 when a level above 21 is spelled,
// else the default 21 — a newer javac compiles an older level, and a
// toolchain pin resolves through the derived gradle.properties. Mirrors
// scipsource.java_home_for so the oracle compiles what the ingest did.
func JavaHome(dir string) string {
	wanted := 0
	filepath.WalkDir(dir, func(p string, d os.DirEntry, err error) error {
		if err != nil {
			return nil
		}
		if d.IsDir() {
			switch d.Name() {
			case "target", "build", ".git", "node_modules", ".gradle":
				return filepath.SkipDir
			}
			return nil
		}
		name := d.Name()
		if name != "pom.xml" && name != "build.gradle" && name != "build.gradle.kts" && name != "gradle.properties" {
			return nil
		}
		raw, err := os.ReadFile(p)
		if err != nil {
			return nil
		}
		for _, m := range javaLevel.FindAllStringSubmatch(string(raw), -1) {
			if n, err := strconv.Atoi(m[1]); err == nil && n > wanted {
				wanted = n
			}
		}
		return nil
	})
	if wanted > 21 {
		return "/usr/local/java-25"
	}
	return "/usr/local/java-21"
}

type decl struct {
	pos  edges.Pos
	kind string
}

// Merge joins the shards: declarations by key, the class hierarchy, and
// every site under module with its resolved target and — for dynamic
// sites — the CHA override set.
func Merge(dir, module string) (*edges.OracleExport, error) {
	names, err := filepath.Glob(filepath.Join(dir, "*.json"))
	if err != nil {
		return nil, err
	}
	if len(names) == 0 {
		return nil, fmt.Errorf("javac: the plugin wrote nothing under %s (did the build compile anything?)", dir)
	}
	sort.Strings(names)
	var all []shard
	for _, n := range names {
		raw, err := os.ReadFile(n)
		if err != nil {
			return nil, err
		}
		var s shard
		if err := json.Unmarshal(raw, &s); err != nil {
			return nil, fmt.Errorf("%s: %w", n, err)
		}
		all = append(all, s)
	}
	out := &edges.OracleExport{Kind: "resolution", Module: module, Tags: []string{}, Excluded: map[string]int{}}
	decls := map[string]decl{}
	supers := map[string][]string{}
	// name(params) -> owners declaring it
	byMember := map[string][]string{}
	files := map[string]bool{}
	for _, s := range all {
		if out.Oracle == "" {
			out.Oracle = "javac " + s.JDK
		}
		if s.Generated {
			continue
		}
		if edges.Under(s.File, module) {
			files[s.File] = true
		}
		for _, d := range s.Declarations {
			if _, dup := decls[d.Key]; dup {
				continue // a lib compiled for itself and for its tests reports it twice
			}
			decls[d.Key] = decl{pos: edges.Pos{Path: s.File, Line: d.Line}, kind: d.Kind}
			owner, member := splitKey(d.Key)
			byMember[member] = append(byMember[member], owner)
		}
		for _, c := range s.Classes {
			supers[c.Binary] = append(supers[c.Binary], c.Supers...)
		}
	}
	// subtypes[owner] = every declared class below it, transitively.
	subtypes := map[string]map[string]bool{}
	var ancestors func(c string, seen map[string]bool)
	ancestors = func(c string, seen map[string]bool) {
		for _, s := range supers[c] {
			if seen[s] {
				continue
			}
			seen[s] = true
			ancestors(s, seen)
		}
	}
	for c := range supers {
		seen := map[string]bool{}
		ancestors(c, seen)
		for a := range seen {
			if subtypes[a] == nil {
				subtypes[a] = map[string]bool{}
			}
			subtypes[a][c] = true
		}
	}
	type key struct {
		path      string
		line, col int
	}
	merged := map[key]*edges.Site{}
	var order []key
	for _, s := range all {
		out.Excluded["synthetic"] += s.Synthetic
		if s.Generated {
			out.Excluded["generated"] += len(s.Sites)
			continue
		}
		if !edges.Under(s.File, module) {
			continue
		}
		for _, site := range s.Sites {
			k := key{s.File, site.Line, site.Col}
			if _, dup := merged[k]; dup {
				continue
			}
			declared := target(site.Key, decls, site.TargetKind)
			es := &edges.Site{
				Pos:    edges.Pos{Path: s.File, Line: site.Line},
				Col:    site.Col,
				Caller: site.Caller,
				Mode:   site.Mode,
			}
			if site.Mode == "dynamic" {
				iface := declared
				es.Interface = &iface
				if !declared.External {
					es.Targets = append(es.Targets, declared)
				}
				owner, member := splitKey(site.Key)
				for _, o := range byMember[member] {
					if subtypes[owner][o] {
						t := target(o+"#"+member, decls, site.TargetKind)
						if !hasTarget(es.Targets, t) {
							es.Targets = append(es.Targets, t)
						}
					}
				}
				if declared.External && len(es.Targets) == 0 {
					es.Targets = append(es.Targets, declared)
				}
			} else {
				es.Targets = []edges.Target{declared}
			}
			merged[k] = es
			order = append(order, k)
		}
	}
	sort.Slice(order, func(i, j int) bool {
		a, b := order[i], order[j]
		if a.path != b.path {
			return a.path < b.path
		}
		if a.line != b.line {
			return a.line < b.line
		}
		return a.col < b.col
	})
	for _, k := range order {
		out.Sites = append(out.Sites, *merged[k])
	}
	for f := range files {
		out.Files = append(out.Files, f)
	}
	sort.Strings(out.Files)
	if out.Sites == nil {
		out.Sites = []edges.Site{}
	}
	if out.Files == nil {
		out.Files = []string{}
	}
	return out, nil
}

// target resolves a declaration key to a Target: in-repo when a shard
// declared it (position = the name identifier's line), external
// otherwise (the JDK, a dependency, generated code) — named by the key.
func target(k string, decls map[string]decl, kind string) edges.Target {
	if d, ok := decls[k]; ok {
		return edges.Target{Pos: d.pos, Name: memberName(k), Kind: d.kind}
	}
	return edges.Target{Name: memberName(k), Kind: kind, External: true}
}

func splitKey(k string) (owner, member string) {
	at := strings.Index(k, "#")
	if at < 0 {
		return k, ""
	}
	return k[:at], k[at+1:]
}

func memberName(k string) string {
	_, member := splitKey(k)
	if at := strings.Index(member, "("); at >= 0 {
		member = member[:at]
	}
	if member == "<init>" {
		owner, _ := splitKey(k)
		if at := strings.LastIndexAny(owner, ".$"); at >= 0 {
			owner = owner[at+1:]
		}
		return owner
	}
	return member
}

func hasTarget(ts []edges.Target, t edges.Target) bool {
	for _, x := range ts {
		if x.Pos == t.Pos && x.Name == t.Name && x.External == t.External {
			return true
		}
	}
	return false
}
