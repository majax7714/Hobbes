import { expect, test } from "bun:test"
import { createStateDiagramDrawing } from "../../src/state/drawing"
import { parseMermaidStateDiagram } from "../../src/state/parser"
import { drawn, summary } from "./drawing-summary"

// Each transition as drawn: its ends, its route's kind, its corners and its label's top left.
const routes = (body: string) =>
  Object.entries(summary(createStateDiagramDrawing(parseMermaidStateDiagram(`stateDiagram-v2\n${body}`)))).flatMap(
    ([key, value]) => (key.startsWith("route:") ? [value] : []),
  )

test("on one row a transition runs from a tee on the source's facing side to an arrow at the target, its label centred above", () => {
  expect(routes("A --> B : go")).toEqual(["A>B horizontal-forward 4,1 17,1 @10,0"])
  expect(routes("direction RL\nA --> B")).toEqual(["A>B horizontal-forward 18,1 5,1"])
})

test("top to bottom a transition runs straight down the column, its label two right of it on the row after the source", () => {
  expect(routes("direction TB\nA --> B : go")).toEqual(["A>B vertical 2,2 2,6 @4,4"])
  expect(routes("direction BT\nA --> B")).toEqual(["A>B vertical 2,7 2,3"])
})

test("left to right, a transition back runs under the row, the shorter on the higher lane, 3 apart, into the target's second cell", () => {
  expect(routes("A --> B\nB --> C\nC --> A\nB --> A")).toEqual([
    "A>B horizontal-forward 4,1 17,1",
    "B>C horizontal-forward 22,1 35,1",
    "C>A bottom-feedback 38,2 38,9 1,9 1,3",
    "B>A bottom-feedback 20,2 20,6 1,6 1,3",
  ])
})

test("a self transition leaves the bottom a third in and comes back up two thirds in; another loops 3 lower and 4 wider", () => {
  expect(routes('state "Longer" as A\nA --> A\nA --> A')).toEqual([
    "A>A self 3,2 3,4 7,4 7,3",
    "A>A self 3,2 3,7 11,7 11,3",
  ])
})

// The cases below were found by planting each fault the cases above miss into a copy of routing.ts and searching random
// state diagrams for one it changes (`bench/subsume/pinned.py` with the state harnesses), each input then shrunk and
// the fewest kept that tell every such fault apart. Each asserts only the routes (`drawing-summary.ts`) those faults
// change and, where they change the rows, the count of rows; for the faults that change no route, only drawn rows, the
// fewest rows that tell them apart (each such fault planted, its changed rows read). All as drawn today: pinned as
// observed, not derived by hand. The harnesses keep no input that shows a known wrong drawing (`state-defects.ts`:
// composites crossing, a state outside its composite, a route through a state), so none of these does. Cases above that
// are redundant against these stay as the readable statement of each rule (Max, 2026-10-30).
test("pinned as observed: self loops", () => {
  expect(
    drawn(
      'state P0 {\n}\nstate "A long composite title" as P1 {\n}\nstate ch <<choice>>\nch --> ch : retry\nch --> ch : a<br>b',
    ),
  ).toMatchObject({
    "route:0": "ch>ch self 1,2 4,2 4,4 0,4 0,2 @2,0",
    "route:1": "ch>ch self 1,2 8,2 8,6 0,6 0,2 @10,5",
    rows: 7,
  })
  expect(
    drawn(
      'state "Outer" as P0 {\nP0x --> P0y\n}\nP0y --> ch : a<br>b\nP0y --> A : a long label here\nP0 --> P0 : a long label here',
      { minStateGap: 3 },
    ),
  ).toMatchObject({
    "route:0": "P0x>P0y horizontal-forward 8,3 19,3",
    "route:1": "P0y>ch horizontal-forward 26,3 37,3 @31,1",
    "route:2": "P0y>A vertical-elbow 23,4 23,7 @25,7",
    "route:3": "P0>P0 self 9,6 9,8 20,8 20,7 @4,10",
    rows: 11,
  })
  expect(drawn("A --> A : retry\nA --> A : retry")).toMatchObject({
    "route:0": "A>A self 2,2 2,4 5,4 5,3 @7,2",
    "route:1": "A>A self 2,2 2,7 9,7 9,3 @11,6",
    "row:6": "  │      │ retry",
    rows: 8,
  })
  expect(
    drawn("state P0 {\nstate P0n {\n}\n}\nP0nw --> P0nw : a long label here", {
      borderStyle: "heavy",
      arrowHeadStyle: "line",
      layoutMaxWidth: 55,
    }),
  ).toMatchObject({ "route:0": "P0nw>P0nw self 2,2 2,4 5,4 5,3 @7,3", "row:4": "  ╰──╯", rows: 5 })
  expect(
    drawn("state ch <<choice>>\nch --> ch : x<br>yy<br>zzz\nch --> ch", {
      borderStyle: "rounded",
      arrowHeadStyle: "filled",
      layoutMaxWidth: 52,
    }),
  ).toMatchObject({
    "route:0": "ch>ch self 1,3 4,3 4,5 0,5 0,3 @6,0",
    "route:1": "ch>ch self 1,3 8,3 8,7 0,7 0,3",
    "row:3": "◆───┬───╮",
    "row:4": "▲   │   │",
    "row:5": "├───╯   │",
    "row:6": "│       │",
    rows: 8,
  })
})

