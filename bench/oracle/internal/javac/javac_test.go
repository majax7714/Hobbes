package javac

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

// The merge on hand-written shards: keys join across compilation units
// (a test's call into main resolves against a class file), a dynamic
// site's targets are the declared method plus every override below its
// owner (CHA), an undeclared key is external, generated sources are
// dropped and counted, and a constructor is named after its type.
func TestMergeJoinsShardsAndComputesCHA(t *testing.T) {
	dir := t.TempDir()
	write := func(name, body string) {
		if err := os.WriteFile(filepath.Join(dir, name), []byte(body), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	write("a.json", `{"file":"src/main/java/a/Shape.java","generated":false,"jdk":"21",
	  "declarations":[{"key":"a.Shape#area()","kind":"method","line":3}],
	  "classes":[{"binary":"a.Shape","kind":"interface","supers":[]}],"sites":[]}`)
	write("b.json", `{"file":"src/main/java/a/Circle.java","generated":false,"jdk":"21",
	  "declarations":[{"key":"a.Circle#area()","kind":"method","line":7},{"key":"a.Circle#<init>(double)","kind":"constructor","line":4}],
	  "classes":[{"binary":"a.Circle","kind":"class","supers":["java.lang.Object","a.Shape"]}],"sites":[]}`)
	write("c.json", `{"file":"src/main/java/a/Square.java","generated":false,"jdk":"21",
	  "declarations":[{"key":"a.Square#area()","kind":"method","line":5}],
	  "classes":[{"binary":"a.Square","kind":"class","supers":["a.Circle"]}],"sites":[]}`)
	write("d.json", `{"file":"src/test/java/a/ReportTest.java","generated":false,"jdk":"21",
	  "declarations":[],"classes":[],
	  "sites":[
	    {"line":10,"col":8,"caller":"a.ReportTest#t()","mode":"dynamic","key":"a.Shape#area()","target_kind":"method"},
	    {"line":11,"col":8,"caller":"a.ReportTest#t()","mode":"static","key":"a.Circle#<init>(double)","target_kind":"constructor"},
	    {"line":12,"col":8,"caller":"a.ReportTest#t()","mode":"static","key":"java.lang.String#valueOf(int)","target_kind":"method"},
	    {"line":13,"col":8,"caller":"a.ReportTest#t()","mode":"dynamic","key":"java.util.List#size()","target_kind":"method"}]}`)
	write("e.json", `{"file":"target/generated-sources/a/Gen.java","generated":true,"jdk":"21",
	  "declarations":[],"classes":[],"sites":[{"line":1,"col":0,"caller":"x","mode":"static","key":"a.Circle#area()","target_kind":"method"}]}`)

	o, err := Merge(dir, "")
	if err != nil {
		t.Fatal(err)
	}
	if o.Kind != "resolution" || o.Oracle != "javac 21" || o.Excluded["generated"] != 1 {
		t.Fatalf("header: %+v", o)
	}
	if len(o.Files) != 4 {
		t.Fatalf("files: %v", o.Files)
	}
	if len(o.Sites) != 4 {
		t.Fatalf("sites: %d", len(o.Sites))
	}
	area := o.Sites[0]
	if area.Mode != "dynamic" || area.Interface == nil || area.Interface.Pos != (edges.Pos{Path: "src/main/java/a/Shape.java", Line: 3}) {
		t.Fatalf("interface: %+v", area)
	}
	got := map[string]bool{}
	for _, tg := range area.Targets {
		got[tg.Pos.Key()] = true
	}
	for _, want := range []string{"src/main/java/a/Shape.java:3", "src/main/java/a/Circle.java:7", "src/main/java/a/Square.java:5"} {
		if !got[want] {
			t.Errorf("CHA target %s missing from %v", want, area.Targets)
		}
	}
	ctor := o.Sites[1]
	if len(ctor.Targets) != 1 || ctor.Targets[0].Name != "Circle" || ctor.Targets[0].Kind != "constructor" || ctor.Targets[0].Pos.Line != 4 {
		t.Fatalf("constructor: %+v", ctor.Targets)
	}
	ext := o.Sites[2]
	if len(ext.Targets) != 1 || !ext.Targets[0].External || ext.Targets[0].Name != "valueOf" {
		t.Fatalf("external: %+v", ext.Targets)
	}
	dyn := o.Sites[3]
	if dyn.Interface == nil || !dyn.Interface.External || len(dyn.Targets) != 1 || !dyn.Targets[0].External {
		t.Fatalf("external dynamic: %+v", dyn)
	}
}

func TestMemberNames(t *testing.T) {
	cases := map[string]string{
		"a.b.Outer$Inner#<init>(int)":       "Inner",
		"a.b.Foo#bar(java.lang.String,int)": "bar",
		"a.Foo#<init>()":                    "Foo",
	}
	for k, want := range cases {
		if got := memberName(k); got != want {
			t.Errorf("%s: got %q want %q", k, got, want)
		}
	}
}

func TestJavaHomeIsDerivedFromTheBuildFiles(t *testing.T) {
	dir := t.TempDir()
	os.WriteFile(filepath.Join(dir, "build.gradle"), []byte("sourceCompatibility = JavaVersion.VERSION_25\n"), 0o644)
	if got := JavaHome(dir); got != "/usr/local/java-25" {
		t.Fatalf("got %s", got)
	}
	os.WriteFile(filepath.Join(dir, "build.gradle"), []byte("java { toolchain { languageVersion = JavaLanguageVersion.of(17) } }\n"), 0o644)
	if got := JavaHome(dir); got != "/usr/local/java-21" {
		t.Fatalf("got %s", got)
	}
}
