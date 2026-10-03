package main

func init() {
	// allow user explicitly setting progress via env, but default it to "auto"
	// otherwise
	if progress == "" {
		progress = "auto"
	}
}

func main() {}

func init() {
	agentCmd.GroupID = "daily"
	register(callCoreCmd.Command())
}

func register(c *Cmd) {}
