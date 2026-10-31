import { harnessPackage } from "./harness-package"
import { expect, test } from "bun:test"
import { packageRoot } from "./harnesses/cli"
import { random } from "./harnesses/random"
import { generate, summarize } from "./harnesses/sequence"
import { generateStyled, summarize as summarizeDrawing } from "./harnesses/state-drawing"
import { generate as generateState } from "./harnesses/state-gen"
import { summarize as summarizeLayout } from "./harnesses/state-layout"
import { generate as generateSearch, summarize as summarizeSearch } from "./harnesses/state-search"

const BUN = process.execPath
const run = (args: string[], stdin?: string) =>
  Bun.spawnSync([BUN, ...args], {
    cwd: import.meta.dir,
    stdin: stdin ? Buffer.from(stdin) : undefined,
    env: process.env,
  })

test("a seed makes the same numbers in [0, 1) each time, and another seed others", () => {
  const draw = (seed: number) => {
    const next = random(seed)
    return Array.from({ length: 5 }, next)
  }
  expect(draw(7)).toEqual(draw(7))
  expect(draw(7)).not.toEqual(draw(8))
  expect(draw(7).every((value) => value >= 0 && value < 1)).toBe(true)
})

test("the harnesses load the package named by $PINNED_PACKAGE, else the one above their directory", () => {
  expect(packageRoot).toBe(harnessPackage)
  const child = run(["-e", 'import { packageRoot } from "./harnesses/cli"; console.log(packageRoot)'])
  const unset = Bun.spawnSync([BUN, "-e", 'import { packageRoot } from "./harnesses/cli"; console.log(packageRoot)'], {
    cwd: import.meta.dir,
    env: { ...process.env, PINNED_PACKAGE: undefined },
  })
  expect(child.stdout.toString().trim()).toBe(harnessPackage)
  expect(unset.stdout.toString().trim()).toBe(new URL(".", import.meta.url).pathname.replace(/\/$/, ""))
})

test("the sequence harness makes the same diagrams for a seed, every one drawn without an error", () => {
  const inputs = (seed: number) =>
    Array.from(
      { length: 200 },
      (
        (rand) => () =>
          generate(rand)
      )(random(seed)),
    )
  expect(inputs(3)).toEqual(inputs(3))
  expect(inputs(3)[0]!.split("\n").slice(0, 2)).toEqual([
    expect.stringMatching(/^%%opts compact=[01] gap=\d*$/),
    "sequenceDiagram",
  ])
  expect(
    inputs(3)
      .map(summarize)
      .filter((summary) => "error" in summary),
  ).toEqual([])
})

test("the sequence harness summarizes a diagram's parse, plan and text, one key per value, and catches an error", () => {
  const summary = summarize("%%opts compact=1 gap=30\nsequenceDiagram\nA->>B: hi")
  expect(summary).toMatchObject({
    "diagram.participants.0.id": "A",
    "diagram.messages.0.label": "hi",
    "plan.width": 32,
    "plan.participants.1.centerX": 31,
    "plan.steps.0.inlineLabel": " hi ",
    text: " A                             B\n │                             │\n ├──────────── hi ─────────────►\n │                             │",
  })
  expect(Object.values(summary).every((value) => typeof value !== "object")).toBe(true)
  expect(summarize("sequenceDiagram\nalt")).toEqual({
    error: 'MermaidSyntaxError: Unsupported syntax in sequence diagram at line 2: "alt"',
  })
})

test("run as pinned.py runs it: gen prints a seed's inputs, eval their summaries", () => {
  const gen = run(["harnesses/sequence.ts", "gen", "3", "4"])
  const inputs: string[] = JSON.parse(gen.stdout.toString())
  expect(inputs).toHaveLength(4)
  const evaluated = run(["harnesses/sequence.ts", "eval"], JSON.stringify(inputs))
  expect(JSON.parse(evaluated.stdout.toString())).toEqual(inputs.map(summarize))
})

const many = (make: (rand: () => number) => string, seed: number, count: number) => {
  const rand = random(seed)
  return Array.from({ length: count }, () => make(rand))
}

test("the state harnesses make the same inputs for a seed, a gap line and a header first", () => {
  expect(many(generateState, 5, 50)).toEqual(many(generateState, 5, 50))
  expect(many(generateState, 5, 1)[0]!.split("\n").slice(0, 2)).toEqual([
    expect.stringMatching(/^%%gap \d+$/),
    "stateDiagram-v2",
  ])
  expect(many(generateStyled, 5, 50)).toEqual(many(generateStyled, 5, 50))
  expect(
    many(generateStyled, 5, 50).some((input) =>
      /^%%style (rounded|single|double|heavy) (filled|line) \d*\n/.test(input),
    ),
  ).toBe(true)
  expect(many(generateSearch, 5, 1)[0]).toMatch(/^grid \d+ goal \d+ \d+ budget \d+(\n(start|block) \d+ \d+)+$/)
})

test("the state search harness summarizes the path found and the budget left", () => {
  expect(summarizeSearch("grid 4 goal 3 1 budget 8\nstart 3 3")).toEqual({
    path: '[{"x":3,"y":3},{"x":3,"y":2},{"x":3,"y":1}]',
    remaining: 5,
  })
  expect(summarizeSearch("grid 2 goal 1 1 budget 30\nstart 0 0\nblock 1 1")).toEqual({ path: "null", remaining: 27 })
  expect(
    many(generateSearch, 5, 200)
      .map(summarizeSearch)
      .filter((summary) => "error" in summary),
  ).toEqual([])
})

test("the state layout harness lays out the visible model with the gap line's gap, by the tests' own summary", () => {
  expect(summarizeLayout("%%gap 5\nstateDiagram-v2\nA --> B")).toEqual({
    A: "0,0 5x3 c2,1",
    B: "18,0 5x3 c20,1",
  })
  expect(summarizeLayout("%%gap 1\nstateDiagram-v2\nA --> B")).toMatchObject({
    B: "14,0 5x3 c16,1",
  })
  // From the visible model: the composite's markers are passed through, as the drawing passes them.
  expect(
    Object.keys(summarizeLayout("stateDiagram-v2\nstate P {\n[*] --> X\nX --> [*]\n}\nA --> P\nP --> B")).sort(),
  ).toEqual(["A", "B", "X", "[P]"])
  expect(
    many(generateState, 5, 100)
      .map(summarizeLayout)
      .filter((summary) => "error" in summary),
  ).toEqual([])
})

test("the state drawing harness summarizes each route and each drawn row, with the style line's options", () => {
  expect(summarizeDrawing("stateDiagram-v2\nA --> B : go")).toEqual({
    "route:0": "A>B horizontal-forward 4,1 17,1 @10,0",
    "row:0": "╭───╮     go      ╭───╮",
    "row:1": "│ A ├────────────▶│ B │",
    "row:2": "╰───╯             ╰───╯",
  })
  expect(summarizeDrawing("%%style single line \nstateDiagram-v2\nA --> B")).toMatchObject({
    "row:1": "│ A ├────────────→│ B │",
    "row:0": "┌───┐             ┌───┐",
  })
  // Where the drawing refuses, the summary says why; on these diagrams, only the composite separation does.
  const errors = many(generateStyled, 1, 100)
    .map(summarizeDrawing)
    .flatMap((summary) => ("error" in summary ? [summary.error] : []))
  expect(errors.filter((error) => error !== "Error: State composite separation did not converge")).toEqual([])
}, 60_000)
