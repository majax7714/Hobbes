// Command app is the first module of the twomod fixture: it calls into
// the replaced lib module and into itself.
package main

import (
	"fmt"

	"example.com/lib"
)

func banner(s string) string {
	return "[" + s + "]"
}

func main() {
	fmt.Println(banner(lib.Greet("app")))
	fmt.Println(lib.Lookup(lib.MemStore{}, "key"))
}
