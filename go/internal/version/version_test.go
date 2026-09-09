package version

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// The constant equals the root VERSION file (ADR-103); the Python
// suite checks the rest of the copies against the same file.
func TestVersionMatchesTheRootFile(t *testing.T) {
	b, err := os.ReadFile(filepath.Join("..", "..", "..", "VERSION"))
	if err != nil {
		t.Fatal(err)
	}
	if got := strings.TrimSpace(string(b)); got != Version {
		t.Fatalf("VERSION file says %q, version.Version is %q — bump both in one commit", got, Version)
	}
}
