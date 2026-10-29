import { BoxRenderable, parseColor, TextRenderable, type MarkdownCodeBlockRenderer, type StyledText } from "@opentui/core"
import { createTestRenderer } from "@opentui/core/testing"
import { expect, test } from "bun:test"
import { drawFlowchartDiagramGrid } from "../src/flowchart/drawing"
import { parseMermaidFlowchartDiagram } from "../src/flowchart/parser"
import { renderGridStyledText, resolveFlowchartStyleColors } from "../src/flowchart/style"
import { drawGanttDiagramGrid } from "../src/gantt/drawing"
import { parseMermaidGanttDiagram } from "../src/gantt/parser"
import { renderGanttGridStyledText } from "../src/gantt/render-grid"
import { resolveGanttStyleColors } from "../src/gantt/style"
import type { GanttDiagramRenderOptions } from "../src/gantt/types"
import { drawGitGraphDiagramGrid } from "../src/gitgraph/drawing"
import { parseMermaidGitGraphDiagram } from "../src/gitgraph/parser"
import { renderGitGraphGridStyledText } from "../src/gitgraph/render-grid"
import { resolveGitGraphStyleColors } from "../src/gitgraph/style"
import { createMermaidCodeBlockRenderer, createMermaidMarkdownRenderer, type MermaidMarkdownRendererOptions } from "../src/markdown"
import { drawSequenceDiagramGrid } from "../src/sequence/drawing"
import { parseMermaidSequenceDiagram } from "../src/sequence/parser"
import { renderSequenceGridStyledText } from "../src/sequence/render-grid"
import { resolveSequenceStyleColors } from "../src/sequence/style"
import { drawStateDiagramGrid } from "../src/state/drawing"
import { parseMermaidStateDiagram } from "../src/state/parser"
import { renderStateGridStyledText } from "../src/state/render-grid"
import { resolveStateStyleColors } from "../src/state/style"
import { drawTimelineDiagramGrid } from "../src/timeline/drawing"
import { parseMermaidTimelineDiagram } from "../src/timeline/parser"
import { renderTimelineGridStyledText } from "../src/timeline/render-grid"
import { resolveTimelineStyleColors } from "../src/timeline/style"

type CodeToken = Parameters<MarkdownCodeBlockRenderer>[0]
type Palette = NonNullable<MermaidMarkdownRendererOptions["colors"]>

const WIDTH = 60
const setup = await createTestRenderer({ width: WIDTH, height: 12, useThread: false })
const renderer = setup.renderer
renderer.setMaxListeners(64)

const token = (text: string, lang = "mermaid") => ({ type: "code", raw: "```" + lang + "\n" + text + "\n```", text, lang }) as CodeToken

function call(render: MarkdownCodeBlockRenderer, text: string, id?: string, lang?: string) {
  const fallback = id ? new TextRenderable(renderer, { id, content: "" }) : null
  return render(token(text, lang), { syntaxStyle: undefined as never, conceal: false, concealCode: false, defaultRender: () => fallback })
}

/** Every cell's text, colour and background, comparable by value. */
const cells = (text: StyledText | TextRenderable) =>
  (text instanceof TextRenderable ? text.chunks : text.chunks).map((chunk) => [chunk.text, chunk.fg?.toInts(), chunk.bg?.toInts(), chunk.attributes])
const lineCount = (text: StyledText) => text.chunks.filter((chunk) => chunk.text === "\n").length + 1

