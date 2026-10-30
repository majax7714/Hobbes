import { expect, test } from "bun:test"
import { parseMermaidStateDiagram } from "../../src/state/parser"
import { isHiddenCompositeMarker, prepareVisibleStateDiagram } from "../../src/state/visible-model"

const visible = (body: string) => prepareVisibleStateDiagram(parseMermaidStateDiagram(`stateDiagram-v2\n${body}`))
const edges = (body: string) => visible(body).transitions.map((t) => `${t.from}>${t.to}:${t.label}`)

test("a hidden marker is a start or end inside a composite", () => {
  expect(
    [
      { id: "P.__start", label: "●", kind: "start" as const, parentId: "P" },
      { id: "P.__end", label: "◎", kind: "end" as const, parentId: "P" },
      { id: "__start", label: "●", kind: "start" as const },
      { id: "X", label: "X", kind: "state" as const, parentId: "P" },
      undefined,
    ].map(isHiddenCompositeMarker),
  ).toEqual([true, true, false, false, false])
})

test("a composite's markers are passed through: each way in joins each way on, the labels joined by a break", () => {
  const diagram = visible("state P {\n[*] --> X\nX --> [*]\n}\nA --> P : in\nP --> B : out\nC --> P : again")
  expect(diagram.transitions).toEqual([
    { from: "A", to: "X", label: "in" },
    { from: "C", to: "X", label: "again" },
    { from: "X", to: "B", label: "out" },
  ])
  expect(diagram.states.map((state) => state.id)).toEqual(["X", "A", "B", "C"])
  expect(edges("state P {\n[*] --> X : a\n}\nA --> P : b")).toEqual(["A>X:b<br/>a"])
  // Through two composites' markers in a row.
  expect(edges("state P {\nX --> [*]\n}\nstate Q {\n[*] --> Y\n}\nP --> Q : hop")).toEqual(["X>Y:hop"])
})

test("a marker with no way in or no way on stays, and so does its state; a composite's loop to itself runs through both", () => {
  expect(edges("state P {\n[*] --> X\n}")).toEqual(["P.__start>X:"])
  expect(visible("state P {\n[*] --> X\n}").states.map((state) => state.id)).toEqual(["P.__start", "X"])
  expect(edges("state P {\n[*] --> X\nX --> [*]\n}\nP --> P")).toEqual(["X>X:"])
})

// subsume reads this case as redundant: no fault it plants drops the copy alone. Planted by hand (the
// transitions passed on uncopied), this is the only case that fails.
test("a top-level diagram is passed through as it is", () => {
  const diagram = parseMermaidStateDiagram("stateDiagram\n[*] --> A\nA --> [*]")
  const prepared = prepareVisibleStateDiagram(diagram)
  expect(prepared).toEqual(diagram)
  expect(prepared.transitions[0]).not.toBe(diagram.transitions[0])
})
