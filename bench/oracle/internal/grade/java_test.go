package grade

import (
	"path/filepath"
	"testing"

	"github.com/majax7714/Hobbes/bench/oracle/internal/contain"
	"github.com/majax7714/Hobbes/bench/oracle/internal/export"
	"github.com/majax7714/Hobbes/bench/oracle/internal/javac"
)

// The Java javac oracle on the minijava fixture (O8's self-test,
// ADR-096). Hand truth: the JUnit tests' calls (twice, render, the
// Calculator/Circle/Line constructors, text), Report.render's interface
// call to Shape.area with Circle.area as its CHA target, twice → add
// (the two-int overload), Line.text → Strings.pad, this(0) → the
// one-argument constructor, of → the no-argument one. Runs the fixture's
// Maven build inside the image (network, C-66 — the oracle's single
// pass, see ADR-097); skipped without it.
func TestMinijavaJavac(t *testing.T) {
	if why := contain.UnavailableReason(); why != "" && !contain.Uncontained() {
		t.Skip("containment unavailable: " + why)
	}
	repo, _ := filepath.Abs(fixtures + "/minijava")
	plugin, _ := filepath.Abs("../../java")
	o, err := javac.Run(javac.Options{Repo: repo, Module: ".", Out: t.TempDir(), Plugin: plugin})
	if err != nil {
		t.Fatal(err)
	}
	if o.Kind != "resolution" || len(o.Roots) != 1 || o.Roots[0] != "maven" || o.Excluded["synthetic"] == 0 {
		t.Fatalf("header: kind %s roots %v excluded %v", o.Kind, o.Roots, o.Excluded)
	}
	pairs := map[string]bool{}
	for _, s := range o.Sites {
		for _, tg := range s.Targets {
			if !tg.External {
				pairs[s.Pos.Key()+" -> "+tg.Pos.Key()] = true
			}
		}
	}
	app := "src/main/java/com/example/app/"
	test := "src/test/java/com/example/app/"
	want := []string{
		app + "Calculator.java:8 -> " + app + "Calculator.java:11",  // this(0): the one-argument constructor
		app + "Calculator.java:24 -> " + app + "Calculator.java:15", // add(x, x): the int overload
		app + "Calculator.java:32 -> " + app + "Calculator.java:7",  // of(): new Calculator()
		app + "Report.java:11 -> " + app + "Shape.java:5",           // render: the declared area()
		app + "Report.java:11 -> " + app + "Circle.java:11",         // ... and its CHA override
		app + "Report.java:11 -> " + app + "Shapes.java:38",         // ... and the anonymous Shape's, which CHA also holds
		app + "Report.java:17 -> src/main/java/com/example/util/Strings.java:6",
		app + "Report.java:25 -> " + app + "Report.java:10", // the anonymous run(): render(..)
		app + "Report.java:25 -> " + app + "Circle.java:6",  // ... new Circle(1.0)
		app + "Report.java:26 -> " + app + "Report.java:29", // ... tick(), an anonymous member (Hobbes: local-binding)
		app + "Report.java:35 -> " + app + "Report.java:10", // the lambda's render
		app + "Color.java:5 -> " + app + "Color.java:10",    // RED(1): the enum's constructor
		app + "Color.java:6 -> " + app + "Color.java:10",    // GREEN(2)
		app + "Shapes.java:19 -> " + app + "Shapes.java:8",  // Derived.log(s, 1): the inherited two-argument log
		app + "Shapes.java:26 -> " + app + "Shapes.java:11", // Inner.describe(): Base's label(), not the outer Shapes.label()
		test + "CalculatorTest.java:11 -> " + app + "Calculator.java:7",
		test + "CalculatorTest.java:11 -> " + app + "Calculator.java:23",
		test + "CalculatorTest.java:16 -> " + app + "Report.java:10",
		test + "CalculatorTest.java:16 -> " + app + "Circle.java:6",
		test + "CalculatorTest.java:21 -> " + app + "Report.java:15", // new Report.Line(): the implicit constructor, at the class line
		test + "CalculatorTest.java:21 -> " + app + "Report.java:16",
	}
	for _, w := range want {
		if !pairs[w] {
			t.Errorf("missing %s", w)
		}
		delete(pairs, w)
	}
	for extra := range pairs {
		t.Errorf("unexpected in-repo pair %s", extra)
	}
	h, err := export.FromFile("../../testdata/minijava.graph.json", ".", "java")
	if err != nil {
		t.Fatal(err)
	}
	r := Grade(h, o)
	if r.Total.Contradicted != 0 || r.Total.Confirmed < 12 {
		t.Fatalf("minijava: %+v recall %d/%d misses %v", r.Total, r.RecallHits, r.OraclePairs, r.MissBy)
	}
}