test("pinned as observed: transitions back: lanes under and over the rows, allocated apart, and their approaches", () => {
  expect(
    drawn(
      "direction RL\nstate P0 {\n}\nstate P1 {\nP1x --> P1y : retry\n}\nP1x --> P0\nP0x --> P1x : a long label here\nA --> C : a<br>b\nP0 --> C : a long label here",
      { minStateGap: 2 },
    ),
  ).toMatchObject({
    "route:0": "P1x>P1y horizontal-forward 102,6 92,6 @94,5",
    "route:1": "P0x>P1x bottom-feedback 37,13 37,17 107,17 107,8 @63,16",
    "route:2": "A>C top-feedback 21,11 21,0 75,0 75,10 @23,3",
    "row:0": "                     ╭─────────────────────────────────────────────────────╮",
    rows: 18,
  })
  expect(drawn("state P0 {\nP0y --> [*]\n}\nB --> P0y\nP0y --> D : a<br>b")).toMatchObject({
    "route:0": "P0y>P0.__end horizontal-forward 8,3 22,3",
    "route:1": "B>P0y bottom-feedback 58,10 58,14 2,14 2,5 3,5",
    "route:2": "P0y>D vertical-elbow 5,4 5,7 @9,7",
    "row:3": "│ │ P0y ├────────────── │",
    "row:5": "│ ╭▲ │                  │",
    rows: 15,
  })
  expect(drawn("state P0 {\n[*] --> P0x\nP0x --> P0y\n}\nstate P1 {\n}\n[*] --> C\nC --> P0y\nC --> P0")).toMatchObject(
    {
      "route:0": "P0x>P0y vertical-elbow 18,8 18,7 37,7 37,5",
      "route:1": "__start>C bottom-parallel 0,4 0,19 48,19 48,5",
      "route:2": "C>P0y bottom-feedback 47,4 47,16 33,16 33,5",
      "route:3": "C>P0x vertical-elbow 46,4 46,6 14,6 14,7",
      rows: 20,
    },
  )
  expect(
    drawn("state P0 {\nP0x --> [*]\n}\nP0 --> P0\nP0 --> P0 : a<br>b", {
      borderStyle: "double",
      arrowHeadStyle: "line",
    }),
  ).toMatchObject({
    "route:0": "P0x>P0 horizontal-forward 9,3 0,3",
    "route:1": "P0x>P0 bottom-parallel 6,4 6,10 10,10 10,7 @8,7",
    "row:9": "      │   │",
    "row:10": "      ╰───╯",
    rows: 11,
  })
  expect(
    drawn(
      "state P0 {\nP0x --> P0y : a long label here\n}\nstate ch <<choice>>\nD --> P0x : go\nch --> B : go\nP0 --> ch : retry",
    ),
  ).toMatchObject({
    "route:0": "P0x>P0y horizontal-forward 8,3 27,3 @10,2",
    "route:3": "P0>ch vertical-elbow 18,6 18,7 30,7 30,8 @20,5",
    rows: 15,
  })
  expect(drawn("A --> B : x<br>yy<br>zzz\nB --> A : a long label here")).toMatchObject({
    "route:0": "A>B horizontal-forward 4,3 17,3 @9,0",
    "route:1": "B>A bottom-feedback 20,4 20,8 1,8 1,5 @2,7",
    rows: 9,
  })
  expect(drawn('direction RL\nstate P0 {\nstate "Inside" as P0x\n}\nA --> P0x\nP0 --> A')).toMatchObject({
    "route:0": "A>P0x bottom-feedback 4,10 4,14 23,14 23,5",
    "route:1": "P0>A vertical-elbow 20,6 20,7 4,7",
    rows: 15,
  })
  expect(
    drawn("state ch <<choice>>\n[*] --> C\nB --> C : x<br>yy<br>zzz\nA --> ch", {
      borderStyle: "heavy",
      arrowHeadStyle: "line",
    }),
  ).toMatchObject({
    "route:0": "__start>C horizontal-forward 1,6 13,6",
    "route:1": "B>C bottom-feedback 56,13 56,17 15,17 15,8 @34,14",
    "route:2": "A>ch top-feedback 74,11 74,0 28,0 28,11",
    "row:1": "                            │                                             │",
    rows: 18,
  })
  expect(
    drawn(
      "state P0 {\nstate P0n {\nP0nz --> P0nw\n}\n}\n[*] --> A\nP0n --> A\nP0nw --> P0nz : a long label here\nP0x --> P0nz : a long label here",
    ),
  ).toMatchObject({
    "route:0": "P0nz>P0nw horizontal-forward 49,13 62,13",
    "route:1": "__start>A horizontal-forward 1,7 13,7",
    "route:2": "P0n>A bottom-feedback 56,23 56,22 15,22 15,9",
    "route:3": "P0nw>P0nz top-feedback 67,12 67,3 48,3 48,11 @50,6",
    "route:4": "P0x>P0nz top-feedback 87,12 87,0 48,0 48,11 @68,6",
    "row:3": "                                      │ │       ├──────────────────╮    │ │            │",
    rows: 26,
  })
  expect(
    drawn("[*] --> B\nD --> A : a<br>b\nA --> ch\nD --> C : retry\nch --> D : a<br>b\nB --> ch : go"),
  ).toMatchObject({
    "route:0": "__start>B horizontal-forward 1,2 13,2",
    "route:1": "D>A vertical-elbow 53,3 53,6 @57,5",
    "route:2": "A>ch bottom-feedback 53,9 53,13 33,13 33,4",
    "route:3": "D>C horizontal-forward 55,2 68,2 @59,1",
    "route:4": "ch>D horizontal-forward 37,2 50,2 @43,0",
    "route:5": "B>ch horizontal-forward 18,2 31,2 @24,1",
    rows: 14,
  })
  expect(
    drawn('state P0 {\nstate "Inside" as P0x\nP0x --> [*]\n}\nstate P1 {\n[*] --> P1x\nP1x --> P1y\nP1y --> [*]\n}', {
      minStateGap: 8,
    }),
  ).toMatchObject({
    "route:0": "P0x>P0.__end bottom-feedback 111,10 111,16 87,16 87,8",
    "route:1": "P1.__start>P1x horizontal-forward 3,3 18,3",
    "route:2": "P1x>P1y horizontal-forward 25,3 41,3",
    "route:3": "P1y>P1.__end horizontal-forward 48,3 65,3",
    "row:9":
      "                                                                                     │ │                  │ Inside │ │",
    rows: 18,
  })
  expect(
    drawn("direction RL\nstate P0 {\nstate P0n {\nP0nz --> P0nw\n}\n}\nP0x --> P0nw : a long label here\nB --> P0nw", {
      minStateGap: 4,
    }),
  ).toMatchObject({
    "route:0": "P0nz>P0nw horizontal-forward 73,5 61,5",
    "route:1": "P0x>P0nw bottom-feedback 39,12 39,16 59,16 59,7 @40,15",
    "route:2": "B>P0nw bottom-feedback 21,12 21,19 59,19 59,7",
    rows: 20,
  })
  expect(
    drawn(
      'direction RL\nstate P0 {\n[*] --> P0x\n}\nstate P1 {\nstate "Inside" as P1x\n}\n[*] --> B\nA --> B : a<br>b\nB --> P1x',
    ),
  ).toMatchObject({
    "route:0": "P0.__start>P0x horizontal-forward 106,3 94,3",
    "route:1": "__start>B side-parallel 39,8 39,11 23,11",
    "route:2": "A>B bottom-feedback 4,10 4,16 23,16 23,11 @13,14",
    "route:3": "B>P1x bottom-feedback 22,10 22,20 60,20 60,11",
    rows: 21,
  })
  expect(
    drawn("state P0 {\nstate P0n {\nP0nz --> P0nw\n}\n}\nstate ch <<choice>>\nD --> P0nw\nC --> ch : x<br>yy<br>zzz", {
      borderStyle: "double",
      arrowHeadStyle: "line",
    }),
  ).toMatchObject({
    "route:0": "P0nz>P0nw horizontal-forward 11,8 24,8",
    "route:1": "D>P0nw bottom-feedback 69,15 69,19 26,19 26,10",
    "route:2": "C>ch top-feedback 87,13 87,0 41,0 41,13 @43,3",
    rows: 20,
  })
  expect(
    drawn(
      "state P0 {\n[*] --> P0x\n}\n[*] --> A\nA --> P0 : go\nA --> P0\nB --> A : a long label here\nP0x --> A : a long label here",
      { minStateGap: 6 },
    ),
  ).toMatchObject({ "route:1": "B>A bottom-feedback 59,8 59,14 13,14 13,3 16,3 @27,13", rows: 15 })
  expect(
    drawn(
      'state P0 {\nstate "Inside" as P0x\nstate P0n {\nP0nz --> P0nw\n}\n}\nP0x --> P0nw : a long label here\nP0nw --> P0x : retry',
      { minStateGap: 4 },
    ),
  ).toMatchObject({
    "route:0": "P0nz>P0nw bottom-feedback 46,12 46,20 36,20 36,7",
    "route:1": "P0x>P0nw horizontal-forward 11,5 34,5 @14,4",
    "route:2": "P0nw>P0x bottom-feedback 39,6 39,23 3,23 3,7 @18,22",
    rows: 25,
  })
  expect(
    drawn(
      'state "A long composite title" as P0 {\nP0x --> P0y : a<br>b\n}\n[*] --> A\nP0y --> A : x<br>yy<br>zzz\nP0y --> P0x : a<br>b',
    ),
  ).toMatchObject({
    "route:0": "P0x>P0y horizontal-forward 46,9 59,9 @52,7",
    "route:1": "__start>A horizontal-forward 1,3 13,3",
    "route:2": "P0y>A bottom-feedback 63,10 63,21 15,21 15,5 @37,18",
    "route:3": "P0y>P0x bottom-feedback 63,10 63,16 41,16 41,11 @51,14",
    rows: 20,
  })
})

