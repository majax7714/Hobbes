package grade

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"testing"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

// The JavaScript fixture, graded with no tsconfig.json anywhere (ADR-140
// step 3): the oracle builds the program from the discovered sources
// under the options the ingest generates for such files, so the key
// grades the program both product lanes see.
//
// The hand's reading of minijs, written from the fixture before the
// oracle was run — every call site by path:line (two sites share
// esm/main.mjs:3), the mode, and what the compiler should resolve it to:
//
//	index.js:2   require("./lib/math")   static, none — `require` has no declaration here
//	index.js:3   require("./lib/counter") static, none
//	index.js:4   require("./lib/math")   static, none
//	index.js:5   require("./lib/apply")  static, none
//	index.js:8   new Counter(1)          static → lib/counter.js:3   (module.exports = Counter)
//	index.js:9   c.inc()                 static → lib/counter.js:7   (the prototype assignment)
//	index.js:10  math.double(2)          static → lib/math.js:9      (exports.double = function)
//	index.js:11  add(1, 2)               static → lib/math.js:3      (the destructured require)
//	index.js:12  apply((s) => s)         static → lib/apply.js:4
//	lib/math.js:10   add(x, x)           static → lib/math.js:3
//	lib/apply.js:5   f("a")              dynamic → lib/apply.js:4    (the JSDoc-typed parameter)
//	esm/greet.mjs:7  greet("x")          static → esm/greet.mjs:1
//	esm/main.mjs:3   new Greeter()       static → esm/greet.mjs:5
//	esm/main.mjs:3   .hello()            static → esm/greet.mjs:6
//	esm/main.mjs:4   greet("y")          static → esm/greet.mjs:1
//	ui/button.jsx:2  <span>              static, none — an intrinsic element has no declaration
//	ui/button.jsx:6  <Label />           static → ui/button.jsx:1
//
// Where tsc's answer differs from that reading the assertion below says
// what tsc says, with the hand's row kept beside it: only the program's
// construction is the oracle's to change, never its resolution.
func TestMinijsNoTsconfigResolvesTheJavaScriptShapes(t *testing.T) {
	o, _ := runJSOracle(t, "minijs", "--no-tsconfig")
	if o.Kind != "resolution" {
		t.Fatalf("kind: %s", o.Kind)
	}
	wantFiles := []string{
		"esm/greet.mjs", "esm/main.mjs", "index.js",
		"lib/apply.js", "lib/counter.js", "lib/math.js", "ui/button.jsx",
	}
	if fmt.Sprint(o.Files) != fmt.Sprint(wantFiles) {
		t.Fatalf("files: %v", o.Files)
	}

	// One row per site, in the oracle's order (path, line, column):
	// "<mode> <target path:line>…", or "<mode> —" for a silent site.
	want := map[string][]string{
		"index.js:2":      {"static —"},
		"index.js:3":      {"static —"},
		"index.js:4":      {"static —"},
		"index.js:5":      {"static —"},
		"index.js:8":      {"static lib/counter.js:3"},
		"index.js:9":      {"static lib/counter.js:7"},
		"index.js:10":     {"static lib/math.js:9"},
		"index.js:11":     {"static lib/math.js:3"},
		"index.js:12":     {"static lib/apply.js:4"},
		"lib/math.js:10":  {"static lib/math.js:3"},
		"lib/apply.js:5":  {"dynamic lib/apply.js:4"},
		"esm/greet.mjs:7": {"static esm/greet.mjs:1"},
		// tsc's reading, not the hand's: `Greeter` has no constructor, so
		// the resolved construct signature is synthesized and has no
		// declaration to name — the new-site is silent. The hand read
		// `static esm/greet.mjs:5`. The `.hello()` beside it resolving
		// shows the class itself is fully resolved.
		"esm/main.mjs:3":  {"static —", "static esm/greet.mjs:6"},
		"esm/main.mjs:4":  {"static esm/greet.mjs:1"},
		"ui/button.jsx:2": {"static —"},
		"ui/button.jsx:6": {"static ui/button.jsx:1"},
	}
	got := map[string][]string{}
	for _, s := range o.Sites {
		parts := []string{}
		for _, tg := range s.Targets {
			parts = append(parts, tg.Pos.Key())
		}
		if len(parts) == 0 {
			parts = []string{"—"}
		}
		k := s.Pos.Key()
		got[k] = append(got[k], s.Mode+" "+strings.Join(parts, " "))
	}
	for k, w := range want {
		if fmt.Sprint(got[k]) != fmt.Sprint(w) {
			t.Errorf("%s: oracle %v, hand %v", k, got[k], w)
		}
		delete(got, k)
	}
	for _, k := range sortedKeys(got) {
		t.Errorf("%s: site the hand did not key: %v", k, got[k])
	}

	// The shape the cell is most for, named again through the target:
	// `f("a")` reaches the parameter, and reaches it as a binding rather
	// than as a declaration of its own — a `parameter`, not a `closure`
	// (H-33), so the miss class a lost edge here would carry names the
	// parameter.
	for _, s := range o.Sites {
		if s.Pos.Key() == "lib/apply.js:5" && len(s.Targets) == 1 {
			tg := s.Targets[0]
			if tg.Via != "binding" || tg.Name != "f" {
				t.Errorf("f(\"a\") must resolve to the parameter's binding: %+v", tg)
			}
			if tg.Kind != "parameter" || tg.Closure {
				t.Errorf("the binding is a parameter, not a closure: kind %q closure %v", tg.Kind, tg.Closure)
			}
			if c := missClass(s, tg); c != "func-value→parameter" {
				t.Errorf("miss class: %s", c)
			}
		}
	}
}