const SAMPLES = {
  flowchart: "flowchart LR\n  subgraph G [Group]\n    A[Start] -->|go| B[(Store)]\n  end",
  state:
    "stateDiagram-v2\n  [*] --> Idle\n  Idle --> Busy: start\n  state Busy {\n    [*] --> Work\n  }\n  state pick <<choice>>\n  Busy --> pick\n  pick --> [*]\n  note right of Idle: waits",
  sequence: "sequenceDiagram\n  box Team\n  participant A\n  participant B\n  end\n  A->>B: ask\n  B-->>A: answer\n  loop again\n    A->>B: more\n  end\n  Note over A: thinking",
  gantt:
    "gantt\n  title Plan\n  dateFormat YYYY-MM-DD\n  section One\n  Done task :done, a1, 2024-01-01, 2d\n  Active task :active, a2, after a1, 2d\n  Crit task :crit, a3, after a2, 2d\n  Plain task :a4, after a3, 2d",
  gitGraph: 'gitGraph\n  commit\n  commit type: HIGHLIGHT\n  commit type: REVERSE\n  branch dev\n  commit\n  checkout main\n  merge dev\n  commit tag: "v1"',
  timeline: "timeline\n  title History\n  section Early\n    2001 : One : Two\n    2002 : Three",
} as const
type Kind = keyof typeof SAMPLES

/** The diagram as its family draws and colours it, with the palette mapped as the renderer is meant to map it. */
function expected(kind: Kind, source: string, p: Palette, o: { compact?: boolean; layoutMaxWidth?: number; gantt?: GanttDiagramRenderOptions } = {}): StyledText {
  const c = (...keys: Array<keyof Palette>) => {
    const key = keys.find((k) => p[k] !== undefined)
    return key === undefined ? undefined : parseColor(p[key]!)
  }
  const compact = o.compact ?? true
  const layoutMaxWidth = o.layoutMaxWidth ?? WIDTH
  switch (kind) {
    case "flowchart":
      return renderGridStyledText(
        drawFlowchartDiagramGrid(parseMermaidFlowchartDiagram(source), { compact, layoutMaxWidth }),
        resolveFlowchartStyleColors({
          node: c("boxText", "primary"),
          nodeBorder: c("boxBorder", "muted"),
          database: c("boxText", "primary"),
          databaseBorder: c("boxBorder", "muted"),
          edge: c("line", "secondary"),
          label: c("text"),
          group: c("group", "muted"),
          groupLabel: c("groupText", "group", "muted"),
        }),
        { label: c("labelBackground") },
      )
    case "gitGraph":
      return renderGitGraphGridStyledText(
        drawGitGraphDiagramGrid(parseMermaidGitGraphDiagram(source)),
        resolveGitGraphStyleColors({ primary: c("primary"), secondary: c("secondary"), muted: c("muted"), warning: c("warning"), text: c("text") }),
      )
    case "gantt":
      return renderGanttGridStyledText(
        drawGanttDiagramGrid(parseMermaidGanttDiagram(source), { ...o.gantt, layoutMaxWidth }),
        resolveGanttStyleColors({
          title: c("text"),
          axis: c("muted"),
          background: c("background"),
          section: c("secondary"),
          task: c("primary"),
          active: c("primary"),
          critical: c("warning"),
          done: c("muted"),
        }),
      )
    case "sequence":
      return renderSequenceGridStyledText(
        drawSequenceDiagramGrid(parseMermaidSequenceDiagram(source), { compact }),
        resolveSequenceStyleColors({
          participant: c("primary"),
          lifeline: c("muted"),
          group: c("secondary"),
          request: c("request", "primary"),
          response: c("response", "primary"),
          fragment: c("secondary"),
          fragmentLabelBg: c("background"),
          note: c("note", "warning"),
          noteBg: c("noteBackground", "background"),
        }),
      )
    case "state":
      return renderStateGridStyledText(
        drawStateDiagramGrid(parseMermaidStateDiagram(source), { layoutMaxWidth }),
        resolveStateStyleColors({
          state: c("boxText", "primary"),
          stateBorder: c("boxBorder", "primary"),
          composite: c("group", "muted"),
          compositeLabel: c("groupText", "group", "muted"),
          transition: c("line", "secondary"),
          label: c("text"),
          noteBorder: c("noteBorder", "warning"),
          noteText: c("noteText", "warning"),
          noteConnector: c("noteConnector", "muted"),
          start: c("marker", "muted"),
          end: c("marker", "muted"),
          choice: c("marker", "secondary"),
        }),
        { label: c("labelBackground") },
      )
    case "timeline":
      return renderTimelineGridStyledText(
        drawTimelineDiagramGrid(parseMermaidTimelineDiagram(source)),
        resolveTimelineStyleColors({ title: c("text"), section: c("secondary"), period: c("warning"), spine: c("muted"), event: c("primary") }),
      )
  }
}

