import { expect, test } from "bun:test"
import { createStateDiagramLayout } from "../../src/state/layout"
import { parseMermaidStateDiagram } from "../../src/state/parser"
import { prepareVisibleStateDiagram } from "../../src/state/visible-model"
import { summary } from "./layout-summary"

// Laid out as the drawing lays it out: from the visible model, composite markers passed through.
const layout = (body: string, minStateGap = 5) =>
  summary(
    createStateDiagramLayout(prepareVisibleStateDiagram(parseMermaidStateDiagram(`stateDiagram-v2\n${body}`)), {
      minStateGap,
    }),
  )

test("left to right, the main path runs on one row; neighbours sit the minimum gap plus 8 apart, or the label between them plus 2 if wider", () => {
  // A box is its label plus 2 each side; a marker is 1 cell, on the row below the top.
  expect(layout("[*] --> A\nA --> B : go\nB --> [*]")).toEqual({
    __start: "0,1 1x1 c0,1",
    A: "14,0 5x3 c16,1",
    B: "32,0 5x3 c34,1",
    __end: "50,1 1x1 c50,1",
  })
  expect(layout("A --> B")).toEqual({ A: "0,0 5x3 c2,1", B: "18,0 5x3 c20,1" })
  expect(layout("A --> B", 1)).toMatchObject({ B: "14,0 5x3 c16,1" })
  expect(layout("A --> B : abcdefghijklmnopqrst")).toMatchObject({ B: "27,0 5x3 c29,1" })
  // The row drops to fit the tallest label anywhere, a marker's top on it.
  expect(layout("[*] --> A\nA --> B : a<br>b<br>c")).toEqual({
    __start: "0,3 1x1 c0,3",
    A: "14,2 5x3 c16,3",
    B: "32,2 5x3 c34,3",
  })
})

test("a label into a composite needs 6 more, not 2, and the composite frames its states 2 out", () => {
  const placed = layout('A --> B : abcdefghijkl\nstate P {\nstate "B" as B\n}')
  expect(placed).toEqual({ A: "0,2 5x3 c2,3", B: "23,2 5x3 c25,3", "[P]": "21,0 9x7 c25,3" })
})

test("the main path takes an end first, then a state that does not lead back, then one with no transition back", () => {
  expect(layout("A --> B\nA --> [*]")).toEqual({ A: "0,0 5x3 c2,1", __end: "18,1 1x1 c18,1", B: "0,6 5x3 c2,7" })
  expect(layout("A --> B\nA --> C\nB --> A")).toEqual({ A: "0,0 5x3 c2,1", C: "18,0 5x3 c20,1", B: "0,6 5x3 c2,7" })
  expect(layout("A --> B\nB --> C\nC --> A\nA --> D\nD --> A")).toEqual({
    A: "0,0 5x3 c2,1",
    B: "18,0 5x3 c20,1",
    C: "36,0 5x3 c38,1",
    D: "0,6 5x3 c2,7",
  })
})

test("with no clear way on, the main path stops; the rest branch beneath, centred under their parent, the canvas shifted", () => {
  expect(layout("A --> B\nB --> A\nA --> C\nC --> A")).toEqual({
    A: "9,0 5x3 c11,1",
    B: "0,6 5x3 c2,7",
    C: "18,6 5x3 c20,7",
  })
})

test("branches that rejoin the path further on sit one row lower, under the state after their parent", () => {
  expect(layout("[*] --> A\nA --> B\nB --> C\nA --> D\nD --> C")).toEqual({
    __start: "0,1 1x1 c0,1",
    A: "14,0 5x3 c16,1",
    B: "32,0 5x3 c34,1",
    C: "50,0 5x3 c52,1",
    D: "32,7 5x3 c34,8",
  })
})

test("a state off the path and off every branch sits on the lower row at its rank's column", () => {
  expect(layout("A --> B\nC --> D")).toEqual({
    A: "0,0 5x3 c2,1",
    B: "18,0 5x3 c20,1",
    C: "36,6 5x3 c38,7",
    D: "54,6 5x3 c56,7",
  })
})

test("right to left mirrors left to right, then shifts right by the widest label on a transition between rows, plus 2", () => {
  expect(layout("direction RL\nA --> B")).toEqual({ A: "18,0 5x3 c20,1", B: "0,0 5x3 c2,1" })
  expect(layout("direction RL\nA --> B\nA --> C : abcd")).toEqual({
    A: "24,0 5x3 c26,1",
    B: "6,0 5x3 c8,1",
    C: "24,6 5x3 c26,7",
  })
})

