// Package policy decides whether a command may run.
package policy

import (
	"os"
	"strings"
)

// Decision is what the engine answers.
type Decision string

const DefaultDecision = "escalate"

// Rule matches a command prefix.
type Rule struct {
	Pattern  string
	Decision Decision
}

// Matches reports whether the rule covers cmd.
func (r *Rule) Matches(cmd string) bool {
	return strings.HasPrefix(cmd, r.Pattern)
}

// Resolve picks the first matching rule's decision.
func Resolve(rules []Rule, cmd string) Decision {
	for _, rule := range rules {
		if rule.Matches(cmd) {
			return rule.Decision
		}
	}
	return Decision(DefaultDecision)
}

// HomeDir reads the environment, so the cross-layer join has a Go end.
func HomeDir() string {
	return os.Getenv("MINIGO_HOME")
}