const BASE: Palette = { text: "#010101", primary: "#020202", secondary: "#030303", muted: "#040404", warning: "#050505", background: "#060606" }
const FULL: Palette = {
  ...BASE,
  request: "#070707",
  response: "#080808",
  note: "#090909",
  noteBackground: "#0a0a0a",
  boxText: "#0b0b0b",
  boxBorder: "#0c0c0c",
  line: "#0d0d0d",
  labelBackground: "#0e0e0e",
  group: "#0f0f0f",
  groupText: "#101010",
  marker: "#111111",
  noteBorder: "#121212",
  noteText: "#131313",
  noteConnector: "#141414",
}
const GROUPED: Palette = { ...BASE, group: "#0f0f0f" }

for (const [name, palette] of [["the full palette", FULL], ["only the base colours and a group colour, the rest falling back", GROUPED]] as const) {
  test(`each kind is drawn as its family draws it, one row down, as tall as its text, coloured from ${name}`, () => {
    const render = createMermaidCodeBlockRenderer(renderer, { colors: palette })
    for (const kind of Object.keys(SAMPLES) as Kind[]) {
      const diagram = call(render, SAMPLES[kind]) as TextRenderable
      const want = expected(kind, SAMPLES[kind], palette)
      expect(diagram.constructor.name).toBe("StaticDiagramRenderable")
      expect(cells(diagram)).toEqual(cells(want))
      expect([kind, diagram.height, diagram.marginTop]).toEqual([kind, lineCount(want), 1])
    }
  })
}

/** 118 columns wide: it folds at a layout width of 120 and fits at 121. */
const BOUNDARY = `flowchart LR\n  A[${"a".repeat(52)}] --> B[${"b".repeat(53)}]`

test("the layout width is the configured one, 120 by default, never wider than the terminal nor narrower than one column", async () => {
  const render = (options: MermaidMarkdownRendererOptions, on = renderer) => cells(call(createMermaidCodeBlockRenderer(on, options), BOUNDARY) as TextRenderable)
  const at = (layoutMaxWidth: number) => cells(expected("flowchart", BOUNDARY, {}, { layoutMaxWidth }))
  expect(at(120)).not.toEqual(at(121))
  expect(render({ layoutMaxWidth: 500 })).toEqual(at(WIDTH))
  expect(render({ layoutMaxWidth: 0 })).toEqual(at(1))
  const wide = await createTestRenderer({ width: 200, height: 4, useThread: false })
  expect(render({}, wide.renderer)).toEqual(at(120))
  expect(render({ layoutMaxWidth: 121.9 }, wide.renderer)).toEqual(at(121))
  expect(render({ layoutMaxWidth: 120 }, wide.renderer)).toEqual(at(120))
  expect(render({ layoutMaxWidth: 500 }, wide.renderer)).toEqual(at(200))
  wide.renderer.destroy()
  const fitting = await createTestRenderer({ width: 121, height: 4, useThread: false })
  expect(render({ layoutMaxWidth: 500 }, fitting.renderer)).toEqual(at(121))
  fitting.renderer.destroy()
})

test("compact spacing is on unless turned off, gantt options pass through, and options given as a function are read at each render", () => {
  let options: MermaidMarkdownRendererOptions = {}
  const render = createMermaidCodeBlockRenderer(renderer, () => options)
  for (const [kind, source] of [["flowchart", "flowchart LR\n  A[alpha] --> B[beta]"], ["sequence", SAMPLES.sequence]] as const) {
    expect(cells(expected(kind, source, {}, { compact: false }))).not.toEqual(cells(expected(kind, source, {})))
    options = { compact: false }
    expect(cells(call(render, source) as TextRenderable)).toEqual(cells(expected(kind, source, {}, { compact: false })))
    options = {}
    expect(cells(call(render, source) as TextRenderable)).toEqual(cells(expected(kind, source, {})))
  }
  options = { gantt: { style: "block", sections: "compact" } }
  expect(cells(expected("gantt", SAMPLES.gantt, {}, { gantt: options.gantt }))).not.toEqual(cells(expected("gantt", SAMPLES.gantt, {})))
  expect(cells(call(render, SAMPLES.gantt) as TextRenderable)).toEqual(cells(expected("gantt", SAMPLES.gantt, {}, { gantt: options.gantt })))
})

