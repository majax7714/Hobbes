// Package main is ADR-166's fixture: dagger's internal/cmd/dagger/main.go
// writes two `func init()` in one file; the commands live in another.
package main

// Cmd stands in for a cobra command.
type Cmd struct{ GroupID string }

// Command returns the command itself, as dagger's call commands do.
func (c *Cmd) Command() *Cmd { return c }

var (
	agentCmd    = &Cmd{}
	callCoreCmd = &Cmd{}
	progress    string
)

// init on a type is a method, with its own qualname, and is not one of
// the file's init functions.
func (c *Cmd) init() {}
