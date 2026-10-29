import { RGBA } from "@opentui/core"
import { expect, test } from "bun:test"
import { resolveOpenCodeDiagramPalette } from "../src/palette"

const rgb = (r: number, g: number, b: number) => RGBA.fromInts(r, g, b, 255)
const ints = (palette: Record<string, RGBA>) => Object.fromEntries(Object.entries(palette).map(([key, value]) => [key, value.toInts()]))

const input = {
  text: rgb(200, 100, 0),
  subdued: rgb(100, 200, 50),
  info: rgb(1, 1, 1),
  success: rgb(2, 2, 2),
  warning: rgb(3, 3, 3),
  background: rgb(0, 0, 0),
  accent: { soft: rgb(4, 4, 4), clear: rgb(5, 5, 5) },
}

function theme(categorical: Array<Record<200 | 300 | 700 | 800, RGBA>>) {
  return {
    text: {
      base: input.text,
      muted: input.subdued,
      feedback: { info: { base: input.info }, success: { base: input.success }, warning: { base: input.warning } },
    },
    background: { base: input.background },
    categorical,
  }
}
const shade = (n: number) => ({ 200: rgb(n, 2, 0), 300: rgb(n, 3, 0), 700: rgb(n, 7, 0), 800: rgb(n, 8, 0) })

test("a theme names every role: text blended toward subdued for secondary and muted, its accent the fourth categorical colour, 300/200 in dark mode and 700/800 in light", () => {
  const four = theme([shade(0), shade(1), shade(2), shade(3)])
  expect(ints(resolveOpenCodeDiagramPalette(four, "dark"))).toEqual({
    text: [200, 100, 0, 255],
    primary: [200, 100, 0, 255],
    secondary: [150, 150, 25, 255],
    muted: [130, 170, 35, 255],
    warning: [1, 1, 1, 255],
    background: [0, 0, 0, 255],
    request: [2, 2, 2, 255],
    response: [3, 3, 3, 255],
    note: [200, 100, 0, 255],
    noteBackground: [25, 50, 13, 255],
    boxText: [200, 100, 0, 255],
    boxBorder: [130, 170, 35, 255],
    line: [100, 200, 50, 255],
    labelBackground: [200, 100, 0, 20],
    group: [3, 3, 0, 255],
    groupText: [3, 3, 0, 255],
    marker: [150, 150, 25, 255],
    noteBorder: [3, 3, 0, 255],
    noteText: [3, 2, 0, 255],
    noteConnector: [3, 3, 0, 255],
  })
  const light = resolveOpenCodeDiagramPalette(four, "light")
  expect([light.group.toInts(), light.noteText.toInts()]).toEqual([
    [3, 7, 0, 255],
    [3, 8, 0, 255],
  ])
})

test("a theme with fewer than four categorical colours takes its first as the accent", () => {
  const dark = resolveOpenCodeDiagramPalette(theme([shade(9), shade(1)]), "dark")
  expect([dark.group.toInts(), dark.noteText.toInts()]).toEqual([
    [9, 3, 0, 255],
    [9, 2, 0, 255],
  ])
})