test("a block that is no diagram this renderer draws is left to the default renderer", () => {
  const render = createMermaidCodeBlockRenderer(renderer)
  for (const text of ["pie\n  \"a\" : 1", "classDiagram\n  A <|-- B", ""]) expect(call(render, text, "x")).toBeUndefined()
})

test("a diagram too large for the canvas is left to the default renderer, whole or as a streaming tail", () => {
  const render = createMermaidCodeBlockRenderer(renderer)
  const huge = `gitGraph\n  commit id: "${"x".repeat(260_000)}"`
  expect(call(render, huge, "big")).toBeUndefined()
  expect(call(render, `${huge}\n  frobnicate`, "big2")).toBeUndefined()
})

test("a syntax error on the last written line past the second draws the lines before it, as a block still streaming in; one earlier is left to the default renderer", () => {
  const render = createMermaidCodeBlockRenderer(renderer)
  expect(call(render, "gitGraph\n  frobnicate")).toBeUndefined()
  expect(call(render, "gitGraph\n  commit\n  frobnicate\n  commit")).toBeUndefined()
  expect(cells(call(render, "gitGraph\n  commit\n  frobnicate") as TextRenderable)).toEqual(cells(expected("gitGraph", "gitGraph\n  commit", {})))
  const partial = call(render, "gitGraph\n  commit\n  commit\n  frobnicate\n  \n") as TextRenderable
  const want = expected("gitGraph", "gitGraph\n  commit\n  commit", {})
  expect(cells(partial)).toEqual(cells(want))
  expect([partial.height, partial.marginTop]).toEqual([lineCount(want), 1])
  expect(call(render, "sequenceDiagram\n\n  bogus")).toBeUndefined()
})

test("while a block streams, a broken update keeps the last diagram that drew for that block, of the same kind, until the block is destroyed and not replaced", async () => {
  const render = createMermaidCodeBlockRenderer(renderer)
  const good = cells(call(render, "gitGraph\n  commit\n  commit\n  commit", "s1") as TextRenderable)
  expect(cells(call(render, "gitGraph\n  commit\n  frobnicate\n  commit", "s1") as TextRenderable)).toEqual(good)
  // The reused diagram is claimed again, so the block keeps it through a further broken update.
  expect(cells(call(render, "gitGraph\n  frobnicate", "s1") as TextRenderable)).toEqual(good)
  expect(call(render, "sequenceDiagram\n  A->>B: hi\n  A-xx B\n  A->>B: x", "s1")).toBeUndefined()
  // Without a block id nothing is remembered, and another block's diagram is not borrowed.
  call(render, "gitGraph\n  commit")
  expect(call(render, "gitGraph\n  frobnicate")).toBeUndefined()
  expect(call(render, "gitGraph\n  frobnicate", "s2")).toBeUndefined()
  // A streaming tail that draws is remembered too.
  const tail = cells(call(render, "gitGraph\n  commit\n  commit\n  frobnicate", "s3") as TextRenderable)
  expect(cells(call(render, "gitGraph\n  frobnicate", "s3") as TextRenderable)).toEqual(tail)

  const first = call(render, "gitGraph\n  commit", "d1")!
  first.destroy()
  await Promise.resolve()
  expect(call(render, "gitGraph\n  frobnicate", "d1")).toBeUndefined()
  // Reconciliation destroys the old block, then synchronously makes its replacement from the remembered diagram.
  const kept = cells(call(render, "gitGraph\n  commit\n  commit", "d3") as TextRenderable)
  call(render, "gitGraph\n  frobnicate", "d3")
  const replaced = call(render, "gitGraph\n  frobnicate", "d3")!
  replaced.destroy()
  const replacement = call(render, "gitGraph\n  frobnicate", "d3") as TextRenderable
  await Promise.resolve()
  expect(cells(replacement)).toEqual(kept)
  expect(cells(call(render, "gitGraph\n  frobnicate", "d3") as TextRenderable)).toEqual(kept)
  const older = call(render, "gitGraph\n  commit", "d2")!
  const newer = cells(call(render, "gitGraph\n  commit\n  commit", "d2") as TextRenderable)
  older.destroy()
  await Promise.resolve()
  expect(cells(call(render, "gitGraph\n  frobnicate", "d2") as TextRenderable)).toEqual(newer)
})

