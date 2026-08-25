// Package kinds holds the types and helpers the shapes fixture calls.
package kinds

// JSON is a named string type: kinds.JSON("x") is a conversion, not a call.
type JSON string

// Config is mutated through a call on the left of an assignment.
type Config struct{ Base string }

// Box wraps a Config.
type Box struct{ cfg Config }

// Cfg returns the box's config for in-place assignment.
func (b *Box) Cfg() *Config { return &b.cfg }

// Chain is a builder step.
func (b *Box) Chain(s string) *Box { return b }

// Tail ends a chain.
func (b *Box) Tail() string { return b.cfg.Base }

// Job is called as a method expression: (*Box).Job(&b, "x").
func (b *Box) Job(name string) string { return name }

// Ref is a generic function called with an explicit instantiation.
func Ref[T any](v T) T { return v }

// Walk recurses.
func Walk(n int) int {
	if n <= 0 {
		return 0
	}
	return Walk(n - 1)
}

// Embedded is a typed var: its symbol is Embedded, not `string`.
var Embedded string

// Key is a typed const, likewise.
const Key string = "k"

// A, B share one spec.
var A, B int
