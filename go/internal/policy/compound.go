package policy

import "strings"

// ResolveCommand decides a whole shell command — including a compound one
// (`a && b`, `a; b`, `a | b`) and one carrying `cd`/env-assignment prefixes —
// against the chain (ADR-075).
//
// The rule is: **a compound command is as permitted as its least-permitted
// part.** Each top-level segment is resolved on its own with Resolve, and
// the results combine most-restrictive-wins — deny beats escalate beats
// allow. This is the only honest reading: the single string `git status &&
// rm -rf /` must not run just because its first segment is allowed, and
// `cd /work && python -m pytest` must not escalate just because the anchored
// `python -m pytest*` rule cannot see past the `cd /work &&` prefix. The
// five-fresh-27b run escalated 104 of 253 exec calls to an expiring queue
// with no approver for exactly that reason (C-54).
//
// Splitting is quote-aware but deliberately conservative: when the tokenizer
// cannot be sure it has found a real top-level operator (an unbalanced quote,
// say), it falls back to treating the whole command as one segment — which
// resolves exactly as before this function existed, so ambiguity never
// loosens a decision.
//
// A segment that is only a directory change (`cd <path>`) or bare
// env-assignments (`FOO=bar`) is neutral: it runs nothing the policy governs,
// so it neither drives nor blocks the decision. Env-assignment prefixes on a
// real command (`PYTHONDONTWRITEBYTECODE=1 python -m pytest`) are stripped
// before that segment is matched, so the command under them is what the
// policy sees.
func (c *Chain) ResolveCommand(command string) Result {
	segments, ok := splitTopLevel(command)
	if !ok || len(segments) <= 1 {
		// One segment (or an ambiguous parse): the env/cd prefix still
		// needs handling, but there is nothing compound to combine. A
		// lone neutral segment (a bare `cd /work`) runs nothing the
		// policy governs, so allow it rather than escalate a no-op.
		if len(segments) == 1 && isNeutralSegment(segments[0]) {
			return Result{Command: normalize(command), Decision: Allow, Matches: []RuleMatch{}}
		}
		return c.resolveSegment(command, command)
	}

	// Most-restrictive-wins across the segments. Deny is final (deny-
	// overrides across the whole command); otherwise escalate outranks
	// allow. The decisive segment's Result is returned so the recorder's
	// rule label names the segment that caused the decision, but its
	// Command is the normalized whole command the caller ran.
	var chosen *Result
	rank := func(d Decision) int {
		switch d {
		case Deny:
			return 3
		case Escalate:
			return 2
		default:
			return 1
		}
	}
	any := false
	for _, seg := range segments {
		if isNeutralSegment(seg) {
			continue
		}
		any = true
		r := c.resolveSegment(seg, command)
		if chosen == nil || rank(r.Decision) > rank(chosen.Decision) {
			rc := r
			chosen = &rc
		}
		if chosen.Decision == Deny {
			break
		}
	}
	if !any {
		// Every segment was neutral (e.g. a lone `cd /work`): nothing the
		// policy governs runs, so allow it rather than escalate a no-op.
		return Result{Command: normalize(command), Decision: Allow, Matches: []RuleMatch{}}
	}
	chosen.Command = normalize(command)
	return *chosen
}

// resolveSegment resolves one segment, stripping any leading env-assignments
// first, and reports the whole command as the matched Command so the label
// stays meaningful. matchedOn is the (sub)string actually matched.
func (c *Chain) resolveSegment(segment, whole string) Result {
	stripped := stripEnvAssignments(segment)
	res := c.Resolve(stripped)
	res.Command = normalize(whole)
	return res
}

// isNeutralSegment reports whether a segment runs nothing the policy governs:
// a bare directory change, a shell no-op, or only env-assignments.
func isNeutralSegment(segment string) bool {
	s := stripEnvAssignments(segment)
	s = strings.TrimSpace(s)
	if s == "" || s == "true" || s == ":" {
		return true
	}
	fields := strings.Fields(s)
	if fields[0] == "cd" {
		return true
	}
	return false
}

// stripEnvAssignments removes leading `VAR=value` tokens from a command, so
// `PYTHONDONTWRITEBYTECODE=1 python -m pytest` is matched as `python -m
// pytest`. A value may be single- or double-quoted; the scan stops at the
// first token that is not an assignment.
func stripEnvAssignments(command string) string {
	s := strings.TrimLeft(command, " \t")
	for {
		tok, rest, ok := firstToken(s)
		if !ok || !isAssignment(tok) {
			return s
		}
		s = strings.TrimLeft(rest, " \t")
	}
}

// isAssignment reports whether tok has the shape NAME=... with a valid shell
// name before the first `=`.
func isAssignment(tok string) bool {
	eq := strings.IndexByte(tok, '=')
	if eq <= 0 {
		return false
	}
	for i, r := range tok[:eq] {
		if r == '_' || (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') {
			continue
		}
		if i > 0 && r >= '0' && r <= '9' {
			continue
		}
		return false
	}
	return true
}

// firstToken returns the first whitespace-delimited token of s (honoring
// quotes so a quoted value stays one token) and the remainder. ok is false
// when s is empty or a quote is unbalanced.
func firstToken(s string) (tok, rest string, ok bool) {
	s = strings.TrimLeft(s, " \t")
	if s == "" {
		return "", "", false
	}
	var b strings.Builder
	var quote rune
	for i, r := range s {
		switch {
		case quote != 0:
			b.WriteRune(r)
			if r == quote {
				quote = 0
			}
		case r == '\'' || r == '"':
			quote = r
			b.WriteRune(r)
		case r == ' ' || r == '\t':
			return b.String(), s[i:], true
		default:
			b.WriteRune(r)
		}
	}
	if quote != 0 {
		return "", "", false
	}
	return b.String(), "", true
}

// splitTopLevel splits a shell command on top-level operators `&&`, `||`,
// `;`, and `|`, honoring single and double quotes so an operator inside a
// string is not a separator. ok is false when a quote is unbalanced — the
// caller then treats the command as one segment, so an unparseable command
// resolves exactly as the raw string does (never more permissively).
func splitTopLevel(command string) (segments []string, ok bool) {
	var b strings.Builder
	var quote rune
	runes := []rune(command)
	flush := func() {
		seg := strings.TrimSpace(b.String())
		if seg != "" {
			segments = append(segments, seg)
		}
		b.Reset()
	}
	for i := 0; i < len(runes); i++ {
		r := runes[i]
		switch {
		case quote != 0:
			b.WriteRune(r)
			if r == quote {
				quote = 0
			}
		case r == '\'' || r == '"':
			quote = r
			b.WriteRune(r)
		case r == '\\' && i+1 < len(runes):
			// A backslash escapes the next rune outside quotes; keep both
			// so an escaped operator is not a separator.
			b.WriteRune(r)
			b.WriteRune(runes[i+1])
			i++
		case r == ';':
			flush()
		case (r == '&' || r == '|') && i+1 < len(runes) && runes[i+1] == r:
			flush()
			i++ // consume the doubled operator
		case r == '|': // a single pipe
			flush()
		default:
			b.WriteRune(r)
		}
	}
	if quote != 0 {
		return nil, false
	}
	flush()
	return segments, true
}
