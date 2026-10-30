import { expect, test } from "bun:test"
import { normalizeSequenceMinParticipantGap } from "../../src/sequence/options"
import { parseMermaidSequenceDiagram } from "../../src/sequence/parser"
import { createSequencePlacementPlan, type SequencePlacementPlan } from "../../src/sequence/placement"
import type { SequenceDiagramRenderOptions } from "../../src/sequence/types"

type Options = Pick<SequenceDiagramRenderOptions, "compact" | "minParticipantGap">
const plan = (body: string, options?: Options) =>
  createSequencePlacementPlan(parseMermaidSequenceDiagram(`sequenceDiagram\n${body}`), options)
const centers = (placed: SequencePlacementPlan) => placed.participants.map((participant) => participant.centerX)
const size = (placed: SequencePlacementPlan) => [placed.width, placed.height]
const letters = (count: number) => "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMN".slice(0, count)
const AB = "participant A\nparticipant B\n"
const ABC = "participant A\nparticipant B\nparticipant C\n"

test("a diagram with no participants places nothing, boxes or not", () => {
  const empty = {
    width: 0,
    height: 0,
    rows: { participantHeaderTopY: 0, participantHeaderY: 0, participantRuleY: 0, lifelineStartY: 0, lifelineEndY: 0 },
    participants: [],
    groups: [],
    activations: [],
    steps: [],
  }
  expect(plan("")).toEqual(empty)
  expect(plan("box Empty\nend")).toEqual(empty)
})

test("two participants and a message: header row, rule, lifelines, then the label above its arrow", () => {
  const placed = plan("A->>B: hi")
  expect(placed).toEqual({
    width: 21,
    height: 6,
    rows: { participantHeaderTopY: 0, participantHeaderY: 0, participantRuleY: 1, lifelineStartY: 2, lifelineEndY: 5 },
    participants: [
      { participant: { id: "A", label: "A" }, centerX: 1, headerLeftX: 0, headerRightX: 2, labelLines: ["A"] },
      { participant: { id: "B", label: "B" }, centerX: 19, headerLeftX: 18, headerRightX: 20, labelLines: ["B"] },
    ],
    groups: [],
    activations: [],
    steps: [
      {
        type: "message",
        message: { from: "A", to: "B", label: "hi", style: "solid" },
        labelLines: ["hi"],
        labelX: 3,
        labelY: 3,
        arrowY: 4,
        fromX: 1,
        toX: 19,
        leftX: 1,
        rightX: 19,
        headX: 19,
        direction: 1,
        inlineLabel: undefined,
      },
    ],
  })
})

test("a header is at least 3 wide; neighbours sit half of each header plus 6 apart, or the minimum gap if wider", () => {
  const placed = plan("participant A as Alice\nparticipant B as Bartholomew Jones-Smith")
  expect(centers(placed)).toEqual([2, 23])
  expect(placed.participants.map((p) => [p.headerLeftX, p.headerRightX])).toEqual([
    [0, 4],
    [12, 34],
  ])
  expect(size(placed)).toEqual([35, 3])
  expect(placed.rows.lifelineEndY).toBe(2)
  expect(size(plan("participant A"))).toEqual([3, 3])
})

test("the minimum gap is floored and at least 1; a missing or non-finite one is 18", () => {
  expect(
    [undefined, Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY, 0, -3, 12.7, 30].map(
      normalizeSequenceMinParticipantGap,
    ),
  ).toEqual([18, 18, 18, 18, 1, 1, 12, 30])
  const gaps = [30, 12.7, 5, 0, Number.NaN].map((minParticipantGap) => centers(plan(AB, { minParticipantGap })))
  expect(gaps).toEqual([
    [1, 31],
    [1, 13],
    [1, 11],
    [1, 11],
    [1, 19],
  ])
})

test("a message between neighbours widens their gap to its label plus 6, its number included", () => {
  expect(centers(plan(`A->>B: ${letters(20)}`))).toEqual([1, 27])
  const numbered = plan(`autonumber\nA->>B: ${letters(20)}`)
  expect(centers(numbered)).toEqual([1, 30])
  expect(numbered.steps[0]).toMatchObject({ labelLines: [`1. ${letters(20)}`], labelX: 3 })
  // Either direction, any neighbouring pair, after a self message or a message past a neighbour.
  expect(centers(plan(`${AB}B->>A: ${letters(20)}`))).toEqual([1, 27])
  expect(centers(plan(`${ABC}B->>C: ${letters(20)}`))).toEqual([1, 19, 45])
  expect(centers(plan(`${ABC}A->>C: x\nA->>A: x\nA->>B: ${letters(20)}`))).toEqual([1, 27, 45])
})