test("top to bottom, ranks are rows: a lone state centred on the widest lone one, rows 4 apart", () => {
  const down = { __start: "2,0 1x1 c2,0", A: "0,5 5x3 c2,6", B: "0,12 5x3 c2,13", __end: "2,19 1x1 c2,19" }
  expect(layout("direction TB\n[*] --> A\nA --> B\nB --> [*]")).toEqual(down)
  // Bottom to top turns the ranks over.
  expect(layout("direction BT\n[*] --> A\nA --> B\nB --> [*]")).toEqual({
    __end: "2,0 1x1 c2,0",
    B: "0,5 5x3 c2,6",
    A: "0,12 5x3 c2,13",
    __start: "2,19 1x1 c2,19",
  })
})

test("top to bottom, states sharing a rank sit left to right; a row's gap grows for labels, self loops and a choice; a state is two columns wider per self loop than a bare box", () => {
  expect(layout("direction TB\nA --> B : x<br>y\nA --> C")).toEqual({
    A: "0,0 5x3 c2,1",
    B: "0,8 5x3 c2,9",
    C: "18,8 5x3 c20,9",
  })
  // Two loops: A is 2 * 2 + 5 = 9 wide, and B is centred under it; the gap is 3 rows per loop plus 1.
  expect(layout("direction TB\nA --> A\nA --> A\nA --> B")).toEqual({ A: "0,0 9x3 c4,1", B: "2,10 5x3 c4,11" })
  // An unreached state takes the next free rank.
  expect(layout("direction TB\nstate c <<choice>>\nA --> c\nc --> B")).toEqual({
    c: "2,0 1x1 c2,0",
    B: "0,7 5x3 c2,8",
    A: "0,14 5x3 c2,15",
  })
})

test("a composite is at least its title plus 5 wide", () => {
  expect(layout('state "A long composite title" as P {\nstate "A" as A\n}')).toEqual({
    A: "2,2 5x3 c4,3",
    "[P]": "0,0 27x7 c13,3",
  })
  expect(layout("state P {\nA --> B\n}")).toEqual({ A: "2,2 5x3 c4,3", B: "20,2 5x3 c22,3", "[P]": "0,0 27x7 c13,3" })
})