test("pinned as observed: the route's kind: straight, elbowed or a side rail, through corridors clear of other states", () => {
  expect(
    drawn(
      'state "Outer" as P0 {\n}\n[*] --> A\nP0y --> C : a long label here\nA --> C : a long label here\nA --> [*]',
      { borderStyle: "single", arrowHeadStyle: "line", layoutMaxWidth: 36 },
    ),
  ).toMatchObject({
    "route:0": "__start>A vertical 4,1 4,4",
    "route:1": "P0y>C side-parallel 7,20 23,20 23,10 4,10 4,11 @25,16",
    "route:2": "A>C vertical-elbow 4,7 4,9 3,9 3,11 @8,8",
    "route:3": "A>__end side-parallel 2,6 1,6 1,11 0,11 0,15 19,15 19,14",
    "row:9": " │ ╭╯",
    "row:10": " │ │╭──────────────────╮",
    "row:11": "╭╯ ↓↓                  │",
    rows: 22,
  })
  expect(
    drawn("direction BT\n[*] --> C\nB --> A : retry\nA --> B : x<br>yy<br>zzz\nC --> A : a<br>b\nC --> B"),
  ).toMatchObject({
    "route:0": "__start>C vertical 2,16 2,12",
    "route:1": "B>A horizontal-forward 4,1 17,1 @8,0",
    "route:2": "A>B bottom-parallel 20,2 20,21 5,21 5,3 1,3 @11,18",
    "route:3": "C>A vertical-elbow 2,9 2,8 20,8 20,3 @10,6",
    "route:4": "C>B vertical 2,9 2,3",
    "row:3": " ▲▲──╮              ▲",
    rows: 22,
  })
  expect(
    drawn(
      "direction TB\nstate P0 {\n[*] --> P0x\nstate P0n {\nP0nz --> P0nw\n}\n}\nP0n --> P0 : retry\nP0n --> P0nz : a<br>b",
    ),
  ).toMatchObject({
    "route:0": "P0nz>P0nw vertical 8,11 8,15",
    "route:1": "P0n>P0nz side-parallel 13,14 14,14 14,10 12,10 @14,7",
    "route:2": "P0n>P0x side-parallel 13,14 17,14 17,3 12,3 @19,8",
    rows: 23,
  })
  expect(
    drawn(
      "[*] --> A\nA --> B : a<br>b\nA --> B : a<br>b\nA --> A : go\nA --> B : go\nB --> A : a<br>b\nnote right of A : a note",
    ),
  ).toMatchObject({
    "route:0": "__start>A horizontal-forward 1,2 13,2",
    "route:1": "A>B vertical-elbow 15,3 15,6 @12,5",
    "route:2": "A>B side-parallel 16,3 16,6 @22,6",
    "route:3": "A>A self 16,3 16,5 19,5 19,4 @21,4",
    "route:4": "A>B side-parallel 16,3 16,6 @24,5",
    "route:5": "B>A vertical-elbow 17,7 17,4 @20,6",
    "row:1": "●────────────▶│ A │════╣ a note ║",
    rows: 9,
  })
  expect(
    drawn(
      'state "A long composite title" as P0 {\nP0x --> [*]\n}\nstate P1 {\nP1y --> [*]\n}\nstate ch <<choice>>\nA --> ch : a long label here',
    ),
  ).toMatchObject({
    "route:0": "P0x>P0.__end horizontal-forward 8,3 22,3",
    "route:1": "P1y>P1.__end side-parallel 48,9 63,9 63,8 62,8",
    "route:2": "A>ch bottom-feedback 94,10 94,16 76,16 76,8 @77,14",
    "row:8": "                                        │ ╭─────╮             ─┬│           ◆               ╭───╮",
    rows: 17,
  })
  expect(drawn("direction TB\nstate ch <<choice>>\nch --> A\nch --> B : retry", { minStateGap: 1 })).toMatchObject({
    "route:0": "ch>A vertical-elbow 0,1 0,4 2,4 2,6",
    "route:1": "ch>B vertical-elbow 0,1 0,4 16,4 16,6 @5,3",
    rows: 10,
  })
  expect(
    drawn("state P0 {\n[*] --> P0x\nP0x --> P0y : a<br>b\nstate P0n {\n}\n}\nP0y --> P0\nP0x --> P0nz"),
  ).toMatchObject({
    "route:0": "P0x>P0y vertical-elbow 3,4 3,7 @1,13",
    "route:1": "P0x>P0nz horizontal-forward 8,3 21,3",
    "route:2": "P0y>P0x vertical-elbow 7,8 7,5",
    rows: 16,
  })
  expect(
    drawn(
      "state P0 {\nP0y --> [*]\n}\nB --> B\nD --> P0x : go\nP0y --> P0x : retry\nC --> P0 : retry\nA --> B : a<br>b",
      { minStateGap: 7 },
    ),
  ).toMatchObject({
    "route:0": "P0y>P0.__end horizontal-forward 8,6 24,6",
    "route:1": "B>B self 64,13 64,15 67,15 67,14",
    "route:2": "D>P0x bottom-feedback 84,13 84,17 3,17 3,14 @42,16",
    "route:3": "P0y>P0x vertical-elbow 5,7 5,10 @7,8",
    "route:4": "C>P0 top-feedback 104,11 104,0 25,0 25,2 @97,3",
    "route:5": "A>B bottom-feedback 124,13 124,14 87,14 87,10 67,10 67,14 63,14 @93,16",
    rows: 18,
  })
  expect(
    drawn(
      'state P0 {\nstate "Inside" as P0x\nP0x --> [*]\n}\nP0x --> A : a<br>b\nB --> P0x : x<br>yy<br>zzz\nP0 --> P0 : a<br>b\nP0x --> B\nP0 --> P0x : x<br>yy<br>zzz',
    ),
  ).toMatchObject({
    "route:0": "P0x>A horizontal-forward 11,4 42,4 @26,2",
    "route:1": "B>P0x bottom-feedback 25,11 25,15 3,15 3,6 @12,12",
    "route:2": "P0x>B vertical-elbow 5,5 5,7 24,7 24,8",
    "route:3": "P0x>P0 side-parallel 11,4 12,4 12,0 7,0 @14,2",
    "route:4": "P0x>P0x self 5,5 5,7 9,7 9,6 @8,10",
    rows: 16,
  })
  expect(
    drawn(
      'direction TD\nstate P0 {\nP0x --> [*]\n}\nstate "A long composite title" as P1 {\nstate "Inside" as P1x\n}\nP0x --> P1',
    ),
  ).toMatchObject({
    "route:0": "P0x>P0.__end vertical 7,4 7,9",
    "route:1": "P0x>P1 vertical-elbow 7,4 7,9 13,9 13,11",
    rows: 19,
  })
  expect(
    drawn(
      "direction RL\nstate P0 {\n[*] --> P0x\nP0x --> P0y : a<br>b\n}\nB --> P0x : retry\nP0x --> B : retry\nB --> P0x : a<br>b",
    ),
  ).toMatchObject({
    "route:0": "P0.__start>P0x horizontal-forward 46,3 34,3",
    "route:1": "P0x>P0y horizontal-forward 27,3 14,3 @19,1",
    "route:2": "B>P0x vertical-elbow 31,8 31,7 32,7 32,5 @34,7",
    "route:3": "P0x>B vertical-elbow 28,4 28,6 29,6 29,7 @21,5",
    "route:4": "B>P0x side-parallel 32,9 53,9 53,3 34,3 @55,5",
    "row:3": "     │ │ P0y │◀────────────┤ P0x │◀──────────────────╮",
    rows: 11,
  })
  expect(
    drawn(
      'direction BT\nstate "Outer" as P0 {\n}\nstate "Outer" as P1 {\n}\n[*] --> B\nP0y --> P1x : retry\nP0y --> C : x<br>yy<br>zzz',
    ),
  ).toMatchObject({
    "route:0": "__start>B vertical 3,29 3,26",
    "route:1": "P0y>P1x vertical 3,14 3,10 @5,11",
    "route:2": "P0y>C side-parallel 6,15 10,15 10,1 6,1 @12,7",
    "row:11": "   │ retry│",
    rows: 31,
  })
  expect(
    drawn("direction TB\nstate P0 {\n[*] --> P0x\n}\nstate P1 {\n}\n[*] --> D\nP0 --> P0 : x<br>yy<br>zzz"),
  ).toMatchObject({
    "route:0": "__start>D vertical 5,1 5,4",
    "route:1": "P0>P0x horizontal-forward 10,13 1,13 @12,12",
    rows: 17,
  })
  expect(
    drawn(
      'direction BT\nstate "Outer" as P0 {\n}\nstate ch <<choice>>\n[*] --> A\nA --> ch : x<br>yy<br>zzz\nP0x --> ch\nA --> P0x : a long label here',
      { minStateGap: 7 },
    ),
  ).toMatchObject({
    "route:0": "__start>A vertical 2,17 2,12",
    "route:1": "A>ch vertical-elbow 2,9 2,8 0,8 0,1 @1,5",
    "route:2": "P0x>ch horizontal-forward 16,1 0,1",
    "route:3": "A>P0x vertical-elbow 2,9 2,8 19,8 19,3 @5,10",
    "row:8": "╰─┬────────────────╯",
    "row:11": "╰───╯",
    rows: 19,
  })
  expect(
    drawn(
      "state P0 {\nP0x --> P0y : a<br>b\nP0y --> [*]\n}\nP0x --> B : a<br>b\nP0x --> A : go\nA --> [*]\nnote left of B : two<br>lines",
      { borderStyle: "heavy", arrowHeadStyle: "line", layoutMaxWidth: 55 },
    ),
  ).toMatchObject({ "row:16": "┃ │       ┃    ║↓", rows: 23 })
  expect(
    drawn("direction RL\nA --> C\nA --> C\nB --> [*]", { borderStyle: "rounded", arrowHeadStyle: "line" }),
  ).toMatchObject({ "route:2": "B>__end side-parallel 20,7 21,7 21,5 3,5 3,6", rows: 13 })
  expect(drawn("direction TD\nstate P0 {\n}\nstate P1 {\n[*] --> P1x\n}\n[*] --> B\nP1 --> B")).toMatchObject({
    "route:0": "P1.__start>P1x vertical 5,3 5,6",
    "route:1": "__start>B vertical 5,15 5,18",
    "route:2": "P1>B side-parallel 10,6 14,6 14,20 8,20",
    rows: 22,
  })
  expect(
    drawn("state P0 {\nstate P0n {\nP0nz --> P0nw\n}\n}\nstate P2 {\n}\nP0n --> P0nw : go", { minStateGap: 8 }),
  ).toMatchObject({
    "route:0": "P0nz>P0nw horizontal-forward 11,5 27,5",
    "route:1": "P0n>P0nw horizontal-forward 37,5 27,5 @26,3",
    rows: 11,
  })
  expect(drawn('direction BT\nstate "Outer" as P0 {\nP0y --> [*]\n}\nstate "Outer" as P1 {\n}')).toMatchObject({
    "route:0": "P0y>P0.__end vertical 5,7 5,2",
    "row:3": "│    │           │",
    rows: 12,
  })
  expect(
    drawn("direction RL\nstate P0 {\nstate P0n {\nP0nz --> P0nw\n}\n}\nP0nz --> P0n", {
      borderStyle: "double",
      arrowHeadStyle: "filled",
    }),
  ).toMatchObject({
    "route:0": "P0nz>P0nw horizontal-forward 25,5 12,5",
    "route:1": "P0nz>P0n horizontal-forward 25,5 35,5",
    rows: 11,
  })
  expect(
    drawn(
      "state P0 {\n[*] --> P0x\nP0x --> P0y : retry\n}\nstate ch <<choice>>\n[*] --> B\nch --> P0 : x<br>yy<br>zzz",
      { minStateGap: 4 },
    ),
  ).toMatchObject({
    "route:0": "P0x>P0y horizontal-forward 44,9 56,9 @48,8",
    "route:1": "__start>B horizontal-forward 1,3 12,3",
    "route:2": "ch>P0x side-parallel 77,8 80,8 80,12 43,12 43,11 @82,7",
    "row:6": "                                    │ ╭─────╮   retry    ╭─────╮ │          ◆───╮ yy",
    rows: 11,
  })
  expect(
    drawn(
      "direction BT\nstate P0 {\nP0x --> P0y\n}\nstate P1 {\n[*] --> P1x\n}\nD --> P0x\nP0 --> P1 : a long label here",
    ),
  ).toMatchObject({
    "route:0": "P0x>P0y vertical 5,21 5,17",
    "route:1": "D>P0x side-parallel 7,1 21,1 21,22 9,22",
    "route:2": "P0>P1x vertical-elbow 9,12 9,11 5,11 5,10 @4,4",
    rows: 26,
  })
  expect(
    drawn(
      'state "A long composite title" as P0 {\nP0x --> P0y : a long label here\n}\nP0x --> P0y : a<br>b\nP0x --> B : a<br>b',
      { borderStyle: "rounded", arrowHeadStyle: "filled", layoutMaxWidth: 35 },
    ),
  ).toMatchObject({
    "route:0": "P0x>P0y vertical 5,4 5,9 @7,15",
    "route:1": "P0x>P0y side-parallel 8,3 11,3 11,11 9,11 @13,5",
    rows: 17,
  })
  expect(
    drawn(
      'state "A long composite title" as P0 {\nP0x --> P0y : a long label here\n}\nP0x --> ch : a long label here\nD --> P0x : go\nP0 --> C : go',
      { borderStyle: "double", arrowHeadStyle: "line", layoutMaxWidth: 74 },
    ),
  ).toMatchObject({ "route:3": "P0>C vertical-elbow 13,13 13,14 2,14 2,24 @9,16", rows: 26 })
})

