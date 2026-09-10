// Package version holds the one version of the Hobbes layer (ADR-103).
// It equals the root VERSION file, the Python package's __version__ and
// the Node helpers' package.json; the Python suite's test_version.py and
// this package's test hold them together. Bench tooling and the
// experiments under bench/ are not versioned — they are internal testing,
// not releases of Hobbes.
package version

// Version is the Hobbes layer's version, bumped by hand in the same
// commit as every other copy (see ADR-103 for what bumps which part).
const Version = "0.1.4-beta"