// The cases below were found by planting each fault the cases above miss into a copy of layout.ts and searching random
// state diagrams for one it changes (`bench/subsume/pinned.py` with the state harnesses), each input then shrunk and
// the fewest kept that tell every such fault apart. Each asserts only the entries of its layout (`layout-summary.ts`)
// those faults change, as laid out today: pinned as observed, not derived by hand. The harnesses keep no input that
// shows a known wrong drawing (`state-defects.ts`: composites crossing, a state outside its composite, a route through
// a state), so none of these does. A marker or choice on the left-to-right fallback row (pinned as a defect in
// drawing.test.ts) is not one of those kinds, and 6 of these inputs place one: a fix to that row changes them too.
// Cases above that are redundant against these stay as the readable statement of each rule (Max, 2026-10-30).
test("pinned as observed: notes: the side a note takes, its connector, and the room its composite makes for it", () => {
  expect(
    layout(
      "direction TB\nstate P0 {\nstate P0n {\nP0nz --> P0nw\n}\n}\nnote left of P0nz : a note\nnote left of P0nz : a note",
    ),
  ).toMatchObject({
    P0nw: "36,11 8x3 c40,12",
    P0nz: "36,4 8x3 c40,5",
    "[P0]": "0,0 48x23 c24,11",
    "[P0n]": "2,2 44x19 c24,11",
    "{P0nz-note-0}": "18,4 10x3 c23,5 35,5 28,5",
    "{P0nz-note-1}": "4,17 10x3 c9,18 40,3 16,3 16,18 14,18",
  })
  expect(
    layout(
      'state P0 {\nstate "Inside" as P0x\nstate P0n {\nP0nz --> P0nw\n}\n}\nP0nw --> P0x : a long label here\nP0 --> P0nw : a long label here\nB --> A : x<br>yy<br>zzz\nnote right of B : two<br>lines',
    ),
  ).toMatchObject({
    A: "83,8 5x3 c85,9",
    B: "65,8 5x3 c67,9",
    P0nw: "44,8 8x3 c48,9",
    P0nz: "23,8 8x3 c27,9",
    P0x: "2,2 10x3 c7,3",
    "[P0]": "0,0 56x15 c28,7",
    "[P0n]": "21,6 33x7 c37,9",
    "{B-note-0}":
      "74,14 9x4 c78,16 64,8 63,8 62,8 61,8 60,8 59,8 58,8 57,8 56,8 55,8 54,8 54,7 54,6 55,6 56,6 57,6 58,6 59,6 60,6 61,6 62,6 63,6 64,6 65,6 66,6 67,6 68,6 69,6 70,6 71,6 72,6 72,5 72,4 72,3 72,2 73,2 74,2 75,2 76,2 77,2 78,2 78,3 78,4 78,5 78,6 79,6 80,6 81,6 82,6 83,6 84,6 85,6 86,6 87,6 88,6 89,6 90,6 91,6 92,6 93,6 94,6 95,6 96,6 97,6 98,6 99,6 100,6 101,6 102,6 103,6 104,6 105,6 106,6 107,6 108,6 109,6 110,6 111,6 111,7 111,8 111,9 111,10 110,10 109,10 108,10 107,10 106,10 105,10 104,10 103,10 102,10 101,10 100,10 99,10 98,10 97,10 96,10 95,10 94,10 93,10 92,10 92,11 92,12 92,13 91,13 90,13 89,13 88,13 87,13 86,13 85,13 84,13 83,13 82,13 81,13 80,13 79,13 78,13 77,13 76,13 75,13 74,13 73,13 72,13 72,14 72,15 73,15",
  })
  expect(
    layout('direction BT\nstate "Outer" as P0 {\nstate P0n {\nP0nz --> P0nw\n}\n}\nnote left of P0nw : two<br>lines'),
  ).toMatchObject({
    P0nw: "21,4 8x3 c25,5",
    P0nz: "21,11 8x3 c25,12",
    "[P0]": "0,0 40x18 c20,9",
    "[P0n]": "2,2 36x14 c20,9",
    "{P0nw-note-0}": "4,3 9x4 c8,5 20,5 13,5",
  })
  expect(
    layout(
      "direction BT\nC --> B : a<br>b\nC --> A\nC --> B\nnote left of A : two<br>lines\nnote right of B : a note",
      7,
    ),
  ).toMatchObject({
    A: "20,6 5x3 c22,7",
    B: "0,6 5x3 c2,7",
    C: "0,13 5x3 c2,14",
    "{A-note-0}": "7,5 9x4 c11,7 19,7 19,7 17,7 16,7",
    "{B-note-1}": "9,0 10x3 c14,1 0,5 0,1 7,1 8,1",
  })
  expect(
    layout("state P0 {\n}\nstate P1 {\n}\nstate ch <<choice>>\nnote left of ch : n\nnote left of ch : a note"),
  ).toMatchObject({
    ch: "9,1 1x1 c9,1",
    "{ch-note-0}": "0,0 5x3 c2,1 8,1 5,1",
    "{ch-note-1}": "13,0 10x3 c18,1 10,1 12,1",
  })
  expect(
    layout(
      "state P0 {\n[*] --> P0x\nstate P0n {\nP0nz --> P0nw\n}\n}\nP0 --> P0\nch --> P0x : go\nA --> P0x : a<br>b\nnote right of P0nw : two<br>lines",
    ),
  ).toMatchObject({
    A: "90,11 5x3 c92,12",
    P0nw: "44,11 8x3 c48,12",
    P0nz: "23,11 8x3 c27,12",
    P0x: "2,5 7x3 c5,6",
    "[P0]": "0,0 69x26 c34,13",
    "[P0n]": "21,2 46x22 c44,13",
    ch: "71,11 6x3 c74,12",
    "{P0nw-note-0}":
      "56,3 9x4 c60,5 43,13 43,14 43,15 43,16 42,16 41,16 40,16 39,16 38,16 37,16 36,16 35,16 34,16 33,16 32,16 31,16 30,16 29,16 28,16 27,16 27,17 27,18 27,19 27,20 27,21 27,22 28,22 29,22 30,22 31,22 32,22 33,22 34,22 35,22 36,22 37,22 38,22 39,22 40,22 41,22 42,22 43,22 44,22 45,22 46,22 47,22 48,22 49,22 50,22 51,22 52,22 53,22 54,22 55,22 56,22 57,22 58,22 59,22 59,21 59,20 59,19 59,18 59,17 59,16 59,15 59,14 59,13 59,12 59,11 59,10 59,9 59,8 59,7 58,7 57,7 56,7 55,7 54,7 54,6 54,5 55,5",
  })
  expect(
    layout("state ch <<choice>>\nC --> C : retry\nB --> ch\nA --> C : a<br>b\nnote right of B : two<br>lines"),
  ).toMatchObject({
    A: "58,7 5x3 c60,8",
    B: "40,7 5x3 c42,8",
    C: "20,7 7x3 c23,8",
    ch: "0,2 1x1 c0,2",
    "{B-note-0}": "49,12 9x4 c53,14 45,8 45,13 47,13 48,13",
  })
  expect(layout("state ch <<choice>>\nch --> D\nnote left of D : a note", 1)).toMatchObject({
    D: "24,0 5x3 c26,1",
    ch: "14,1 1x1 c14,1",
    "{D-note-0}": "0,6 10x3 c5,7 23,0 12,0 12,7 10,7",
  })
  expect(
    layout(
      "state P0 {\nstate P0n {\nP0nz --> P0nw\n}\n}\n[*] --> A\nP0n --> C : a long label here\nC --> B\nnote left of C : two<br>lines",
    ),
  ).toMatchObject({
    A: "14,1 5x3 c16,2",
    B: "102,7 5x3 c104,8",
    C: "84,7 5x3 c86,8",
    P0nw: "63,7 8x3 c67,8",
    P0nz: "42,7 8x3 c46,8",
    "[P0]": "38,3 37x11 c56,8",
    "[P0n]": "40,5 33x7 c56,8",
    __start: "0,2 1x1 c0,2",
    "{C-note-0}":
      "71,1 9x4 c75,3 83,9 82,9 81,9 80,9 79,9 78,9 77,9 76,9 75,9 74,9 73,9 72,9 71,9 71,8 71,7 71,6 71,5 70,5 70,4 70,3 70,2 70,1 70,0 71,0 72,0 73,0 74,0 75,0 76,0 77,0 78,0 79,0 80,0 81,0 81,1 81,2 81,3 80,3",
  })
  expect(layout('state "Outer" as P0 {\n[*] --> P0x\n}\nstate P1 {\n}\nnote left of P0x : a note', 3)).toMatchObject({
    "P0.__start": "4,7 1x1 c4,7",
    P0x: "16,6 7x3 c19,7",
    "[P0]": "0,0 25x11 c12,5",
    "{P0x-note-0}": "2,1 10x3 c7,2 15,5 15,2 13,2 12,2",
  })
  expect(layout("C --> A : a long label here\nnote right of B : a note\nnote right of A : two<br>lines")).toMatchObject(
    { A: "24,1 5x3 c26,2", C: "0,1 5x3 c2,2", "{A-note-1}": "33,0 9x4 c37,2 29,2 29,2 31,2 32,2" },
  )
  expect(
    layout(
      "direction TB\nB --> A : go\nA --> A\nA --> A : a<br>b\nA --> A : go\nA --> B : x<br>yy<br>zzz\nB --> [*]\nnote right of A : a note",
      3,
    ),
  ).toMatchObject({
    A: "0,7 11x3 c5,8",
    B: "0,0 5x3 c2,1",
    __end: "22,8 1x1 c22,8",
    "{A-note-0}": "15,12 10x3 c20,13 11,10 11,13 13,13 14,13",
  })
  expect(
    layout(
      'state P0 {\nstate "In" as P0x\n}\nstate P1 {\nP1x --> P1y : a long label here\n}\nP1x --> P1 : a long label here\nP1y --> P0 : a long label here\nB --> P1y\nnote right of P1x : a note',
    ),
  ).toMatchObject({
    B: "62,8 5x3 c64,9",
    P0x: "2,2 6x3 c5,3",
    P1x: "22,8 7x3 c25,9",
    P1y: "42,8 7x3 c45,9",
    "[P0]": "0,0 10x7 c5,3",
    "[P1]": "17,0 34x13 c34,6",
    "{P1x-note-0}":
      "33,1 10x3 c38,2 21,8 21,7 20,7 19,7 18,7 18,6 18,5 18,4 18,3 19,3 20,3 21,3 22,3 23,3 24,3 25,3 26,3 27,3 28,3 29,3 30,3 31,3 31,2 32,2",
  })
  expect(
    layout(
      'state P0 {\nP0x --> P0y\nstate P0n {\n}\n}\nstate "Outer" as P2 {\nP2y --> [*]\n}\nnote left of P0x : two<br>lines',
    ),
  ).toMatchObject({
    P0x: "17,2 7x3 c20,3",
    P0y: "37,2 7x3 c40,3",
    "P2.__end": "77,9 1x1 c77,9",
    P2y: "57,8 7x3 c60,9",
    "[P0]": "0,0 46x7 c23,3",
    "[P2]": "55,6 25x7 c67,9",
    "{P0x-note-0}": "2,1 9x4 c6,3 16,3 11,3",
  })
  expect(
    layout(
      'direction TD\nstate "A long composite title" as P0 {\nP0x --> P0y : retry\nstate P0n {\n}\n}\nstate "A long composite title" as P2 {\nstate P2n {\n}\n}\nnote right of P0y : two<br>lines',
    ),
  ).toMatchObject({
    P0x: "2,2 7x3 c5,3",
    P0y: "2,9 7x3 c5,10",
    "[P0]": "0,0 27x14 c13,7",
    "{P0y-note-0}": "13,8 9x4 c17,10 9,10 9,10 11,10 12,10",
  })
})