test("a message past a neighbour widens no gap but the canvas, its label starting two right of the left end", () => {
  const placed = plan(`${ABC}A->>C: ${letters(40)}`)
  expect(centers(placed)).toEqual([1, 19, 37])
  expect(placed.width).toBe(3 + 40)
  expect(placed.steps[0]).toMatchObject({ labelX: 3, leftX: 1, rightX: 37 })
  const leftward = plan(`${ABC}C->>A: ${letters(40)}`)
  expect(leftward.width).toBe(3 + 40)
  expect(leftward.steps[0]).toMatchObject({ labelX: 3, fromX: 37, toX: 1 })
})

test("a head other than the default stops one cell short of the target, either way", () => {
  const head = (line: string) => {
    const step = plan(`${AB}${line}`).steps[0]!
    return step.type === "message" ? [step.direction, step.fromX, step.toX, step.leftX, step.rightX, step.headX] : []
  }
  expect(head("A->>B: x")).toEqual([1, 1, 19, 1, 19, 19])
  expect(head("A->B: x")).toEqual([1, 1, 19, 1, 19, 18])
  expect(head("A-xB: x")).toEqual([1, 1, 19, 1, 19, 18])
  expect(head("B-->>A: x")).toEqual([-1, 19, 1, 1, 19, 1])
  expect(head("B--)A: x")).toEqual([-1, 19, 1, 1, 19, 2])
})

test("a self message loops right by its label plus 4, at least 10, and pushes the next participant past the loop", () => {
  const placed = plan(`participant A\nparticipant B as Bobby\nA->>A: ${letters(20)}`)
  expect(centers(placed)).toEqual([1, 30])
  expect(placed.steps).toEqual([
    {
      type: "selfMessage",
      message: { from: "A", to: "A", label: letters(20), style: "solid" },
      labelLines: [letters(20)],
      centerX: 1,
      rightX: 25,
      topY: 3,
      bottomY: 5,
    },
  ])
  expect(size(placed)).toEqual([33, 7])
  // On the last participant the loop widens only the canvas.
  const last = plan("A->>A: hi")
  expect(last.steps[0]).toMatchObject({ rightX: 11, topY: 3, bottomY: 5 })
  expect(size(last)).toEqual([12, 7])
})

test("a note is padded 2 each side and centred over one participant, the canvas shifted right if it overflows the left", () => {
  const placed = plan("Note over A: hey")
  expect(centers(placed)).toEqual([3])
  expect(placed.steps).toEqual([
    { type: "note", note: { over: ["A"], label: "hey" }, textLines: ["  hey  "], textX: 0, textY: 4 },
  ])
  expect(size(placed)).toEqual([7, 6])
  const empty = plan("Note over A:")
  expect(centers(empty)).toEqual([2])
  expect(empty.steps[0]).toMatchObject({ textLines: ["    "], textX: 0 })
  // A note over one participant widens no gap, however long.
  const long = plan(`${AB}Note over A: ${letters(30)}`)
  expect(centers(long)).toEqual([17, 35])
  expect(long.steps[0]).toMatchObject({ textX: 0 })
  expect(long.width).toBe(37)
})

test("a note left or right of one participant starts 2 off its lifeline and widens that side's gap to its width plus 4", () => {
  const right = plan(`${AB}Note right of A: ${letters(16)}`)
  expect(centers(right)).toEqual([1, 25])
  expect(right.steps[0]).toMatchObject({ textLines: [`  ${letters(16)}  `], textX: 3 })
  const left = plan(`${AB}Note left of B: ${letters(16)}`)
  expect(centers(left)).toEqual([1, 25])
  expect(left.steps[0]).toMatchObject({ textX: 25 - 20 - 2 })
  // Left of the first participant there is no gap to widen; the canvas shifts instead.
  const first = plan(`${AB}Note left of A: hi`)
  expect(centers(first)).toEqual([8, 26])
  expect(first.steps[0]).toMatchObject({ textX: 0 })
  expect(centers(plan(`A->>B: x\nNote right of A: ${letters(16)}`))).toEqual([1, 25])
})

