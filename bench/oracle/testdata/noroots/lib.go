// Package noroots is a library with no main and no tests: a
// reachability oracle has nothing to root at (A-1).
package noroots

func Helper() int { return inner() }

func inner() int { return 1 }
