// Package policy is the single implementation of Hobbes's layered policy
// semantics: box → repo → folder scopes merged with deny-overrides-allow and
// a three-tier decision (allow | deny | escalate).
//
// Per build plan M0 there is exactly one implementation of these semantics
// everywhere: the hobbes-policy CLI wraps this package for the Python
// pipeline to shell out to, and the M4 proxy/supervisor daemon imports it
// directly. The file format is defined in ADR-001, resolution semantics in
// ADR-002.
//
// Usage: load the ordered scope chain with LoadChain (or assemble a Chain
// from ParseFile results), then ask it to Resolve a command string.
package policy

import (
	"bytes"
	"errors"
	"fmt"
	"io"
	"os"

	"gopkg.in/yaml.v3"
)

// Decision is the outcome tier of a policy rule or resolution.
type Decision string

const (
	// Allow permits the command to run.
	Allow Decision = "allow"
	// Deny refuses the command. Deny is the only decision that cannot be
	// shadowed by a more specific scope (ADR-002).
	Deny Decision = "deny"
	// Escalate parks the command for human confirmation (architecture §9);
	// unconfirmed escalations expire to deny at the enforcement layer.
	Escalate Decision = "escalate"
)

// valid reports whether d is one of the three known decision tiers.
func (d Decision) valid() bool {
	return d == Allow || d == Deny || d == Escalate
}

// Rule is one command-pattern entry in a policy file. Pattern is a glob over
// the normalized command string: `*` matches any run of characters
// (including spaces and slashes), `?` matches exactly one character, and the
// match is anchored at both ends.
type Rule struct {
	Pattern  string   `yaml:"pattern" json:"pattern"`
	Decision Decision `yaml:"decision" json:"decision"`
	Reason   string   `yaml:"reason,omitempty" json:"reason,omitempty"`
}

// File is one parsed policy file at a single scope level.
type File struct {
	// Version is the schema version; only 1 exists.
	Version int `yaml:"version"`
	// Scope optionally declares the level this file expects to be loaded at
	// (box, repo, role, folder, or agent); the loader rejects the file if
	// it is loaded at a different level.
	Scope string `yaml:"scope,omitempty"`
	// Default is the decision applied when no rule in the whole chain
	// matches; the most specific file that sets one wins (ADR-002).
	Default Decision `yaml:"default,omitempty"`
	// Rules are evaluated in file order.
	Rules []Rule `yaml:"rules"`

	// Source is the path the file was loaded from (diagnostics only).
	Source string `yaml:"-"`
	// Level is the scope level the file was loaded at: "box", "repo",
	// "role", "folder", or "agent". Assigned by the loader, not read from
	// YAML.
	Level string `yaml:"-"`
}

// scopeLevels are the values File.Scope may declare.
var scopeLevels = map[string]bool{
	"box": true, "repo": true, "role": true, "folder": true, "agent": true,
}

// ParseFile parses and validates one policy file. Parsing is strict: unknown
// keys are errors, so a typo in a policy file fails loudly instead of
// silently dropping a rule (ADR-001). source is used in error messages and
// recorded on the returned File.
func ParseFile(data []byte, source string) (*File, error) {
	dec := yaml.NewDecoder(bytes.NewReader(data))
	dec.KnownFields(true)
	var f File
	if err := dec.Decode(&f); err != nil {
		if errors.Is(err, io.EOF) {
			return nil, fmt.Errorf("%s: policy file is empty", source)
		}
		return nil, fmt.Errorf("%s: %w", source, err)
	}
	if f.Version != 1 {
		return nil, fmt.Errorf("%s: unsupported policy version %d (want 1)", source, f.Version)
	}
	if f.Scope != "" && !scopeLevels[f.Scope] {
		return nil, fmt.Errorf("%s: invalid scope %q (want box, repo, role, folder, or agent)", source, f.Scope)
	}
	if f.Default != "" && !f.Default.valid() {
		return nil, fmt.Errorf("%s: invalid default %q (want allow, deny, or escalate)", source, f.Default)
	}
	for i, r := range f.Rules {
		if r.Pattern == "" {
			return nil, fmt.Errorf("%s: rules[%d]: pattern must not be empty", source, i)
		}
		if !r.Decision.valid() {
			return nil, fmt.Errorf("%s: rules[%d] (%q): invalid decision %q (want allow, deny, or escalate)", source, i, r.Pattern, r.Decision)
		}
	}
	f.Source = source
	return &f, nil
}

// LoadFile reads and parses the policy file at path.
func LoadFile(path string) (*File, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return ParseFile(data, path)
}
