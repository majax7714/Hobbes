// Package derived version-checks the extractor artifacts before anything
// reads them (ADR-028).
//
// ADR-006 has always said consumers reject schema versions they don't
// know. Until v4 none did — the Go side read graph.json straight into a
// struct, so a newer artifact would have been *half-read*: unknown fields
// dropped silently, and every answer built on top of them plausible and
// wrong. The knowledge tools cite file:line at agents and the surface
// draws the graph a human reviews, so a quietly incomplete read is worse
// here than a refusal (P6: degrade visibly).
//
// The pipeline owns the schema; this package owns only the question "may
// I read this version", which is why it holds no artifact shapes.
package derived

import (
	"encoding/json"
	"fmt"
	"slices"
)

// Current is the schema version this build's pipeline emits. Kept in step
// with hobbes.extract.SCHEMA_VERSION by TestSchemaVersionMatchesPipeline.
const Current = 4

// V3Compatible is for readers that touch only fields present since v3.
// v4 is additive (ADR-028), so they read either version correctly.
var V3Compatible = []int{3, 4}

// V4Only is for readers that need v4's edge tier or evidence lane.
var V4Only = []int{4}

// Stamp is the version header every extractor artifact carries. Readers
// unmarshal into their own shapes; this is only what the gate needs.
type Stamp struct {
	SchemaVersion int `json:"schema_version"`
}

// CheckVersion reports whether an artifact may be read, naming the fix.
func CheckVersion(name string, found int, accepts []int) error {
	if slices.Contains(accepts, found) {
		return nil
	}
	if found == 0 {
		return fmt.Errorf(
			"%s carries no schema_version (accepts %v); it predates the version "+
				"gate — re-run `hobbes ingest`", name, accepts)
	}
	if found > Current {
		return fmt.Errorf(
			"%s is schema v%d, newer than this build understands (accepts %v) — "+
				"upgrade Hobbes rather than downgrading the artifact", name, found, accepts)
	}
	return fmt.Errorf(
		"%s is schema v%d, but this reader accepts %v — re-run `hobbes ingest` "+
			"to regenerate it", name, found, accepts)
}

// Unmarshal version-checks *data* and then decodes it into v. It never
// decodes an artifact it would refuse, so a caller cannot act on a
// partially-populated struct.
func Unmarshal(name string, data []byte, accepts []int, v any) error {
	var stamp Stamp
	if err := json.Unmarshal(data, &stamp); err != nil {
		return fmt.Errorf("%s: %w", name, err)
	}
	if err := CheckVersion(name, stamp.SchemaVersion, accepts); err != nil {
		return err
	}
	if v == nil {
		return nil
	}
	if err := json.Unmarshal(data, v); err != nil {
		return fmt.Errorf("%s: %w", name, err)
	}
	return nil
}