test("the markdown renderer hands mermaid blocks to the diagram renderer and leaves other languages alone", () => {
  const renderNode = createMermaidMarkdownRenderer(renderer, { colors: FULL })
  const diagram = renderNode(token(SAMPLES.timeline), { syntaxStyle: undefined as never, conceal: false, concealCode: false, defaultRender: () => null }) as TextRenderable
  expect(cells(diagram)).toEqual(cells(expected("timeline", SAMPLES.timeline, FULL)))
  expect(renderNode(token("x = 1", "js"), { syntaxStyle: undefined as never, conceal: false, concealCode: false, defaultRender: () => null })).toBeUndefined()
})

test("a wide diagram fills its row unwrapped and unselectable, pans with a left-button drag, ignores other buttons, and keeps its left-button events from its parent", async () => {
  const seen: string[] = []
  const outer = new BoxRenderable(renderer, {
    width: 24,
    height: 4,
    flexDirection: "row",
    focusable: true,
    onMouseScroll: (event) => void seen.push(`scroll ${event.scroll!.direction}`),
    onMouseDown: (event) => void seen.push(`down ${event.button}`),
    onMouseUp: (event) => void seen.push(`up ${event.button}`),
    onMouseDrag: (event) => void seen.push(`drag ${event.button}`),
    onMouseDragEnd: (event) => void seen.push(`dragend ${event.button}`),
  })
  const diagram = call(createMermaidCodeBlockRenderer(renderer), `gitGraph\n  commit id: "${"w".repeat(60)}"\n  commit id: "${"v".repeat(60)}"`) as TextRenderable
  outer.add(diagram)
  renderer.root.add(outer)
  let cleared = 0
  const clear = renderer.clearSelection.bind(renderer)
  renderer.clearSelection = () => {
    cleared += 1
    clear()
  }
  await setup.renderOnce()
  expect([diagram.width, diagram.height, diagram.selectable]).toEqual([24, 2, false])
  const frame = setup.captureCharFrame().split("\n")
  expect([frame[1], frame[2]].map((row) => row.trimEnd())).toEqual(["●  " + "w".repeat(21), "●  " + "v".repeat(21)])
  await setup.mockMouse.drag(12, 1, 7, 1)
  await setup.renderOnce()
  expect([diagram.scrollX, cleared]).toEqual([5, 1])
  await setup.mockMouse.drag(7, 1, 9, 1)
  await setup.renderOnce()
  expect(diagram.scrollX).toBe(3)
  expect(outer.focused).toBe(false)
  // Press, drag and drag end stop at the diagram; the release that ends a drag still reaches the parent (OpenTUI routes it past the diagram).
  expect(seen).toEqual(["up 0", "up 0"])
  seen.length = 0
  await setup.mockMouse.pressDown(10, 1)
  await setup.mockMouse.release(10, 1)
  expect([seen, diagram.scrollX, cleared]).toEqual([[], 3, 3])
  await setup.mockMouse.drag(12, 1, 2, 1, 2)
  await setup.renderOnce()
  expect([diagram.scrollX, cleared]).toEqual([3, 3])
  expect(seen.filter((event) => !event.startsWith("drag"))).toEqual(["down 2", "up 2"])
  seen.length = 0
  for (const direction of ["left", "right", "up", "down"] as const) await setup.mockMouse.scroll(5, 1, direction)
  expect(seen).toEqual(["scroll up", "scroll down"])
  renderer.clearSelection = clear
  renderer.root.remove(outer)
})
