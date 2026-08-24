package derived

import (
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"testing"
)

func TestAcceptedVersionsPass(t *testing.T) {
	for _, v := range V3Compatible {
		if err := CheckVersion("graph.json", v, V3Compatible); err != nil {
			t.Errorf("v%d should be accepted: %v", v, err)
		}
	}
}

func TestRefusesAndNamesTheFix(t *testing.T) {
	cases := []struct {
		name    string
		found   int
		accepts []int
		want    string
	}{
		{"older than accepted", 2, V3Compatible, "hobbes ingest"},
		{"v3 under a v4-only reader", 3, V4Only, "hobbes ingest"},
		{"newer than this build", Current + 1, V3Compatible, "upgrade Hobbes"},
		{"no version at all", 0, V3Compatible, "no schema_version"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			err := CheckVersion("graph.json", c.found, c.accepts)
			if err == nil {
				t.Fatal("expected a refusal")
			}
			if !strings.Contains(err.Error(), c.want) {
				t.Errorf("error %q should mention %q", err, c.want)
			}
		})
	}
}

// The whole point of the gate: a refused artifact must not reach the
// caller's struct at all, or zero values read as real data.
func TestRefusedArtifactIsNeverDecoded(t *testing.T) {
	var doc struct {
		Nodes []struct{ ID string } `json:"nodes"`
	}
	data := []byte(`{"schema_version":2,"nodes":[{"id":"a"},{"id":"b"}]}`)
	if err := Unmarshal("graph.json", data, V3Compatible, &doc); err == nil {
		t.Fatal("expected a refusal")
	}
	if len(doc.Nodes) != 0 {
		t.Errorf("refused artifact leaked %d nodes into the caller", len(doc.Nodes))
	}
}

func TestAcceptedArtifactDecodes(t *testing.T) {
	var doc struct {
		Nodes []struct {
			ID string `json:"id"`
		} `json:"nodes"`
	}
	data := []byte(`{"schema_version":4,"nodes":[{"id":"a"}]}`)
	if err := Unmarshal("graph.json", data, V3Compatible, &doc); err != nil {
		t.Fatal(err)
	}
	if len(doc.Nodes) != 1 || doc.Nodes[0].ID != "a" {
		t.Errorf("decoded %+v", doc)
	}
}

// A nil target version-checks without decoding — what the byte-for-byte
// artifact handler needs (ADR-022 keeps the bytes untouched).
func TestNilTargetChecksWithoutDecoding(t *testing.T) {
	if err := Unmarshal("graph.json", []byte(`{"schema_version":4}`), V3Compatible, nil); err != nil {
		t.Errorf("accepted version should pass with a nil target: %v", err)
	}
	if err := Unmarshal("graph.json", []byte(`{"schema_version":1}`), V3Compatible, nil); err == nil {
		t.Error("refused version should fail even with a nil target")
	}
}

// Current must track the pipeline's SCHEMA_VERSION. Two languages, one
// number: if they drift, Go refuses artifacts Python has just written.
func TestCurrentMatchesThePipeline(t *testing.T) {
	root, err := filepath.Abs(filepath.Join("..", "..", ".."))
	if err != nil {
		t.Fatal(err)
	}
	src, err := os.ReadFile(filepath.Join(root, "pipeline", "src", "hobbes", "extract", "__init__.py"))
	if err != nil {
		t.Skipf("pipeline source not available: %v", err)
	}
	m := regexp.MustCompile(`(?m)^SCHEMA_VERSION = (\d+)`).FindSubmatch(src)
	if m == nil {
		t.Fatal("could not find SCHEMA_VERSION in the pipeline")
	}
	want, _ := strconv.Atoi(string(m[1]))
	if want != Current {
		t.Errorf("pipeline emits v%d but Go's Current is v%d", want, Current)
	}
}
