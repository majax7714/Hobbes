package main

import (
	"fmt"

	"example.com/shapes/internal/kinds"
)

func main() {
	j := kinds.JSON("0") // conversion, must not be a call edge
	b := &kinds.Box{}
	b.Cfg().Base = "lhs" // call on the left of an assignment
	out := b.
		Chain("a").
		Chain("b").
		Tail() // chain continuations on their own lines
	name := (*kinds.Box).Job(b, "m") // method expression
	v := kinds.Ref[string]("g")     // generic instantiation call
	fmt.Println(j, out, name, v, kinds.Walk(3))
}