test("pinned as observed: detours round states, and the junctions where routes meet", () => {
  expect(
    drawn(
      "state P0 {\n[*] --> P0x\nP0x --> [*]\nstate P0n {\nP0nz --> P0nw\n}\n}\n[*] --> B\nA --> P0n : x<br>yy<br>zzz\nP0n --> P0x : a long label here\nA --> P0nw\nB --> P0nz : a<br>b\nP0x --> P0nw\nnote right of A : a note",
    ),
  ).toMatchObject({
    "route:0": "P0.__start>P0x horizontal-forward 3,3 15,3",
    "route:1": "P0x>P0.__end horizontal-forward 22,3 36,3",
    "route:2": "P0nz>P0nw bottom-feedback 90,10 90,23 16,23 16,11",
    "route:3": "__start>B side-parallel 103,8 103,11 141,11",
    "route:4": "A>P0n side-parallel 158,9 157,9 157,13 96,13 @153,9",
    "route:5": "P0n>P0x bottom-feedback 54,19 54,18 96,18 96,5 17,5 @67,16",
    "route:6": "A>P0nw bottom-feedback 160,10 160,28 16,28 16,11",
    "route:7":
      "B>P0nz bottom-feedback 140,9 97,9 97,4 37,4 37,2 23,2 23,1 15,1 15,2 2,2 2,4 15,4 15,5 16,5 16,6 85,6 85,9 @114,6",
    "route:8": "P0x>P0nw vertical-elbow 19,4 19,7",
    rows: 29,
  })
  expect(
    drawn(
      'state "A long composite title" as P0 {\n[*] --> P0x\nstate P0n {\nP0nz --> P0nw\n}\n}\nstate "A long composite title" as P2 {\nstate "Inside" as P2x\nstate P2n {\nP2nz --> P2nw\n}\n}\nP0nz --> P2nz : x<br>yy<br>zzz\nP2x --> B\nP2 --> C : x<br>yy<br>zzz\nP2nw --> P0n : a<br>b',
    ),
  ).toMatchObject({
    "route:0": "P0.__start>P0x horizontal-forward 3,3 15,3",
    "route:1": "P0nz>P0nw horizontal-forward 51,9 64,9",
    "route:2": "P2nz>P2nw horizontal-forward 124,9 137,9",
    "route:3": "P0nz>P2nz bottom-parallel 48,10 48,23 123,23 123,11 @84,20",
    "route:4": "P2x>B bottom-parallel 99,10 99,11 116,11 116,7 158,7 158,11 162,11",
    "route:5": "P2>C bottom-parallel 149,9 157,9 157,12 176,12 176,7 179,7 @150,11",
    "route:6": "P2nw>P0n bottom-feedback 142,10 142,11 124,11 124,24 43,24 43,13 @92,21",
    "row:11":
      "│                                         │     │                         │ │               │      ╰────────────────╯      ▲╭─────────────────╯    │ │x      │╰───▲             │",
    rows: 25,
  })
  expect(
    drawn('direction RL\nstate "Outer" as P0 {\n}\nstate P1 {\nP1x --> P1y\nP1y --> [*]\n}\n[*] --> A'),
  ).toMatchObject({
    "route:0": "P1x>P1y horizontal-forward 36,7 23,7",
    "route:1": "P1y>P1.__end side-parallel 22,7 23,7 23,5 2,5 2,6",
    "route:2": "__start>A horizontal-forward 81,1 69,1",
    "row:5": "│ │────────────────────╮                    │",
    "row:6": "│ │             ╭─────╮│            ╭─────╮ │",
    rows: 11,
  })
  expect(
    drawn("direction RL\nstate ch <<choice>>\n[*] --> A\nA --> ch : x<br>yy<br>zzz\nC --> ch\nA --> [*]", {
      borderStyle: "double",
      arrowHeadStyle: "line",
      layoutMaxWidth: 21,
    }),
  ).toMatchObject({
    "route:0": "__start>A vertical 3,22 3,17",
    "route:1": "A>ch vertical-elbow 3,14 3,13 1,13 1,7 @2,10",
    "route:2": "C>ch side-parallel 5,1 19,1 19,9 1,9 1,7",
    "route:3": "A>__end vertical-elbow 3,14 3,13 0,13 0,6 15,6",
    "row:8": "│↑                 │",
    "row:9": "│├─────────────────╯",
    rows: 24,
  })
  expect(
    drawn(
      "direction TD\nstate P0 {\nP0x --> P0y\n}\nstate ch <<choice>>\nA --> P0 : a<br>b\nch --> P0y\nch --> B : a long label here\nnote left of P0x : two<br>lines\nnote right of A : a note",
      { minStateGap: 1 },
    ),
  ).toMatchObject({
    "route:0": "P0x>P0y vertical 20,4 20,8",
    "route:1": "A>P0 side-parallel 18,24 17,24 17,14 13,14 @19,18",
    "route:2": "ch>P0y side-parallel 21,16 32,16 32,10 24,10",
    "route:3": "ch>B side-parallel 21,16 37,16 37,32 23,32 @39,24",
    rows: 34,
  })
  expect(
    drawn('direction TB\nstate P0 {\nstate "Inside" as P0x\n}\nB --> P0\nP0 --> P0x\nnote right of P0x : n'),
  ).toMatchObject({
    "route:0": "B>P0 side-parallel 9,10 26,10 26,3 23,3",
    "route:1": "P0>P0x horizontal-forward 0,3 12,3",
    rows: 12,
  })
  expect(drawn("state ch <<choice>>\n[*] --> C\nch --> A : go\nnote right of ch : a note")).toMatchObject({
    "route:0": "__start>C horizontal-forward 1,1 13,1",
    "route:1": "ch>A side-parallel 28,7 28,8 53,8 53,7 @51,6",
    rows: 9,
  })
  expect(
    drawn("state ch <<choice>>\n[*] --> C\nch --> B : a long label here\nA --> A\nnote right of ch : two<br>lines"),
  ).toMatchObject({
    "route:0": "__start>C horizontal-forward 1,1 13,1",
    "route:1": "ch>B side-parallel 28,7 28,9 56,9 @48,11",
    "route:2": "A>A self 74,8 74,10 77,10 77,9",
    rows: 12,
  })
  expect(
    drawn(
      "state P0 {\nP0x --> P0y : a<br>b\n}\nP0x --> B : a<br>b\nP0x --> A : go\nA --> [*]\nnote left of B : a note\nnote left of B : two<br>lines",
      { borderStyle: "heavy", arrowHeadStyle: "line", layoutMaxWidth: 55 },
    ),
  ).toMatchObject({
    "route:0": "P0x>P0y vertical 5,8 5,13 @7,10",
    "route:1": "P0x>B vertical-elbow 5,6 5,5 8,5 8,0 24,0 24,13 @6,2",
    "route:2": "P0x>A vertical-elbow 5,6 5,5 8,5 8,0 39,0 39,15 @2,5",
    "route:3": "A>__end vertical-elbow 42,16 42,18 5,18 5,20",
    rows: 24,
  })
  expect(
    drawn("state ch <<choice>>\nch --> ch\nnote right of ch : two<br>lines", {
      borderStyle: "rounded",
      arrowHeadStyle: "filled",
      layoutMaxWidth: 52,
    }),
  ).toMatchObject({ "route:0": "ch>ch self 0,2", rows: 4 })
  expect(
    drawn(
      'direction TD\nstate "A long composite title" as P0 {\n}\nstate P1 {\n[*] --> P1x\nP1x --> P1y : a<br>b\n}\nP1y --> P1 : a<br>b\nnote right of P1y : a note',
    ),
  ).toMatchObject({
    "route:0": "P1x>P1y vertical 5,4 5,9 @7,6",
    "route:1": "P1y>P1x side-parallel 2,11 1,11 1,3 @3,6",
    rows: 15,
  })
  expect(drawn("state P0 {\n}\nstate P1 {\n[*] --> P1x\n}\nnote left of P1x : n")).toMatchObject({
    "route:0": "P1.__start>P1x horizontal-forward 2,2 2,1 19,1",
    rows: 7,
  })
  expect(
    drawn(
      'state "Outer" as P0 {\n}\nC --> P0x : a<br>b\nA --> C\nB --> C : x<br>yy<br>zzz\nA --> [*]\nnote right of B : a note',
      { minStateGap: 1 },
    ),
  ).toMatchObject({
    "route:0": "C>P0x horizontal-forward 4,3 13,3 @8,1",
    "route:1": "A>C bottom-feedback 30,10 30,14 1,14 1,5",
    "route:2": "B>C bottom-feedback 44,10 44,19 1,19 1,5 @21,16",
    "route:3": "A>__end side-parallel 32,9 41,9 41,7 46,7 46,3 50,3 50,2 61,2 61,6 57,6 57,8",
    "row:13": " ├────────────────────────────╯             │",
    rows: 19,
  })
  expect(
    drawn(
      'direction RL\nstate "A long composite title" as P0 {\n[*] --> P0x\nP0x --> P0y : a<br>b\nstate P0n {\n}\n}\n[*] --> D\nP0nz --> P0y',
    ),
  ).toMatchObject({ "route:3": "P0nz>P0y bottom-feedback 6,10 6,11 37,11 37,7 79,7 79,5", rows: 12 })
  expect(
    drawn(
      'direction TD\nstate "A long composite title" as P0 {\nstate P0n {\nP0nz --> P0nw\n}\n}\nP0nw --> P0n : a long label here\nnote right of P0nw : two<br>lines',
      { borderStyle: "single", arrowHeadStyle: "line" },
    ),
  ).toMatchObject({
    "route:0": "P0nz>P0nw vertical 8,6 8,10",
    "route:1": "P0nw>P0n side-parallel 4,12 3,12 3,9 1,9 @5,14",
    rows: 18,
  })
  expect(
    drawn(
      "state P0 {\nP0x --> P0y : a long label here\nstate P0n {\nP0nz --> P0nw\n}\n}\nstate P2 {\nstate P2n {\n}\n}\nP0nz --> P0x\nP0nw --> P0x : x<br>yy<br>zzz\nP2nz --> P0nz : a long label here\nP0nw --> P0y : retry",
      { borderStyle: "rounded", arrowHeadStyle: "filled", layoutMaxWidth: 45 },
    ),
  ).toMatchObject({
    "route:3": "P0nw>P0x side-parallel 11,24 14,24 14,3 12,3 @16,12",
    "route:5": "P0nw>P0y side-parallel 11,24 14,24 14,10 12,10 @16,17",
    rows: 35,
  })
})