test("a note over two neighbours, in either order, widens their gap to its width plus 4 and centres between them", () => {
  for (const over of ["A,B", "B,A"]) {
    const placed = plan(`${AB}Note over ${over}: ${letters(21)}`)
    expect(centers(placed)).toEqual([1, 30])
    expect(placed.steps[0]).toMatchObject({ textX: 15 - 12, textY: 4 })
  }
  expect(centers(plan(`${AB}Note over A,B: hi`))).toEqual([1, 19])
  expect(centers(plan(`${ABC}Note over B,C: ${letters(21)}`))).toEqual([1, 19, 48])
  // After any other note.
  expect(centers(plan(`${AB}Note right of A: hi\nNote over A,B: ${letters(21)}`))).toEqual([1, 30])
  expect(centers(plan(`${AB}Note over B: hi\nNote over A,B: ${letters(21)}`))).toEqual([1, 30])
})

test("a note over participants apart widens no gap; it centres between the outer two, rounding left, and may overflow", () => {
  const apart = plan(`${ABC}A->>B: ${letters(13)}\nNote over A,C: ${letters(40)}`)
  expect(centers(apart)).toEqual([4, 23, 41])
  expect(apart.steps[1]).toMatchObject({ textX: 22 - 22 })
  expect(apart.width).toBe(44)
})

test("a note over no one takes its rows and places nothing (a fork defect: its text is dropped without an error)", () => {
  const placed = plan("A->>B: x\nNote over ,: ghost")
  expect(placed.steps.map((step) => step.type)).toEqual(["message"])
  expect(size(placed)).toEqual([21, 3 + 3 + 3])
})

test("a multi-line note pads every line to the widest and takes its lines plus 2 rows", () => {
  const placed = plan("Note over A: bb<br>a\nNote over A: c")
  expect(placed.steps.map((step) => (step.type === "note" ? [step.textLines, step.textY] : []))).toEqual([
    [["  bb  ", "  a   "], 4],
    [["  c  "], 8],
  ])
  expect(placed.height).toBe(3 + 4 + 3)
})

test("labels split on <br>, <br/>, <BR /> and a literal \\n, each line's end trimmed", () => {
  const placed = plan("A->>B: one<br>two<BR/>three<br />four\\nfive\nA->>B: a <br> b ")
  expect(
    placed.steps.map((step) => (step.type === "message" ? [step.labelLines, step.labelY, step.arrowY] : [])),
  ).toEqual([
    [["one", "two", "three", "four", "five"], 3, 8],
    [["a", " b"], 10, 12],
  ])
})

// subsume reads this case as redundant. Planted by hand (the rule kept one row down whatever the label's
// height), this is the only case that fails.
test("a participant's lines set the header's height: the rule drops below the tallest", () => {
  const placed = plan("participant A as Web<br/>Server\nA->>B: x")
  expect(placed.rows).toEqual({
    participantHeaderTopY: 0,
    participantHeaderY: 0,
    participantRuleY: 2,
    lifelineStartY: 3,
    lifelineEndY: 6,
  })
  expect(placed.participants[0]).toMatchObject({ labelLines: ["Web", "Server"], headerLeftX: 0, headerRightX: 5 })
  expect(centers(placed)).toEqual([3, 21])
})

test("compact: headers as wide as their label, no rule row, and a one-line label inlined into its arrow when it fits", () => {
  const placed = plan("A->>B: hi", { compact: true })
  expect(placed.rows).toEqual({
    participantHeaderTopY: 0,
    participantHeaderY: 0,
    participantRuleY: 0,
    lifelineStartY: 1,
    lifelineEndY: 3,
  })
  expect(placed.participants.map((p) => [p.centerX, p.headerLeftX, p.headerRightX])).toEqual([
    [1, 1, 1],
    [19, 19, 19],
  ])
  expect(placed.steps[0]).toMatchObject({ inlineLabel: " hi ", labelX: 8, labelY: 2, arrowY: 2 })
  expect(size(placed)).toEqual([20, 4])
  const tall = plan("participant A as Web<br>Server\nA->>B: x", { compact: true })
  expect(tall.rows).toMatchObject({ participantRuleY: 1, lifelineStartY: 2 })
})

test("compact inlines a label only when it and a blank each side fit 3 inside the arrow, on one line, between two lifelines", () => {
  const inline = (body: string) => {
    const step = plan(body, { compact: true }).steps[0]!
    return step.type === "message" ? [step.inlineLabel, step.labelX, step.labelY, step.arrowY] : [step.type]
  }
  expect(inline(`${ABC}A->>C: ${letters(31)}`)).toEqual([` ${letters(31)} `, 2, 2, 2])
  expect(inline(`${ABC}A->>C: ${letters(32)}`)).toEqual([undefined, 3, 2, 3])
  expect(inline("A->>B: a<br>b")).toEqual([undefined, 3, 2, 4])
  expect(inline("A->>A: hi")).toEqual(["selfMessage"])
  expect(plan("A->>B: a<br>b", { compact: true }).height).toBe(2 + 4)
  expect(plan("A->>A: hi", { compact: true }).height).toBe(2 + 4)
})

