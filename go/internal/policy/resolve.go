package policy

// RuleMatch is a rule that matched the command, annotated with where it came
// from. It is the JSON shape promised by ADR-003.
type RuleMatch struct {
	Rule
	// Scope is the level of the file the rule came from: box, repo, folder.
	Scope string `json:"scope"`
	// Source is the path of the policy file the rule came from.
	Source string `json:"source"`

	// specificity is the file's index in the chain; higher is more specific.
	specificity int
}

// Result is the outcome of resolving one command against a Chain. Marshaled
// as-is by the hobbes-policy CLI (ADR-003).
type Result struct {
	// Command is the normalized command string that was matched.
	Command string `json:"command"`
	// Decision is the effective decision for the command.
	Decision Decision `json:"decision"`
	// ByDefault is true when no rule matched and a default applied.
	ByDefault bool `json:"default"`
	// Rule is the decisive rule; nil when ByDefault is true.
	Rule *RuleMatch `json:"rule,omitempty"`
	// DefaultSource names the policy file whose default: applied; empty
	// unless ByDefault is true and a file (not the engine fallback) decided.
	DefaultSource string `json:"default_source,omitempty"`
	// Matches lists every rule that matched, least specific scope first,
	// file order within a scope.
	Matches []RuleMatch `json:"matches"`
}

// Resolve decides a command against the chain per ADR-002:
//
//  1. A matching deny in any scope wins (the box floor); the most specific
//     denying rule is reported as decisive.
//  2. Otherwise the most specific scope holding any match decides
//     (folder over repo over box — shadowing).
//  3. Within that scope, escalate beats allow; ties go to file order.
//  4. With no match anywhere, the default of the most specific file that
//     sets one applies; the engine fallback is escalate.
func (c *Chain) Resolve(command string) Result {
	res := Result{
		Command: normalize(command),
		Matches: []RuleMatch{},
	}

	for i, f := range c.Files {
		for _, r := range f.Rules {
			if matchGlob(r.Pattern, res.Command) {
				res.Matches = append(res.Matches, RuleMatch{
					Rule:        r,
					Scope:       f.Level,
					Source:      f.Source,
					specificity: i,
				})
			}
		}
	}

	if decisive := pickDecisive(res.Matches); decisive != nil {
		res.Decision = decisive.Decision
		res.Rule = decisive
		return res
	}

	res.ByDefault = true
	res.Decision = Escalate
	for i := len(c.Files) - 1; i >= 0; i-- {
		if d := c.Files[i].Default; d != "" {
			res.Decision = d
			res.DefaultSource = c.Files[i].Source
			break
		}
	}
	return res
}

// pickDecisive selects the decisive rule among the matches, or nil if there
// are none. Matches must be ordered least specific first.
func pickDecisive(matches []RuleMatch) *RuleMatch {
	// Deny anywhere wins; report the most specific denying rule (first in
	// file order within its scope, hence the strict > comparison).
	var deny *RuleMatch
	for i := range matches {
		m := matches[i]
		if m.Decision == Deny && (deny == nil || m.specificity > deny.specificity) {
			deny = &matches[i]
		}
	}
	if deny != nil {
		d := *deny
		return &d
	}
	if len(matches) == 0 {
		return nil
	}

	// The most specific scope with any match decides; within it, escalate
	// beats allow, then file order.
	top := matches[0].specificity
	for _, m := range matches {
		if m.specificity > top {
			top = m.specificity
		}
	}
	var allow *RuleMatch
	for i := range matches {
		m := matches[i]
		if m.specificity != top {
			continue
		}
		if m.Decision == Escalate {
			e := m
			return &e
		}
		if allow == nil {
			allow = &matches[i]
		}
	}
	a := *allow
	return &a
}
