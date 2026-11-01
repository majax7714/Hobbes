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

test("a self transition leaves the bottom a third in and comes back up two thirds in; another loops 3 lower and wider, its head still under the box short of the corner", () => {
  // Box 10 wide: the source a third in (3), the first head two thirds in (7); the second would go 4 wider (11), past
  // the box, so it takes the last column short of the corner (8).
  expect(routes('state "Longer" as A\nA --> A\nA --> A')).toEqual([
    "A>A self 3,2 3,4 7,4 7,3",
    "A>A self 3,2 3,7 8,7 8,3",
  ])
})

test("a self loop's head moves to the nearest column no other route takes below the box", () => {
  // Alone, the head comes up at 5; here B --> A arrives on 5, so the head takes 4.
  expect(routes("A --> A")).toEqual(["A>A self 2,2 2,4 5,4 5,3"])
  const drawnRoutes = routes("A --> A\nA --> B\nB --> A\nA --> [*]")
  expect([drawnRoutes[0], drawnRoutes[2]]).toEqual(["A>A self 2,2 2,4 4,4 4,3", "B>A vertical-elbow 4,6 4,5 5,5 5,3"])
})

test("a route whose end earlier routes wall in crosses one of them rather than run through a box", () => {
  // B --> P1x's side rail would come back along row 10, B's bottom row. P1x is ringed by P1y --> P0y's lane under the
  // rows (column 120 down to row 17) and the routes along rows 3 and 6, so no way into it avoids every earlier route:
  // the repair goes under B on row 11 and up into P1x's right side, crossing that lane at column 120.
  const drawnRoutes = routes(
    [
      "state P0 {\n[*] --> P0x\nP0x --> P0y\n}",
      'state "A long composite title" as P1 {\n[*] --> P1x\nP1x --> P1y : a long label here\n}',
      "[*] --> A\nP0y --> P1y\nA --> P0 : a long label here\nA --> P1 : a long label here",
      "P1y --> P0y : a<br>b\nB --> P1",
    ].join("\n"),
  )
  expect(drawnRoutes).toEqual(
    expect.arrayContaining([
      "P1y>P0y bottom-feedback 120,4 120,17 63,17 63,5 @91,15",
      "B>P1x side-parallel 147,9 148,9 148,11 84,11 84,10",
    ]),
  )
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
    "route:0": "A>A self 3,2 3,4 6,4 6,3 @9,4",
    "route:1": "A>A self 3,2 3,7 7,7 7,3 @9,6",
    "row:6": "   │   │ retry",
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
    "route:3": "P0>ch vertical-elbow 16,6 16,8 30,8 30,9 @18,7",
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
    "route:2": "A>ch top-feedback 74,11 74,0 28,0 28,12",
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
    "route:0": "P0x>P0.__end bottom-feedback 111,10 111,16 87,16 87,9",
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
    "route:0": "P0.__start>P0x horizontal-forward 104,3 92,3",
    "route:1": "__start>B horizontal-forward 35,9 23,9",
    "route:2": "A>B bottom-feedback 2,10 2,16 21,16 21,11 @11,14",
    "route:3": "B>P1x bottom-feedback 20,10 20,20 58,20 58,11",
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
    "route:2": "C>ch top-feedback 87,13 87,0 41,0 41,14 @43,3",
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
    "route:1": "A>B vertical-elbow 15,3 15,5 16,5 16,6 @12,3",
    "route:2": "A>B side-parallel 17,3 17,6 @23,4",
    "route:3": "A>A self 16,3 16,5 18,5 18,4 @20,4",
    "route:4": "A>B side-parallel 17,3 17,6 @25,5",
    "route:5": "B>A vertical-elbow 18,7 18,6 19,6 19,4 @21,6",
    "row:1": "●────────────▶│  A  │════╣ a note ║",
    rows: 9,
  })
  expect(
    drawn(
      'state "A long composite title" as P0 {\nP0x --> [*]\n}\nstate P1 {\nP1y --> [*]\n}\nstate ch <<choice>>\nA --> ch : a long label here',
    ),
  ).toMatchObject({
    "route:0": "P0x>P0.__end horizontal-forward 8,3 22,3",
    "route:1": "P1y>P1.__end horizontal-forward 48,9 62,9",
    "route:2": "A>ch bottom-feedback 94,10 94,16 76,16 76,9 @77,14",
    "row:8": "                                        │ ╭─────╮               │                           ╭───╮",
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
    "route:1": "B>B self 70,13 70,15 73,15 73,14",
    "route:2": "D>P0x bottom-feedback 92,13 92,17 3,17 3,14 @46,16",
    "route:3": "P0y>P0x vertical-elbow 5,7 5,10 @7,8",
    "route:4": "C>P0 top-feedback 112,11 112,0 25,0 25,2 @105,3",
    "route:5": "A>B bottom-feedback 132,13 132,14 95,14 95,10 75,10 75,14 69,14 @100,16",
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
    "route:1": "P0x>P1 vertical-elbow 7,4 7,9 30,9 30,11",
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
  ).toMatchObject({ "route:2": "B>__end horizontal-forward 14,7 1,7", rows: 13 })
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
    "route:2": "ch>P0x bottom-feedback 76,10 76,16 39,16 39,11 @56,13",
    "row:6": "                                    │ ╭─────╮   retry    ╭─────╮ │",
    rows: 15,
  })
  expect(
    drawn(
      "direction BT\nstate P0 {\nP0x --> P0y\n}\nstate P1 {\n[*] --> P1x\n}\nD --> P0x\nP0 --> P1 : a long label here",
    ),
  ).toMatchObject({
    "route:0": "P0x>P0y vertical 5,21 5,17",
    "route:1": "D>P0x side-parallel 29,1 36,1 36,22 9,22",
    "route:2": "P0>P1x vertical-elbow 9,12 9,11 27,11 27,10 @5,9",
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
    "route:3": "__start>B horizontal-forward 103,9 139,9",
    "route:4": "A>P0n side-parallel 158,9 157,9 157,13 96,13 @153,9",
    "route:5": "P0n>P0x bottom-feedback 54,19 54,18 96,18 96,5 17,5 @67,16",
    "route:6": "A>P0nw bottom-feedback 160,10 160,28 16,28 16,11",
    "route:7":
      "B>P0nz bottom-feedback 140,9 103,9 103,8 97,8 97,4 37,4 37,2 23,2 23,1 15,1 15,2 2,2 2,4 15,4 15,5 16,5 16,6 85,6 85,9 @114,11",
    "route:8": "P0x>P0nw vertical-elbow 19,4 19,5 86,5 86,7 94,7 94,11 19,11",
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
    "route:1": "P1y>P1.__end horizontal-forward 16,7 2,7",
    "route:2": "__start>A horizontal-forward 81,1 69,1",
    "row:5": "│                                           │",
    "row:6": "│               ╭─────╮             ╭─────╮ │",
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
    "route:1": "ch>A horizontal-forward 28,6 28,5 53,5 53,7 @40,3",
    rows: 9,
  })
  expect(
    drawn("state ch <<choice>>\n[*] --> C\nch --> B : a long label here\nA --> A\nnote right of ch : two<br>lines"),
  ).toMatchObject({
    "route:0": "__start>C horizontal-forward 1,1 13,1",
    "route:1": "ch>B horizontal-forward 28,8 28,9 53,9 53,7 @32,11",
    "route:2": "A>A self 82,8 82,10 85,10 85,9",
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
    "route:3": "A>__end bottom-parallel 30,10 30,11 41,11 41,7 46,7 46,3 50,3 50,2 61,2 61,6 57,6 57,10 56,10",
    "row:13": " ├────────────────────────────╯             │",
    rows: 19,
  })
  expect(
    drawn(
      'direction RL\nstate "A long composite title" as P0 {\n[*] --> P0x\nP0x --> P0y : a<br>b\nstate P0n {\n}\n}\n[*] --> D\nP0nz --> P0y',
    ),
  ).toMatchObject({ "route:3": "P0nz>P0y bottom-feedback 6,10 6,14 79,14 79,5", rows: 15 })
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
    "route:0": "P0x>A horizontal-forward 10,3 40,3 @24,0",
    "route:1": "P0x>P0x self 5,4 5,6 8,6 8,5 @2,6",
    "route:2": "P0x>B vertical-elbow 6,4 6,6 23,6 23,7 @11,4",
    "route:3": "P0x>P0x self 5,4 5,9 9,9 9,5 @8,11",
    "row:6": "│ go ├┴─┴┼─────────────╮",
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
    "route:6": "C>__end horizontal-forward 51,9 61,9",
    "route:7": "C>P1x bottom-feedback 49,10 49,14 32,14 32,5 @39,13",
    "row:5": "│  ▲────╯│                   │  ▲ │   ╰────────────╯    │              b",
    rows: 19,
  })
  expect(
    drawn(
      "direction TB\nB --> B : a<br>b\nB --> A : a long label here\nB --> A : a long label here\nA --> B : a long label here\nA --> B",
    ),
  ).toMatchObject({
    "route:0": "B>B self 2,2 2,4 5,4 5,3 @7,4",
    "route:1": "B>A vertical 3,2 3,7 @18,4",
    "route:2": "B>A side-parallel 6,1 10,1 10,9 6,9 @18,6",
    "route:3": "A>B side-parallel 5,9 13,9 13,1 7,1 @18,2",
    "route:4": "A>B side-parallel 5,9 16,9 16,1 7,1",
    "row:9": " │ A ├────┴──┴──╯",
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
    "route:1": "P0>P0y side-parallel 15,9 30,9 30,19 27,19",
    "route:2": "P0n>P0x vertical-elbow 8,15 8,22 23,22 23,24 @10,21",
    rows: 28,
  })
  expect(
    drawn(
      'direction TB\nstate P0 {\nP0x --> P0y : go\n}\nstate "Outer" as P1 {\nP1x --> P1y : go\nstate P1n {\nP1nz --> P1nw\n}\n}\nP1nz --> B : retry\nP1y --> P1nw : a long label here',
    ),
  ).toMatchObject({
    "route:0": "P0x>P0y vertical 8,4 8,8 @10,6",
    "route:1": "P1x>P1y vertical 44,18 44,22 @46,20",
    "route:2": "P1nz>P1nw vertical 44,32 44,36",
    "route:3": "P1nz>B side-parallel 47,31 64,31 64,45 61,45 @66,38",
    "route:4": "P1y>P1nw side-parallel 41,24 39,24 39,38 @20,31",
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
  ).toMatchObject({ "route:0": "A>C vertical 3,7 3,3 @5,4", "route:1": "A>A self 2,9 2,11 5,11 5,10 @7,10", rows: 12 })
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
    "route:1": "B>P0x bottom-feedback 88,9 88,19 47,19 47,10 @67,17",
    "route:2": "ch>P0x bottom-feedback 69,9 69,15 47,15 47,10 @49,14",
    rows: 19,
  })
  expect(
    drawn(
      'direction TB\nstate P0 {\n[*] --> P0x\n}\nstate "Outer" as P1 {\n[*] --> P1x\nP1x --> P1y : retry\nP1y --> [*]\n}\nD --> P0x : a long label here',
      { minStateGap: 2 },
    ),
  ).toMatchObject({ "route:2": "P1x>P1y vertical 20,21 20,25 @20,14", rows: 41 })
})