test("a box frames its members' headers 2 out, the canvas shifted right to fit it, and moves the header rows down one", () => {
  const placed = plan("box Team\nparticipant A as Alice\nparticipant B\nend\nparticipant C")
  expect(centers(placed)).toEqual([4, 22, 40])
  expect(placed.groups).toEqual([
    { group: { label: "Team", participantIds: ["A", "B"] }, labelText: " Team ", leftX: 0, rightX: 25 },
  ])
  expect(placed.rows).toEqual({
    participantHeaderTopY: 1,
    participantHeaderY: 1,
    participantRuleY: 2,
    lifelineStartY: 3,
    lifelineEndY: 3,
  })
  expect(size(placed)).toEqual([42, 5])
  const step = plan("box T\nA->>B: hi\nend")
  expect(step.rows.lifelineEndY).toBe(6)
  expect(step.height).toBe(4 + 3 + 1)
  expect(step.steps[0]).toMatchObject({ labelY: 4, arrowY: 5 })
})

test("a box widens evenly to fit its label plus 4, and a participant after it moves right to clear it by 2", () => {
  const placed = plan("box Customer facing services\nparticipant A\nend\nparticipant B as Bobby\nparticipant C")
  expect(centers(placed)).toEqual([14, 34, 52])
  expect(placed.groups[0]).toMatchObject({ labelText: " Customer facing services ", leftX: 0, rightX: 29 })
  expect(placed.width).toBe(54)
  // On the right of the boundary: the box starts 2 clear of the header before it.
  const after = plan("participant A as Alice\nbox Payments and ledger teams\nparticipant B\nend")
  expect(centers(after)).toEqual([2, 22])
  expect(after.groups[0]).toMatchObject({ leftX: 7, rightX: 37 })
  expect(after.width).toBe(38)
})

test("each boundary is cleared in turn, past ones a box borders without overlap and ones it does not border", () => {
  const placed = plan(
    "box\nparticipant A\nend\nparticipant B\nparticipant C\nbox Payments and ledger teams\nparticipant D\nend",
  )
  expect(centers(placed)).toEqual([3, 21, 39, 58])
  expect(placed.groups.map((group) => [group.leftX, group.rightX])).toEqual([
    [0, 6],
    [43, 73],
  ])
  expect(size(placed)).toEqual([74, 5])
})

test("a box grows around the steps wholly among its members and ignores a step that leaves it", () => {
  const placed = plan(
    `box T\n${AB}end\nparticipant C\nA->>C: ${letters(30)}\nNote left of A: hi\nNote right of B: hi\nA->>B: x`,
  )
  expect(centers(placed)).toEqual([10, 28, 46])
  expect(placed.groups[0]).toMatchObject({ leftX: 0, rightX: 37 })
  expect(placed.width).toBe(48)
  // A message past a neighbour, wholly inside, counts.
  const wide = plan(`box T\n${ABC}end\nA->>C: ${letters(40)}`)
  expect(wide.groups[0]).toMatchObject({ leftX: 0, rightX: 46 })
  expect(wide.width).toBe(47)
  // A box whose participants were all elsewhere draws nothing and keeps the headers on row 0.
  const none = plan("box Empty\nend\nparticipant A")
  expect(none.groups).toEqual([])
  expect(none.rows.participantHeaderTopY).toBe(0)
})

test("a loop frames every participant 3 out, its label at least, with walls between its rows", () => {
  const placed = plan("loop every 5s\nA->>B: hi\nend")
  expect(centers(placed)).toEqual([3, 21])
  const frame = { leftX: 0, rightX: 24 }
  expect(placed.steps.filter((step) => step.type === "fragment")).toEqual([
    {
      type: "fragment",
      fragment: { kind: "loop", label: "every 5s" },
      labelText: " ↻ loop: every 5s ",
      bounds: frame,
      y: 3,
      wallsBefore: undefined,
    },
    {
      type: "fragment",
      fragment: { kind: "end", label: "loop" },
      labelText: "",
      bounds: frame,
      y: 8,
      wallsBefore: { bounds: frame, startY: 4, endY: 7 },
    },
  ])
  expect(placed.steps[1]).toMatchObject({ labelY: 5, arrowY: 6 })
  expect(size(placed)).toEqual([25, 10])
  const left = plan(`${AB}loop x\nNote left of A: hi\nend`)
  expect(centers(left)).toEqual([9, 27])
  expect(left.steps[0]).toMatchObject({ bounds: { leftX: 0, rightX: 30 } })
  expect(left.width).toBe(31)
  const long = plan(`loop ${letters(40)}\nA->>B: x\nend`)
  expect(long.steps[0]).toMatchObject({ bounds: { leftX: 0, rightX: 2 + 50 + 1 } })
  expect(long.width).toBe(54)
})