test("pinned as observed: labels placed clear of routes and states", () => {
  expect(
    drawn(
      "state P0 {\n[*] --> P0x\nP0x --> [*]\n}\nP0x --> A : x<br>yy<br>zzz\nP0x --> P0x : go\nP0 --> P0 : x<br>yy<br>zzz\nP0x --> B : go",
    ),
  ).toMatchObject({
    "route:0": "P0x>A horizontal-forward 8,3 38,3 @22,0",
    "route:1": "P0x>P0x self 4,4 4,6 7,6 7,5 @1,6",
    "route:2": "P0x>B vertical-elbow 5,4 5,6 22,6 22,7 @9,4",
    "route:3": "P0x>P0x self 4,4 4,9 11,9 11,5 @10,11",
    "row:6": "│go ├┴─┴───┼──────────╮",
    rows: 15,
  })
  expect(
    drawn(
      'state P0 {\nstate "In" as P0x\n}\nstate P1 {\n[*] --> P1x\nP1x --> P1y : retry\n}\nC --> P1 : go\nP1x --> P0\nP1y --> P0x\nP0x --> P1x : a long label here\nA --> C : a<br>b\nP0 --> C : a long label here\nC --> [*]',
      { minStateGap: 2 },
    ),
  ).toMatchObject({
    "route:0": "P1x>P1y horizontal-forward 37,3 47,3 @40,2",
    "route:1": "P1x>P0 bottom-feedback 34,4 34,18 1,18 1,7",
    "route:2": "P1y>P0x bottom-feedback 51,4 51,5 38,5 38,1 8,1 8,5 3,5",
    "route:3": "P0x>P1x horizontal-forward 7,3 30,3 @10,2",
    "route:4": "A>C top-feedback 94,8 94,7 50,7 @71,4",
    "route:5": "P0>C vertical-elbow 3,6 3,7 48,7 @5,9",
    "route:6": "C>__end side-parallel 51,9 52,9 52,7 62,7",
    "route:7": "C>P1x bottom-feedback 49,10 49,14 32,14 32,5 @39,13",
    "row:5": "│  ▶────╯│                   │  ▲ │   ╰────────────╯    │              b",
    rows: 19,
  })
  expect(
    drawn(
      "direction TB\nB --> B : a<br>b\nB --> A : a long label here\nB --> A : a long label here\nA --> B : a long label here\nA --> B",
    ),
  ).toMatchObject({
    "route:0": "B>B self 3,2 3,4 6,4 6,3 @1,4",
    "route:1": "B>A vertical 3,2 3,7 @17,4",
    "route:2": "B>A side-parallel 5,1 9,1 9,9 6,9 @17,6",
    "route:3": "A>B side-parallel 5,9 12,9 12,1 6,1 @17,2",
    "route:4": "A>B side-parallel 5,9 15,9 15,1 6,1",
    "row:9": " │ A ├───┴──┴──╯",
    rows: 11,
  })
  expect(
    drawn(
      'direction RL\nstate P0 {\nstate "Inside" as P0x\n}\n[*] --> A\nA --> P0x : go\nP0 --> B : a<br>b\nP0 --> P0x : a<br>b',
    ),
  ).toMatchObject({
    "route:0": "__start>A horizontal-forward 57,3 45,3",
    "route:1": "A>P0x horizontal-forward 40,3 27,3 @32,2",
    "route:2": "P0>B vertical-elbow 22,6 22,7 2,7 @19,9",
    "route:3": "P0>P0x horizontal-forward 28,3 16,3 @13,2",
    rows: 11,
  })
  expect(
    drawn("direction TB\nstate P0 {\nstate P0n {\nP0nz --> P0nw\n}\n}\nP0 --> P0y\nP0n --> P0x : retry"),
  ).toMatchObject({
    "route:0": "P0nz>P0nw vertical 8,6 8,10",
    "route:1": "P0>P0y side-parallel 15,9 19,9 19,19 12,19",
    "route:2": "P0n>P0x side-parallel 13,9 14,9 14,8 20,8 20,20 12,20 12,26 @24,17",
    rows: 28,
  })
  expect(
    drawn(
      'direction TB\nstate P0 {\nP0x --> P0y : go\n}\nstate "Outer" as P1 {\nP1x --> P1y : go\nstate P1n {\nP1nz --> P1nw\n}\n}\nP1nz --> B : retry\nP1y --> P1nw : a long label here',
    ),
  ).toMatchObject({
    "route:0": "P0x>P0y vertical 8,4 8,8 @10,6",
    "route:1": "P1x>P1y vertical 8,18 8,22 @10,20",
    "route:2": "P1nz>P1nw vertical 8,32 8,36",
    "route:3": "P1nz>B side-parallel 11,31 19,31 19,45 11,45 @21,38",
    "route:4": "P1y>P1nw side-parallel 5,24 3,24 3,38 @16,30",
    rows: 47,
  })
  expect(drawn("A --> A : x<br>yy<br>zzz\nnote right of A : two<br>lines")).toMatchObject({
    "route:0": "A>A self 2,4 2,6 5,6 5,5 @4,7",
    "row:4": "  │  ▲",
    rows: 9,
  })
  expect(drawn('state "Outer" as P0 {\n}\nstate P1 {\n}\nP0x --> P0x : a<br>b')).toMatchObject({
    "route:0": "P0x>P0x self 2,3 2,5 5,5 5,4 @5,6",
    rows: 7,
  })
  expect(
    drawn("direction BT\nA --> C : retry\nA --> A : retry", {
      borderStyle: "rounded",
      arrowHeadStyle: "line",
      layoutMaxWidth: 72,
    }),
  ).toMatchObject({ "route:0": "A>C vertical 2,7 2,3 @4,4", "route:1": "A>A self 2,9 2,11 5,11 5,10 @7,10", rows: 12 })
  expect(
    drawn("direction TB\n[*] --> A\nD --> B : go\nC --> A : a long label here\nnote right of A : two<br>lines"),
  ).toMatchObject({
    "route:0": "__start>A vertical 2,1 2,4",
    "route:1": "D>B vertical 2,14 2,18 @6,16",
    "route:2": "C>A side-parallel 4,27 5,27 5,8 2,8 @7,18",
    rows: 29,
  })
  expect(
    drawn(
      "state P0 {\n[*] --> P0x\n}\nstate P1 {\n}\nstate ch <<choice>>\n[*] --> A\nB --> P0x : a<br>b\nch --> P0 : a long label here",
      { minStateGap: 8 },
    ),
  ).toMatchObject({
    "route:0": "__start>A horizontal-forward 1,2 16,2",
    "route:1": "B>P0x bottom-feedback 88,9 88,15 47,15 47,10 @67,13",
    "route:2": "ch>P0x side-parallel 70,7 70,10 51,10 @27,10",
    rows: 15,
  })
  expect(
    drawn(
      'direction TB\nstate P0 {\n[*] --> P0x\n}\nstate "Outer" as P1 {\n[*] --> P1x\nP1x --> P1y : retry\nP1y --> [*]\n}\nD --> P0x : a long label here',
      { minStateGap: 2 },
    ),
  ).toMatchObject({ "route:2": "P1x>P1y vertical 5,21 5,25 @5,14", rows: 41 })
})