// Found the same way after the 2026-11-01 defect fixes, searching only the faults those fixes left untold: their new
// code, and faults only inputs above told apart until the fixes changed what those inputs draw. Pinned as observed;
// the harnesses keep no input that shows a known wrong drawing.
test("pinned as observed: faults the defect fixes left untold: self-loop heads, same-row routes and the heads repaired routes draw", () => {
  expect(
    drawn(
      'direction TB\nstate "Outer" as P0 {\nstate "Inside" as P0x\n}\nstate P1 {\nP1x --> P1y : x<br>yy<br>zzz\n}\nA --> C\nP1y --> C : retry\nA --> [*]\nnote right of C : a note',
    ),
  ).toMatchObject({
    "route:3": "A>__end side-parallel 25,26 26,26 26,31 40,31 40,35 24,35 24,39",
    "row:26": "                    ││ A ├╮",
    "row:27": "                    │╰─┬─╯│",
    "row:28": "                    │  │  │",
    "row:29": "                    │  │  │",
    "row:30": "                    │  │  │",
    "row:31": "                    │  ▼  ╰─────────────╮",
    "row:33": "                    ▶│ C │════╣ a note ║│",
    "row:35": "                        ╭───────────────╯",
    "row:36": "                        │",
    "row:37": "                        │",
    "row:38": "                        │",
    "row:39": "                       ◎◀",
    rows: 40,
  })
  expect(
    drawn('state P0 {\n}\nstate "Outer" as P1 {\nP1x --> [*]\n}\nnote right of P1x : n', { minStateGap: 7 }),
  ).toMatchObject({
    "route:0": "P1x>P1.__end horizontal-forward 5,2 5,1 24,1 24,3",
    "row:0": "╭─ Outer ─────────────────╮",
    "row:1": "│    ╭──────────────────╮ │",
    "row:2": "│ ╭──┴──╮    ╔═══╗      │ │",
    "row:3": "│ │ P1x │════╣ n ║      │ │",
    "row:4": "│ ╰─────╯    ╚═══╝        │",
    "row:5": "│                         │",
    "row:6": "╰─────────────────────────╯",
    rows: 7,
  })
  expect(
    drawn("[*] --> A\nA --> B : a<br>b\nA --> A : go\nA --> B : go\nB --> B : go\nB --> A : a<br>b"),
  ).toMatchObject({
    "route:0": "__start>A horizontal-forward 1,2 13,2",
    "route:1": "A>B vertical-elbow 15,3 15,6 @12,5",
    "route:2": "A>A self 16,3 16,5 18,5 18,4 @20,4",
    "route:3": "A>B side-parallel 20,2 24,2 24,8 21,8 @26,5",
    "route:4": "B>B self 16,9 16,11 19,11 19,10 @21,10",
    "route:5": "B>A vertical-elbow 19,7 19,4 @22,6",
    "row:0": "              ╭─────╮",
    "row:1": "●────────────▶│  A  ├───╮",
    "row:10": "                ╰──╯",
    "row:2": "              ╰┬┬───╯   │",
    "row:3": "               ││ ▲▲go  │",
    "row:4": "            a  │╰─╯│    │ go",
    "row:5": "            b  ▼   │  a │",
    "row:6": "              ╭────┴╮ b │",
    "row:7": "              │  B  │◀──╯",
    "row:8": "              ╰─┬───╯",
    "row:9": "                │  ▲ go",
    rows: 11,
  })
  expect(drawn("C --> C : go\nC --> C : a long label here")).toMatchObject({
    "route:0": "C>C self 4,2 4,4 7,4 7,3 @1,4",
    "route:1": "C>C self 4,2 4,7 8,7 8,3 @10,6",
    "row:0": " ╭───────╮",
    "row:1": " │   C   │",
    "row:2": " ╰──┬────╯",
    "row:3": "    │  ▲▲",
    "row:4": " go ├──╯│",
    "row:5": "    │   │",
    "row:6": "    │   │ a long label here",
    "row:7": "    ╰───╯",
    rows: 8,
  })
  expect(
    drawn(
      "state P0 {\nP0x --> P0y : a long label here\n}\nstate ch <<choice>>\nP0x --> ch : retry\nD --> P0x : go\nch --> B : go",
    ),
  ).toMatchObject({
    "route:0": "P0x>P0y horizontal-forward 8,3 27,3 @10,2",
    "route:1": "P0x>ch vertical-elbow 5,4 5,8 @7,5",
    "route:2": "D>P0x bottom-feedback 76,10 76,14 3,14 3,5 @38,13",
    "route:3": "ch>B side-parallel 6,8 6,11 39,11 @41,11",
    "row:0": "╭─ P0 ──────────────────────────────╮",
    "row:1": "│                                   │",
    "row:10": "   │  │                               ╰───╯                               ╰─┬─╯",
    "row:11": "   │  ╰────────────────────────────────▲ go                                 │",
    "row:12": "   │                                                                        │",
    "row:13": "   │                                  go                                    │",
    "row:14": "   ╰────────────────────────────────────────────────────────────────────────╯",
    "row:2": "│ ╭─────╮ a long label here ╭─────╮ │",
    "row:3": "│ │ P0x ├──────────────────▶│ P0y │ │",
    "row:4": "│ ╰──┬──╯                   ╰─────╯ │",
    "row:5": "│  ▲ │ retry                        │",
    "row:6": "╰──│─│──────────────────────────────╯",
    "row:7": "   │ ▼",
    "row:8": "   │ ◆│                               ╭───╮                               ╭───╮",
    "row:9": "   │  │                               │ B │                               │ D │",
    rows: 15,
  })
  expect(
    drawn("direction TB\nstate P0 {\n}\nstate P1 {\n}\n[*] --> D\nA --> A\nP0x --> D : a<br>b\nA --> [*]"),
  ).toMatchObject({
    "route:0": "__start>D vertical 4,1 4,4",
    "route:1": "A>A self 3,14 3,16 4,16 4,15",
    "route:2": "P0x>D side-parallel 7,20 11,20 11,6 7,6 @13,12",
    "route:3": "A>__end side-parallel 7,13 8,13 8,15 5,15 5,18 0,18 0,22 5,22 5,27",
    "row:0": "    ●",
    "row:1": "    │",
    "row:10": "           │",
    "row:11": "           │",
    "row:12": " ╭─────╮   │ a",
    "row:13": " │  A  ├╮  │ b",
    "row:14": " ╰─┬───╯│  │",
    "row:15": "   │▲╭──╯  │",
    "row:16": "   ╰╯│     │",
    "row:17": "     │     │",
    "row:18": "╭────╯     │",
    "row:19": "│╭─────╮   │",
    "row:2": "    │",
    "row:20": "││ P0x ├───╯",
    "row:21": "│╰─────╯",
    "row:22": "╰────╮",
    "row:23": "     │",
    "row:24": "     │",
    "row:25": "     │",
    "row:26": "     │",
    "row:27": "    ◎◀",
    "row:3": "    │",
    "row:4": "    ▼",
    "row:5": "  ╭───╮",
    "row:6": "  │ D │◀───╮",
    "row:7": "  ╰───╯    │",
    "row:8": "           │",
    "row:9": "           │",
    rows: 28,
  })
  expect(
    drawn(
      "state P0 {\n[*] --> P0x\n}\nstate P1 {\nP1x --> [*]\n}\n[*] --> A\nA --> A\nP1 --> A : retry\nA --> A : a<br>b",
    ),
  ).toMatchObject({
    "route:0": "P0.__start>P0x horizontal-forward 3,3 15,3",
    "route:1": "__start>A horizontal-forward 63,9 89,9",
    "route:2": "A>A self 93,10 93,12 96,12 96,11",
    "route:3": "A>A self 93,10 93,15 97,15 97,11 @99,14",
    "route:4": "P1x>A bottom-parallel 45,10 45,16 97,16 97,11 @68,15",
    "row:0": "╭─ P0 ──────────────────╮",
    "row:1": "│                       │",
    "row:10": "                                        │ ╰──┬──╯ │                                       ╰──┬────╯",
    "row:11": "                                        │    │    │                                          │  ▲▲",
    "row:12": "                                        ╰────│────╯                                          ├──╯│",
    "row:13": "                                             │                                               │   │",
    "row:14": "                                             │                                               │   │ a",
    "row:15": "                                             │                      retry                    ╰───┤ b",
    "row:16": "                                             ╰───────────────────────────────────────────────────╯",
    "row:2": "│               ╭─────╮ │",
    "row:3": "│ ─────────────▶│ P0x │ │",
    "row:4": "│               ╰─────╯ │",
    "row:5": "│                       │",
    "row:6": "╰───────────────────────╯               ╭─ P1 ────╮",
    "row:7": "                                        │         │",
    "row:8": "                                        │ ╭─────╮ │                                       ╭───────╮",
    "row:9": "                                        │ │ P1x │ │           ●──────────────────────────▶│   A   │",
    rows: 17,
  })
  expect(
    drawn(
      'direction BT\nstate "A long composite title" as P0 {\nP0x --> [*]\n}\nstate P1 {\n[*] --> P1x\n}\nP1 --> P0',
      { borderStyle: "double", arrowHeadStyle: "line", layoutMaxWidth: 79 },
    ),
  ).toMatchObject({
    "route:2": "P1>P0 side-parallel 48,18 52,18 52,6 27,6",
    "row:10": "║                         ║                         │",
    "row:11": "╚═════════════════════════╝                         │",
    "row:12": "                               ╔═ P1 ═══════════╗   │",
    "row:13": "                               ║                ║   │",
    "row:14": "                               ║ ╔═════╗        ║   │",
    "row:15": "                               ║ ║ P1x ║        ║   │",
    "row:16": "                               ║ ╚═════╝        ║   │",
    "row:17": "                               ║    ↑           ║   │",
    "row:18": "                               ║    │           ├───╯",
    "row:6": "║    │                    ║←────────────────────────╮",
    "row:7": "║ ╔══┴══╗                 ║                         │",
    "row:8": "║ ║ P0x ║                 ║                         │",
    "row:9": "║ ╚═════╝                 ║                         │",
    rows: 24,
  })
  expect(
    drawn(
      "direction TB\nstate P0 {\nP0x --> P0y\nstate P0n {\nP0nz --> P0nw\n}\n}\nP0 --> P0y\nP0n --> P0x : retry\nnote right of P0nw : a note",
    ),
  ).toMatchObject({
    "route:3": "P0n>P0x side-parallel 15,14 15,13 4,13 4,3 @16,12",
    "row:12": "│   │           retry                    │   │",
    "row:13": "│   ╰──────────╮                         │   │",
    "row:3": "│   ▶│ P0x │                             │",
    rows: 30,
  })
  expect(drawn("direction TD\nstate ch <<choice>>\nB --> ch : a long label here")).toMatchObject({
    "route:0": "B>ch side-parallel 4,8 8,8 8,0 2,0 @10,4",
  })
  expect(
    drawn("state P0 {\nstate P0n {\nP0nz --> P0nw\n}\n}\nP0n --> P0n : x<br>yy<br>zzz\nP0n --> P0n"),
  ).toMatchObject({
    "route:2": "P0n>P0n self 13,8 13,13 28,13 28,9",
    "row:10": "│            ├──────────╯   │       │",
    "row:11": "│            │              │       │",
    "row:12": "│            │              │       │",
    "row:13": "│            ╰──────────────╯       │",
    "row:8": "│ ╰──────────┬────────────────────╯ │",
    "row:9": "│            │          ▲   ▲       │",
    rows: 18,
  })
  expect(
    drawn('direction TB\nstate P0 {\nstate "Inside" as P0x\n}\nA --> A : go\nP0 --> C : x<br>yy<br>zzz'),
  ).toMatchObject({
    "route:0": "A>A self 6,11 6,13 9,13 9,12 @11,12",
    "route:1": "P0>C side-parallel 13,3 17,3 17,17 10,17 @19,9",
    "row:0": "╭─ P0 ───────╮",
    "row:1": "│            │",
    "row:10": "    │  A  │      │ yy",
    "row:11": "    ╰─┬───╯      │ zzz",
    "row:12": "      │  ▲ go    │",
    "row:13": "      ╰──╯       │",
    "row:14": "                 │",
    "row:15": "                 │",
    "row:16": "     ╭───╮       │",
    "row:17": "     │ C │◀──────╯",
    "row:18": "     ╰───╯",
    "row:2": "│ ╭────────╮ │",
    "row:3": "│ │ Inside │ ├───╮",
    "row:4": "│ ╰────────╯ │   │",
    "row:5": "│            │   │",
    "row:6": "╰────────────╯   │",
    "row:7": "                 │",
    "row:8": "                 │",
    "row:9": "    ╭─────╮      │ x",
    rows: 19,
  })
  expect(
    drawn('state P0 {\nstate "Inside" as P0x\nP0x --> [*]\n}\nstate P1 {\n[*] --> P1x\nP1x --> P1y\nP1y --> [*]\n}', {
      minStateGap: 8,
    }),
  ).toMatchObject({
    "row:10":
      "                                                                                     │ │                  ╰────┬───╯ │",
    rows: 18,
  })
  expect(
    drawn('state P0 {\n[*] --> P0x\n}\nstate P1 {\nstate "Inside" as P1x\n}\nP0 --> P1 : a<br>b\nA --> [*]', {
      borderStyle: "double",
      arrowHeadStyle: "filled",
    }),
  ).toMatchObject({
    "route:1": "P0>P1 side-parallel 24,3 93,3 93,14 47,14 47,13 @95,5",
    "row:12": "                                              ╚════════════╝                                 │",
    "row:13": "                                               ▲                                             │",
    "row:3": "║ ─────────────▶║ P0x ║ ├────────────────────────────────────────────────────────────────────╮",
    "row:5": "║                       ║                                                                    │ a",
    "row:6": "╚═══════════════════════╝                     ╔═ P1 ═══════╗                                 │ b",
    rows: 15,
  })
  expect(
    drawn(
      'state "Outer" as P0 {\nstate "In" as P0x\n}\nstate P1 {\n}\nP0 --> P0 : x<br>yy<br>zzz\nP0 --> P0 : a<br>b\nP0 --> P0 : go',
    ),
  ).toMatchObject({
    "route:0": "P0>P0 self 3,6 3,8 6,8 6,7 @10,7",
    "route:1": "P0>P0 self 3,6 3,11 7,11 7,7 @1,10",
    "route:2": "P0>P0 self 3,6 3,14 8,14 8,7 @10,13",
    "row:0": "╭─ Outer ╮",
    "row:1": "│        │",
    "row:10": " a │   ││",
    "row:11": " b ├───╯│",
    "row:12": "   │    │",
    "row:13": "   │    │ go",
    "row:14": "   ╰────╯",
    "row:2": "│ ╭────╮ │",
    "row:3": "│ │ In │ │",
    "row:4": "│ ╰────╯ │",
    "row:5": "│        │",
    "row:6": "╰──┬─────╯",
    "row:7": "   │  ▲▲▲ x",
    "row:8": "   ├──╯││ yy",
    "row:9": "   │   ││ zzz",
    rows: 15,
  })
  expect(
    drawn(
      "direction BT\nstate P0 {\n[*] --> P0x\nstate P0n {\n}\n}\nstate P2 {\nstate P2n {\nP2nz --> P2nw\n}\n}\n[*] --> B\nP2n --> A : go",
    ),
  ).toMatchObject({
    "route:3": "P2n>A vertical-elbow 29,17 29,16 23,16 23,1 @27,14",
    "row:1": "                       ▶│ A │",
    "row:14": "                       │   go                ●",
    rows: 43,
  })
  expect(
    drawn(
      "direction BT\nstate P0 {\nP0x --> P0y : x<br>yy<br>zzz\n}\nP0 --> P0 : a long label here\nP0x --> P0x : x<br>yy<br>zzz",
      { borderStyle: "heavy", arrowHeadStyle: "line" },
    ),
  ).toMatchObject({
    "route:0": "P0x>P0y vertical 5,9 5,5 @10,6",
    "route:1": "P0>P0 self 7,13 7,15 14,15 14,14 @16,14",
    "route:2": "P0x>P0x self 4,11 4,13 6,13 6,12 @34,12",
    "row:0": "┏━ P0 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓",
    "row:1": "┃                                    ┃",
    "row:10": "┃ ┃ P0x ┃                            ┃",
    "row:11": "┃ ┗━┬━━━┛                            ┃",
    "row:12": "┃   │ ↑                           x  ┃",
    "row:13": "┃   ╰─╯┬                          yy ┃",
    "row:14": "┃      │      ↑ a long label here zzz┃",
    "row:15": "┗━━━━━━╰──────╯━━━━━━━━━━━━━━━━━━━━━━┛",
    "row:2": "┃ ┏━━━━━┓                            ┃",
    "row:3": "┃ ┃ P0y ┃                            ┃",
    "row:4": "┃ ┗━━━━━┛                            ┃",
    "row:5": "┃    ↑                               ┃",
    "row:6": "┃    │    x                          ┃",
    "row:7": "┃    │    yy                         ┃",
    "row:8": "┃    │    zzz                        ┃",
    "row:9": "┃ ┏━━┴━━┓                            ┃",
    rows: 16,
  })
  expect(
    drawn(
      "state P0 {\n}\nstate P1 {\nP1y --> [*]\nstate P1n {\nP1nz --> P1nw\n}\n}\nP1nw --> P1nz : x<br>yy<br>zzz\nP1nz --> P1n : a long label here",
    ),
  ).toMatchObject({
    "route:3": "P1nz>P1n side-parallel 51,9 52,9 52,13 75,13 @77,11",
    "row:11": "│                                         │  ▲      │                │    │  a long label here│",
    "row:13": "│                                         │  │      ╰────────────────┼─────◀                  │",
    rows: 22,
  })
  expect(
    drawn(
      'direction TB\nstate "Outer" as P0 {\nP0x --> P0y\n}\nA --> A : a long label here\nA --> D : a long label here\nA --> [*]',
      { borderStyle: "double", arrowHeadStyle: "filled" },
    ),
  ).toMatchObject({
    "route:0": "P0x>P0y vertical 5,4 5,8",
    "route:1": "A>A self 4,18 4,20 7,20 7,19 @16,19",
    "route:2": "A>D vertical 5,18 5,22 @16,21",
    "route:3": "A>__end side-parallel 8,17 14,17 14,30 6,30",
    "row:0": "╔═ Outer ═╗",
    "row:1": "║         ║",
    "row:10": "║ ║ P0y ║ ║",
    "row:11": "║ ╚═════╝ ║",
    "row:12": "║         ║",
    "row:13": "╚═════════╝",
    "row:14": "",
    "row:15": "",
    "row:16": "  ╔═════╗",
    "row:17": "  ║  A  ├─────╮",
    "row:18": "  ╚═┬┬══╝     │",
    "row:19": "    ││ ▲      │ a long label here",
    "row:2": "║ ╔═════╗ ║",
    "row:20": "    ╰┼─╯      │",
    "row:21": "     │        │ a long label here",
    "row:22": "     ▼        │",
    "row:23": "   ╔═══╗      │",
    "row:24": "   ║ D ║      │",
    "row:25": "   ╚═══╝      │",
    "row:26": "              │",
    "row:27": "              │",
    "row:28": "              │",
    "row:29": "              │",
    "row:3": "║ ║ P0x ║ ║",
    "row:30": "     ◎◀───────╯",
    "row:4": "║ ╚══┬══╝ ║",
    "row:5": "║    │    ║",
    "row:6": "║    │    ║",
    "row:7": "║    │    ║",
    "row:8": "║    ▼    ║",
    "row:9": "║ ╔═════╗ ║",
    rows: 31,
  })
  expect(
    drawn(
      "state P0 {\nstate P0n {\nP0nz --> P0nw\n}\n}\nA --> P0n : x<br>yy<br>zzz\nA --> P0nw\nB --> P0nz : a<br>b\nP0n --> P0n : retry\nP0x --> P0nw",
    ),
  ).toMatchObject({
    "route:4": "P0n>P0n self 13,8 13,10 24,10 24,9 @21,12",
    "route:5":
      "P0x>P0nw top-feedback 84,11 63,11 63,9 46,9 46,8 34,8 34,2 11,2 11,3 3,3 3,7 4,7 4,8 12,8 12,11 25,11 25,8 24,8 24,5",
    "row:10": "│  │        │╰──────────╯││         │   ╭───╮│            ╭───╮│                    ╭─────╮",
    "row:5": "│ │││ P0nz ├┼───────────▶│ P0nw │││ │",
    "row:7": "│ │╰╮▲──────╯           │ ▲      ││ │",
    "row:8": "│ ╰─╰───────╮┬──────────╰╮│──────│╰───────────╮",
    "row:9": "│  ▲        ││          ▲││      ╰───────────╮╰────────────────╮",
    rows: 22,
  })
  expect(
    drawn(
      'state "Outer" as P0 {\nstate P0n {\nP0nz --> P0nw\n}\n}\nstate P2 {\nstate P2n {\nP2nz --> P2nw\n}\n}\nstate ch <<choice>>\nP0n --> ch : a long label here',
    ),
  ).toMatchObject({
    "route:2": "P0n>ch vertical-elbow 18,8 18,9 88,9 88,11 @20,11",
    "row:10": "╰───────────────────────────────────╯     │ │ ╭──────╮             ╭──────╮ │ │         ▼",
    rows: 17,
  })
  expect(
    drawn(
      'direction RL\nstate "Outer" as P0 {\nP0x --> P0y : retry\n}\nP0y --> A : x<br>yy<br>zzz\nP0y --> P0 : a<br>b\nP0y --> P0x : retry\nnote right of P0y : n',
    ),
  ).toMatchObject({
    "route:2": "P0y>P0 side-parallel 18,3 17,3 17,6 15,6 @14,4",
    "row:1": "         yy     │    ▼───────────────╮        │",
    "row:4": "╰───╯         a ││╰──┬──╯    ╚═══╝    ╰─────╯ │",
    "row:5": "              b ││   │             retry   ▲  │",
    "row:6": "               ▶─╯   │                     │  │",
    "row:8": "                │    │                     │  │",
    "row:9": "                │    │       retry         │  │",
    rows: 12,
  })
  expect(
    drawn(
      'direction TB\nstate P0 {\nP0x --> P0y : go\n}\nstate "Outer" as P1 {\nP1x --> P1y : go\nstate P1n {\nP1nz --> P1nw\n}\n}\nP1nz --> B : retry\nP0y --> ch : retry\nP1y --> P1nw : a long label here',
    ),
  ).toMatchObject({
    "route:3": "P1nz>B side-parallel 11,38 46,38 46,52 43,52 @48,45",
    "row:21": "╭─ Outer ────────────────────────╮",
    "row:22": "│                                │",
    "row:23": "│    ╭─────╮                     │",
    "row:24": "│    │ P1x │                     │",
    "row:25": "│    ╰──┬──╯                     │",
    "row:26": "│       │                        │",
    "row:27": "│       │ go                     │",
    "row:28": "│       │                        │",
    "row:29": "│       ▼                        │",
    "row:30": "│    ╭─────╮                     │",
    "row:31": "│  ╭─┤ P1y │                     │",
    "row:32": "│  │ ╰─────╯                     │",
    "row:33": "│  │                             │",
    "row:34": "│  │ a long label here           │",
    "row:35": "│ ╭│ P1n ────╮                   │",
    "row:36": "│ ││         │                   │",
    "row:37": "│ ││╭──────╮ │                   │",
    "row:38": "│ │││ P1nz ├──────────────────────────────────╮",
    "row:39": "│ ││╰───┬──╯ │                   │            │",
    "row:40": "│ ││    │    │                   │            │",
    "row:41": "│ ││    │    │                   │            │",
    "row:42": "│ ││    │    │                   │            │",
    "row:43": "│ ││    ▼    │                   │            │",
    "row:44": "│ ││╭──────╮ │                   │            │",
    "row:45": "│ │▶│ P1nw │ │                   │            │ retry",
    "row:46": "│ │ ╰──────╯ │                   │            │",
    "row:47": "│ │          │                   │            │",
    "row:48": "│ ╰──────────╯                   │            │",
    "row:49": "│                                │            │",
    "row:50": "╰────────────────────────────────╯            │",
    "row:51": "                                      ╭───╮   │",
    "row:52": "                                      │ B │◀──╯",
    "row:53": "                                      ╰───╯",
    rows: 54,
  })
})