test("an else splits its alt's walls: each section's walls run from the divider above to the row before", () => {
  const placed = plan("alt ok\nA->>B: x\nelse\nB-->>A: y\nend")
  const frame = { leftX: 0, rightX: 24 }
  expect(
    placed.steps.flatMap((step) => (step.type === "fragment" ? [[step.labelText, step.y, step.wallsBefore]] : [])),
  ).toEqual([
    [" alt: ok ", 3, undefined],
    [" else:  ", 8, { bounds: frame, startY: 4, endY: 7 }],
    ["", 13, { bounds: frame, startY: 9, endY: 12 }],
  ])
  expect(placed.height).toBe(15)
  // What follows the else still widens the frame.
  const after = plan("alt ok\nA->>B: x\nelse\nNote right of B: hi\nend")
  expect(after.steps[0]).toMatchObject({ bounds: { leftX: 0, rightX: 29 } })
  expect(after.width).toBe(30)
})

test("a nested frame steps in 1 a side, and grows its parent to stay 1 inside it", () => {
  const nested = plan("alt a\nloop b\nA->>B: x\nend\nend")
  expect(nested.steps.flatMap((step) => (step.type === "fragment" ? [[step.fragment.kind, step.bounds]] : []))).toEqual(
    [
      ["alt", { leftX: 0, rightX: 24 }],
      ["loop", { leftX: 1, rightX: 23 }],
      ["end", { leftX: 1, rightX: 23 }],
      ["end", { leftX: 0, rightX: 24 }],
    ],
  )
  // A note past the last lifeline pushes the inner frame 1 past it and the outer 1 past that.
  const pushed = plan(`${AB}alt a\nloop b\nNote right of B: hi\nend\nend`)
  expect(pushed.steps.flatMap((step) => (step.type === "fragment" ? [step.bounds.rightX] : []))).toEqual([
    30, 29, 29, 30,
  ])
  expect(pushed.width).toBe(31)
  const leftward = plan(`${AB}alt a\nloop b\nNote left of A: hi\nend\nend`)
  expect(leftward.steps.flatMap((step) => (step.type === "fragment" ? [step.bounds.leftX] : []))).toEqual([0, 1, 1, 0])
  expect(centers(leftward)).toEqual([10, 28])
})

// subsume reads this case as redundant: it cannot swap the row an activation opens on. Planted by hand (a +
// opening at the step's top row, for a message or a self message), this is the only case that fails.
test("a + on a message activates its receiver from the arrow's row until a - from it closes it there", () => {
  expect(plan("A->>+B: go\nB-->>-A: done").activations).toEqual([
    { participant: "B", centerX: 19, startY: 4, endY: 7, depth: 0 },
  ])
  expect(plan("A->>+A: x").activations).toEqual([{ participant: "A", centerX: 1, startY: 5, endY: 6, depth: 0 }])
})

// subsume reads this case as redundant: it does not delete statements. Planted by hand (the receiver's last
// arrow not recorded), this is the only case that fails.
test("an activate statement starts at the participant's last arrow, or the next step's row if it has none", () => {
  expect(plan("activate A\nA->>B: x\ndeactivate A").activations).toEqual([
    { participant: "A", centerX: 1, startY: 3, endY: 4, depth: 0 },
  ])
  expect(plan("A->>B: x\nNote over B: n\nactivate B").activations).toEqual([
    { participant: "B", centerX: 19, startY: 4, endY: 8, depth: 0 },
  ])
})

test("activations nest by depth; one left open closes at the lifeline's end; a deactivate with none open does nothing", () => {
  expect(plan("activate A\nactivate A\nA->>B: x\ndeactivate A").activations).toEqual([
    { participant: "A", centerX: 1, startY: 3, endY: 4, depth: 1 },
    { participant: "A", centerX: 1, startY: 3, endY: 5, depth: 0 },
  ])
  expect(plan("activate A").activations).toEqual([{ participant: "A", centerX: 1, startY: 2, endY: 2, depth: 0 }])
  expect(plan("deactivate A\nA->>B: x").activations).toEqual([])
})
