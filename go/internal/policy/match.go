package policy

import "strings"

// normalize canonicalizes a command string for matching: leading/trailing
// whitespace is trimmed and internal runs of whitespace collapse to a single
// space, so `git  push` cannot dodge a `git push*` rule (ADR-002).
func normalize(command string) string {
	return strings.Join(strings.Fields(command), " ")
}

// matchGlob reports whether s matches pattern. Glob semantics per ADR-001:
// `*` matches any run of characters — including spaces and path separators,
// unlike path.Match — `?` matches exactly one character, every other
// character matches itself, and the match is anchored at both ends. Matching
// is rune-wise so `?` consumes one character, not one byte.
func matchGlob(pattern, s string) bool {
	p, t := []rune(pattern), []rune(s)
	pi, ti := 0, 0
	star, starTi := -1, 0
	for ti < len(t) {
		switch {
		case pi < len(p) && (p[pi] == '?' || p[pi] == t[ti]):
			pi++
			ti++
		case pi < len(p) && p[pi] == '*':
			star, starTi = pi, ti
			pi++
		case star >= 0:
			// Backtrack: let the last `*` swallow one more rune.
			starTi++
			pi, ti = star+1, starTi
		default:
			return false
		}
	}
	for pi < len(p) && p[pi] == '*' {
		pi++
	}
	return pi == len(p)
}