test("pinned as observed: composite frames: their margins, room for inner routes, and outside states kept clear", () => {
  expect(
    layout(
      "direction BT\nstate P0 {\nP0x --> [*]\nstate P0n {\nP0nz --> P0nw\n}\n}\nP0x --> P0nw : retry\nnote right of P0nz : n\nnote right of P0nz : two<br>lines",
      6,
    ),
  ).toMatchObject({
    "P0.__end": "33,17 1x1 c33,17",
    P0nw: "19,16 8x3 c23,17",
    P0nz: "4,9 8x3 c8,10",
    P0x: "34,23 7x3 c37,24",
    "[P0]": "0,0 43x28 c21,14",
    "[P0n]": "2,2 27x19 c15,11",
    "{P0nz-note-0}": "16,9 5x3 c18,10 12,10 12,10 14,10 15,10",
    "{P0nz-note-1}": "16,3 9x4 c20,5 12,8 12,5 14,5 15,5",
  })
  expect(
    layout(
      "direction RL\nstate P0 {\nP0x --> P0y\n}\n[*] --> D\nA --> B : a long label here\nP0y --> P0 : go\nC --> [*]\nnote right of P0y : a note",
    ),
  ).toMatchObject({
    A: "50,6 5x3 c52,7",
    B: "32,6 5x3 c34,7",
    C: "14,6 5x3 c16,7",
    D: "116,0 5x3 c118,1",
    P0x: "88,6 7x3 c91,7",
    P0y: "68,6 7x3 c71,7",
    "[P0]": "66,0 31x11 c81,5",
    __end: "0,7 1x1 c0,7",
    __start: "134,1 1x1 c134,1",
    "{P0y-note-0}": "79,1 10x3 c84,2 75,5 75,2 77,2 78,2",
  })
  expect(
    layout('direction BT\nstate P0 {\nP0y --> [*]\n}\nstate "A long composite title" as P1 {\n[*] --> P1x\n}'),
  ).toMatchObject({
    "P0.__end": "5,2 1x1 c5,2",
    P0y: "2,7 7x3 c5,8",
    "P1.__start": "27,21 1x1 c27,21",
    P1x: "24,14 7x3 c27,15",
    "[P0]": "0,0 18x12 c9,6",
    "[P1]": "22,12 27x12 c35,18",
  })
  expect(
    layout(
      "state P0 {\n[*] --> P0x\nP0x --> P0y : go\n}\n[*] --> B\nA --> P0\nP0 --> B : x<br>yy<br>zzz\nB --> P0 : retry\nnote right of P0x : a note",
    ),
  ).toMatchObject({
    A: "72,16 5x3 c74,17",
    B: "14,10 5x3 c16,11",
    P0x: "32,10 7x3 c35,11",
    P0y: "52,10 7x3 c55,11",
    "[P0]": "30,0 31x15 c45,7",
    __start: "0,11 1x1 c0,11",
    "{P0x-note-0}": "43,1 10x3 c48,2 31,10 31,2 41,2 42,2",
  })
  expect(
    layout(
      'direction TD\nstate "A long composite title" as P0 {\nP0y --> [*]\nstate P0n {\nP0nz --> P0nw\n}\n}\nP0 --> B\nP0y --> P0nz : a long label here',
    ),
  ).toMatchObject({
    B: "31,9 5x3 c33,10",
    P0nw: "4,16 8x3 c8,17",
    P0nz: "4,9 8x3 c8,10",
    P0y: "5,2 7x3 c8,3",
    "[P0]": "0,0 27x23 c13,11",
    "[P0n]": "2,7 12x14 c8,14",
  })
  expect(
    layout("direction TD\nstate P0 {\nstate P0n {\nP0nz --> P0nw\n}\n}\nstate P2 {\n}\nP0nz --> P0nw : retry"),
  ).toMatchObject({
    P0nw: "4,11 8x3 c8,12",
    P0nz: "4,4 8x3 c8,5",
    "[P0]": "0,0 28x18 c14,9",
    "[P0n]": "2,2 24x14 c14,9",
  })
  expect(
    layout('direction TB\nstate "Outer" as P0 {\nstate "Inside" as P0x\nP0x --> [*]\n}\nstate P1 {\n}\nP0x --> B', 3),
  ).toMatchObject({
    B: "18,9 5x3 c20,10",
    "P0.__end": "2,10 1x1 c2,10",
    P0x: "2,2 10x3 c7,3",
    "[P0]": "0,0 14x13 c7,6",
  })
  expect(
    layout(
      'state P0 {\n[*] --> P0x\nP0y --> [*]\n}\nstate P1 {\nstate "Inside" as P1x\n}\nP0x --> B : a long label here',
    ),
  ).toMatchObject({
    B: "89,2 5x3 c91,3",
    "P0.__end": "82,9 1x1 c82,9",
    "P0.__start": "2,3 1x1 c2,3",
    P0x: "16,2 7x3 c19,3",
    P0y: "62,8 7x3 c65,9",
    P1x: "160,8 10x3 c165,9",
    "[P0]": "0,0 85x13 c42,6",
    "[P1]": "158,6 14x7 c165,9",
  })
  expect(
    layout(
      'direction BT\nstate "A long composite title" as P0 {\n[*] --> P0x\nP0x --> P0y : a<br>b\n}\n[*] --> C\nC --> P0 : go\nC --> P0y',
    ),
  ).toMatchObject({
    C: "2,10 5x3 c4,11",
    P0x: "2,2 7x3 c5,3",
    P0y: "22,2 7x3 c25,3",
    "[P0]": "0,0 31x7 c15,3",
    __start: "4,17 1x1 c4,17",
  })
  expect(
    layout(
      'direction BT\nstate P0 {\n}\nstate "Outer" as P1 {\nP1x --> P1y\nstate P1n {\nP1nz --> P1nw\n}\n}\nP1n --> P1x\nP1nw --> P1n : a<br>b',
    ),
  ).toMatchObject({
    P1nw: "4,4 8x3 c8,5",
    P1nz: "4,12 8x3 c8,13",
    P1x: "5,26 7x3 c8,27",
    P1y: "5,19 7x3 c8,20",
    "[P1]": "0,0 34x31 c17,15",
    "[P1n]": "2,2 19x15 c11,9",
  })
  expect(layout("direction RL\nstate P0 {\n}\nstate P1 {\nP1x --> P1y\n}\nP1x --> P1y : x<br>yy<br>zzz")).toMatchObject(
    { P1x: "22,2 7x3 c25,3", P1y: "2,2 7x3 c5,3", "[P1]": "0,0 31x7 c15,3" },
  )
  expect(
    layout("direction BT\nstate P0 {\n}\nstate P1 {\nP1y --> [*]\n}\nP1y --> P0x : a long label here"),
  ).toMatchObject({ P0x: "22,1 7x3 c25,2", "P1.__end": "2,2 1x1 c2,2", P1y: "2,8 7x3 c5,9", "[P1]": "0,0 18x13 c9,6" })
  expect(
    layout("direction BT\nstate P0 {\n}\nstate P1 {\nstate P1n {\nP1nz --> P1nw\n}\n}\nD --> P1nw : go"),
  ).toMatchObject({ D: "27,0 5x3 c29,1" })
  expect(
    layout(
      "direction TD\nstate P0 {\nP0y --> [*]\nstate P0n {\nP0nz --> P0nw\n}\n}\nstate P2 {\n}\nP0 --> P0n : a<br>b",
    ),
  ).toMatchObject({
    P0nw: "4,17 8x3 c8,18",
    P0nz: "4,10 8x3 c8,11",
    P0y: "5,2 7x3 c8,3",
    "[P0]": "0,0 24x24 c12,12",
    "[P0n]": "2,8 12x14 c8,15",
  })
  expect(
    layout(
      'state P0 {\nstate "In" as P0x\nstate P0n {\nP0nz --> P0nw\n}\n}\n[*] --> B\nB --> P0x : a long label here\nB --> [*]',
    ),
  ).toMatchObject({ B: "121,0 5x3 c123,1", __end: "139,1 1x1 c139,1" })
  expect(
    layout(
      'direction TD\nstate "A long composite title" as P0 {\nstate P0n {\nP0nz --> P0nw\n}\n}\nP0y --> P0nz : a long label here',
    ),
  ).toMatchObject({ P0y: "31,18 7x3 c34,19" })
  expect(
    layout(
      "state P0 {\n[*] --> P0x\nP0x --> P0y : a<br>b\nstate P0n {\nP0nz --> P0nw\n}\n}\nA --> P0x : a<br>b\nP0x --> P0\nnote right of P0nw : two<br>lines\nnote left of P0nz : two<br>lines",
    ),
  ).toMatchObject({
    A: "162,9 5x3 c164,10",
    P0nw: "65,9 8x3 c69,10",
    P0nz: "44,9 8x3 c48,10",
    P0x: "2,3 7x3 c5,4",
    P0y: "92,3 7x3 c95,4",
    "[P0]": "0,0 101x16 c50,8",
    "[P0n]": "29,2 59x12 c58,8",
    "{P0nw-note-0}": "77,3 9x4 c81,5 73,10 73,5 75,5 76,5",
    "{P0nz-note-1}": "31,8 9x4 c35,10 43,10 43,10 41,10 40,10",
  })
})

