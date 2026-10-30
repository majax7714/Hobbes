import { harnessPackage } from "./harness-package"
import { expect, test } from "bun:test"
import { packageRoot } from "./harnesses/cli"
import { random } from "./harnesses/random"
import { generate, summarize } from "./harnesses/sequence"

const BUN = process.execPath
const run = (args: string[], stdin?: string) =>
  Bun.spawnSync([BUN, ...args], { cwd: import.meta.dir, stdin: stdin ? Buffer.from(stdin) : undefined, env: process.env })

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
  const inputs = (seed: number) => Array.from({ length: 200 }, ((rand) => () => generate(rand))(random(seed)))
  expect(inputs(3)).toEqual(inputs(3))
  expect(inputs(3)[0]!.split("\n").slice(0, 2)).toEqual([expect.stringMatching(/^%%opts compact=[01] gap=\d*$/), "sequenceDiagram"])
  expect(inputs(3).map(summarize).filter((summary) => "error" in summary)).toEqual([])
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