// Flag mode says what it built the program from, since the repo says
// nothing: the eight generated options, the skip list, and the
// jsconfig.json files it ignored (none here).
func TestMinijsNoTsconfigSaysSo(t *testing.T) {
	_, raw := runJSOracle(t, "minijs", "--no-tsconfig")
	var doc struct {
		Oracle          string `json:"oracle"`
		GeneratedConfig *struct {
			Options        map[string]any `json:"options"`
			SkippedDirs    []string       `json:"skipped_dirs"`
			IgnoredConfigs []string       `json:"ignored_configs"`
		} `json:"generated_config"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatal(err)
	}
	if doc.GeneratedConfig == nil {
		t.Fatal("flag mode must state the config it generated")
	}
	// scipsource._generated_tsconfig's compilerOptions, verbatim.
	wantOptions := map[string]any{
		"allowJs": true, "checkJs": false, "module": "ESNext",
		"moduleResolution": "Bundler", "target": "ES2022", "jsx": "preserve",
		"noEmit": true, "skipLibCheck": true,
	}
	if fmt.Sprint(sortedPairs(doc.GeneratedConfig.Options)) != fmt.Sprint(sortedPairs(wantOptions)) {
		t.Errorf("options: %v", sortedPairs(doc.GeneratedConfig.Options))
	}
	if len(doc.GeneratedConfig.IgnoredConfigs) != 0 {
		t.Errorf("minijs has no jsconfig.json: %v", doc.GeneratedConfig.IgnoredConfigs)
	}
	if len(doc.GeneratedConfig.SkippedDirs) == 0 || !strings.Contains(fmt.Sprint(doc.GeneratedConfig.SkippedDirs), "node_modules") {
		t.Errorf("skipped_dirs: %v", doc.GeneratedConfig.SkippedDirs)
	}
	if !strings.Contains(doc.Oracle, "no tsconfig") {
		t.Errorf("oracle string must say the program had no config: %q", doc.Oracle)
	}
}

// The three ways the mode declines rather than grading a program nobody
// asked for.
func TestNoTsconfigRefusals(t *testing.T) {
	needNode(t)
	for _, tc := range []struct {
		name string
		args []string
		code int
		says string
	}{
		{"minijs without the flag", []string{"--repo", fixtures + "/minijs", "--zone", "."}, 1, "--no-tsconfig"},
		{"minits with it", []string{"--repo", fixtures + "/minits", "--zone", ".", "--no-tsconfig"}, 1, "tsconfig.json"},
		{"both", []string{"--repo", fixtures + "/minijs", "--zone", ".", "--no-tsconfig", "--config", "tsconfig.build.json"}, 2, "--config"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			cmd := exec.Command("node", append([]string{"../../ts/tsc-oracle.mjs"}, tc.args...)...)
			b, err := cmd.CombinedOutput()
			if err == nil {
				t.Fatalf("expected exit %d; the oracle graded it:\n%s", tc.code, b)
			}
			if code := cmd.ProcessState.ExitCode(); code != tc.code {
				t.Fatalf("exit %d, want %d:\n%s", code, tc.code, b)
			}
			if !strings.Contains(string(b), tc.says) {
				t.Fatalf("the refusal must name %q:\n%s", tc.says, b)
			}
		})
	}
}

// The same reading on TypeScript, where the TS cells are graded: a call
// through a parameter is `func-value→parameter`, never `static→closure`
// (H-33), so every site with a parameter binding is dynamic. minits
// holds **0** of them — it has no call through a binding of any kind,
// which is why the shape needed the JavaScript fixture above to be seen
// — so the count is asserted as 0 rather than invented.
func TestMinitsParameterBindingsAreDynamic(t *testing.T) {
	o, _ := runJSOracle(t, "minits")
	n := 0
	for _, s := range o.Sites {
		for _, tg := range s.Targets {
			if tg.Via != "binding" || tg.Kind != "parameter" {
				continue
			}
			n++
			if s.Mode != "dynamic" {
				t.Errorf("%s: a call through the parameter %s is %s, want dynamic", s.Pos.Key(), tg.Name, s.Mode)
			}
		}
	}
	if n != 0 {
		t.Errorf("minits parameter-binding sites: %d, want 0 — the fixture gained the shape; say so and read the count again", n)
	}
}

func needNode(t *testing.T) {
	t.Helper()
	if _, err := exec.LookPath("node"); err != nil {
		t.Skip("node not on PATH")
	}
}

// Runs tsc-oracle.mjs over a fixture and returns both the parsed export
// and the raw bytes (the generated-config key is not on OracleExport).
func runJSOracle(t *testing.T, fixture string, extra ...string) (*edges.OracleExport, []byte) {
	t.Helper()
	needNode(t)
	out := filepath.Join(t.TempDir(), "oracle.json")
	argv := append([]string{"../../ts/tsc-oracle.mjs", "--repo", fixtures + "/" + fixture, "--zone", ".", "--out", out}, extra...)
	cmd := exec.Command("node", argv...)
	if b, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("tsc-oracle: %v\n%s", err, b)
	}
	raw, err := os.ReadFile(out)
	if err != nil {
		t.Fatal(err)
	}
	var o edges.OracleExport
	if err := json.Unmarshal(raw, &o); err != nil {
		t.Fatal(err)
	}
	return &o, raw
}

func sortedKeys[V any](m map[string]V) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}

func sortedPairs(m map[string]any) []string {
	pairs := make([]string, 0, len(m))
	for _, k := range sortedKeys(m) {
		pairs = append(pairs, fmt.Sprintf("%s=%v", k, m[k]))
	}
	return pairs
}