test("pinned as observed: the main path, ranks, branches and the states off the path", () => {
  expect(
    layout(
      'state "A long composite title" as P0 {\nP0x --> P0y : retry\n}\nP0y --> P0x : go\nP0y --> ch\nch --> ch : a long label here\nP0x --> P0y : go',
    ),
  ).toMatchObject({ P0x: "2,2 7x3 c5,3", P0y: "2,8 7x3 c5,9", "[P0]": "0,0 27x13 c13,6", ch: "42,8 7x3 c45,9" })
  expect(layout("C --> A : go\nB --> A : a long label here\nC --> B : retry")).toMatchObject({
    A: "18,0 5x3 c20,1",
    B: "0,6 5x3 c2,7",
  })
  expect(layout("state P0 {\n}\nA --> B : go\nP0 --> ch : x<br>yy<br>zzz\nB --> P0")).toMatchObject({
    A: "0,2 5x3 c2,3",
    B: "18,2 5x3 c20,3",
    ch: "36,2 6x3 c39,3",
  })
  expect(
    layout(
      "state P0 {\n}\nstate P1 {\nP1x --> P1y : x<br>yy<br>zzz\n}\n[*] --> A\nA --> P1x\nA --> C : a<br>b\nP1y --> A",
    ),
  ).toMatchObject({
    A: "14,2 5x3 c16,3",
    C: "32,2 5x3 c34,3",
    P1x: "13,8 7x3 c16,9",
    P1y: "60,8 7x3 c63,9",
    "[P1]": "11,6 58x7 c40,9",
    __start: "0,3 1x1 c0,3",
  })
  expect(
    layout(
      'state "Outer" as P0 {\nP0y --> [*]\n}\nstate P1 {\n}\nP0y --> P0 : x<br>yy<br>zzz\nP0y --> P1x : x<br>yy<br>zzz',
    ),
  ).toMatchObject({ "P0.__end": "22,3 1x1 c22,3", P0y: "2,2 7x3 c5,3", P1x: "2,8 7x3 c5,9", "[P0]": "0,0 25x7 c12,3" })
  expect(
    layout(
      "direction TB\nD --> D : go\nB --> D : go\nA --> A : a<br>b\nB --> [*]\nnote right of A : a note\nnote right of A : two<br>lines",
    ),
  ).toMatchObject({
    A: "0,14 7x3 c3,15",
    B: "1,7 5x3 c3,8",
    D: "0,0 7x3 c3,1",
    __end: "3,22 1x1 c3,22",
    "{A-note-0}": "11,14 10x3 c16,15 7,15 7,15 9,15 10,15",
    "{A-note-1}": "11,8 9x4 c15,10 7,13 7,10 9,10 10,10",
  })
  expect(layout("B --> C : go\nC --> A\nB --> A : a<br>b\nC --> [*]")).toMatchObject({ A: "18,7 5x3 c20,8" })
  expect(layout("direction TD\nstate ch <<choice>>\nch --> A\nch --> B : a long label here", 8)).toMatchObject({
    ch: "0,0 1x1 c0,0",
  })
  expect(layout("state P0 {\nP0x --> P0y : a long label here\n}\nP0x --> P0y : x<br>yy<br>zzz")).toMatchObject({
    P0x: "2,2 7x3 c5,3",
    P0y: "28,2 7x3 c31,3",
    "[P0]": "0,0 37x7 c18,3",
  })
  expect(
    layout("state P0 {\n[*] --> P0x\nP0x --> [*]\n}\n[*] --> B\nA --> B : x<br>yy<br>zzz\nP0x --> A"),
  ).toMatchObject({
    A: "17,8 5x3 c19,9",
    B: "56,8 5x3 c58,9",
    "P0.__end": "36,3 1x1 c36,3",
    "P0.__start": "2,3 1x1 c2,3",
    P0x: "16,2 7x3 c19,3",
    "[P0]": "0,0 39x7 c19,3",
    __start: "74,9 1x1 c74,9",
  })
  expect(
    layout("C --> B\nB --> C\nC --> C : a long label here\nnote left of B : two<br>lines\nnote left of B : a note"),
  ).toMatchObject({
    B: "20,6 5x3 c22,7",
    C: "0,6 7x3 c3,7",
    "{B-note-0}": "7,0 9x4 c11,2 19,5 19,2 17,2 16,2",
    "{B-note-1}": "6,15 10x3 c11,16 25,6 25,16 17,16 16,16",
  })
  expect(
    layout(
      "state P0 {\n[*] --> P0x\nP0x --> P0y : a<br>b\nP0y --> [*]\n}\nstate ch <<choice>>\n[*] --> B\nP0y --> A\nB --> [*]",
    ),
  ).toMatchObject({
    A: "37,8 5x3 c39,9",
    B: "128,8 5x3 c130,9",
    "P0.__end": "56,3 1x1 c56,3",
    "P0.__start": "2,3 1x1 c2,3",
    P0x: "16,2 7x3 c19,3",
    P0y: "36,2 7x3 c39,3",
    "[P0]": "0,0 59x7 c29,3",
    __end: "114,9 1x1 c114,9",
    __start: "86,9 1x1 c86,9",
    ch: "72,9 1x1 c72,9",
  })
  expect(
    layout(
      'state "A long composite title" as P0 {\nstate P0n {\n}\n}\nP0y --> P0y\nB --> P0y : retry\nP0y --> P0nz : a long label here',
    ),
  ).toMatchObject({ B: "36,6 5x3 c38,7", P0nz: "26,0 8x3 c30,1", P0y: "0,0 7x3 c3,1" })
  expect(
    layout(
      'state P0 {\nstate "In" as P0x\n}\nstate "A long composite title" as P1 {\nstate "Inside" as P1x\nP1x --> [*]\nstate P1n {\n}\n}\n[*] --> B',
      4,
    ),
  ).toMatchObject({
    B: "13,0 5x3 c15,1",
    P0x: "36,6 6x3 c39,7",
    "P1.__end": "88,7 1x1 c88,7",
    P1x: "66,6 10x3 c71,7",
    "[P0]": "34,4 10x7 c39,7",
    "[P1]": "64,4 27x7 c77,7",
    __start: "0,1 1x1 c0,1",
  })
})
