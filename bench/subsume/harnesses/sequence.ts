// pinned.py's harness for merman's sequence family: random diagrams, each summarized as its parse, its
// placement plan and its drawn text, flattened to one key per value. An input's `%%opts` line (a comment
// to the parser) carries the render options. It loads the package from `cli.ts`'s root (the planted copy).
import { packageRoot, runHarness } from "./cli"

const { drawSequenceDiagramGrid } = await import(`${packageRoot}/src/sequence/drawing.ts`)
const { parseMermaidSequenceDiagram } = await import(`${packageRoot}/src/sequence/parser.ts`)
const { createSequencePlacementPlan } = await import(`${packageRoot}/src/sequence/placement.ts`)
const { renderSequenceGridText } = await import(`${packageRoot}/src/sequence/render-grid.ts`)

const WORDS = ["a", "go", "ok", "hey", "send", "reply", "a long label", "Customer facing", "x<br>yy", "one<br>two<br>3"]
const ARROWS = ["->>", "-->>", "->", "-->", "-x", "--x", "-)", "--)"]

export function generate(rand: () => number): string {
  const pick = <T>(items: readonly T[]) => items[Math.floor(rand() * items.length)]!
  const chance = (p: number) => rand() < p
  const ids = ["A", "B", "C", "D"].slice(0, 1 + Math.floor(rand() * 4))
  const label = () => (chance(0.15) ? "" : chance(0.2) ? "w".repeat(Math.floor(rand() * 40)) : pick(WORDS))
  const lines = [`%%opts compact=${chance(0.3) ? 1 : 0} gap=${chance(0.2) ? Math.floor(rand() * 30) : ""}`]
  lines.push("sequenceDiagram")
  // Boxes come first: each declares a run of participants.
  let declared = 0
  while (declared < ids.length && chance(0.4)) {
    const take = 1 + Math.floor(rand() * (ids.length - declared))
    lines.push(`box ${chance(0.5) ? pick(["", "Team", "red Ops", "Payments and ledger teams"]) : label()}`)
    for (const id of ids.slice(declared, declared + take))
      lines.push(`participant ${id}${chance(0.3) ? ` as ${label() || id}` : ""}`)
    lines.push("end")
    declared += take
  }
  for (const id of ids.slice(declared))
    if (chance(0.5)) lines.push(`participant ${id}${chance(0.3) ? ` as ${label() || id}` : ""}`)
  const open: string[] = []
  for (let n = Math.floor(rand() * 9); n > 0; n--) {
    const r = rand()
    if (r < 0.45) {
      const from = pick(ids)
      const to = chance(0.15) ? from : pick(ids)
      lines.push(`${from}${pick(ARROWS)}${pick(["", "", "", "+", "-"])}${to}: ${label()}`)
    } else if (r < 0.6) {
      const over = chance(0.4) ? `${pick(ids)},${pick(ids)}` : pick(ids)
      lines.push(`Note ${over.includes(",") ? "over" : pick(["over", "left of", "right of"])} ${over}: ${label()}`)
    } else if (r < 0.7) {
      lines.push(`${pick(["activate", "deactivate"])} ${pick(ids)}`)
    } else if (r < 0.78) {
      lines.push(pick(["autonumber", "autonumber 10 5", "autonumber 3"]))
    } else if (r < 0.88 && open.length < 3) {
      const kind = pick(["alt", "loop"])
      open.push(kind)
      lines.push(`${kind} ${label() || "x"}`)
    } else if (open.length > 0) {
      if (open[open.length - 1] === "alt" && chance(0.5)) lines.push(`else ${label()}`)
      else {
        open.pop()
        lines.push("end")
      }
    }
  }
  while (open.pop()) lines.push("end")
  return lines.join("\n")
}

function flatten(value: unknown, prefix: string, out: Record<string, unknown>): void {
  if (value !== null && typeof value === "object") {
    for (const [key, item] of Object.entries(value)) flatten(item, prefix ? `${prefix}.${key}` : key, out)
  } else if (value !== undefined) {
    out[prefix] = value
  }
}

export function summarize(input: string): Record<string, unknown> {
  try {
    const opts = input.match(/^%%opts compact=(\d) gap=(\d*)$/m)
    const options = {
      compact: opts?.[1] === "1",
      minParticipantGap: opts?.[2] ? Number(opts[2]) : undefined,
    }
    const diagram = parseMermaidSequenceDiagram(input)
    const out: Record<string, unknown> = {}
    flatten(diagram, "diagram", out)
    flatten(createSequencePlacementPlan(diagram, options), "plan", out)
    out.text = renderSequenceGridText(drawSequenceDiagramGrid(diagram, options))
    return out
  } catch (error) {
    return { error: String(error) }
  }
}

if (import.meta.main) await runHarness(generate, summarize)
