import { RGBA } from "@opentui/core"
import { expect, test } from "bun:test"
import {
  blendColor,
  colorsEqual,
  createColorRampTheme,
  DIAGRAM_FADE_STEPS,
  numberedStyleKeys,
  rgba,
} from "../../src/core/color/style"

const black = RGBA.fromInts(0, 0, 0, 255)
const white = RGBA.fromInts(255, 255, 255, 255)

test("the fade steps are one to five and a style key is the prefix and the step", () => {
  expect(DIAGRAM_FADE_STEPS).toEqual([1, 2, 3, 4, 5])
  expect(numberedStyleKeys("fade", [1, 3])).toEqual(["fade1", "fade3"])
})

test("an rgb triple is an opaque colour", () => {
  expect(rgba([10, 20, 30]).toInts()).toEqual([10, 20, 30, 255])
})

test("blending mixes every channel, alpha too, by the amount from the first colour toward the second", () => {
  const to = RGBA.fromInts(100, 200, 50, 55)
  expect(blendColor(black, to, 0).toInts()).toEqual([0, 0, 0, 255])
  expect(blendColor(black, to, 0.5).toInts()).toEqual([50, 100, 25, 155])
  expect(blendColor(black, to, 1).toInts()).toEqual([100, 200, 50, 55])
})

test("blending with a missing side gives the other side unchanged, and two missing give none", () => {
  expect(blendColor(undefined, white, 0.5)).toBe(white)
  expect(blendColor(black, undefined, 0.5)).toBe(black)
  expect(blendColor(undefined, undefined, 0.5)).toBeUndefined()
})

test("colours are equal by value; two missing are equal, one missing is not", () => {
  expect(colorsEqual(RGBA.fromInts(1, 2, 3, 4), RGBA.fromInts(1, 2, 3, 4))).toBe(true)
  expect(colorsEqual(RGBA.fromInts(1, 2, 3, 4), RGBA.fromInts(1, 2, 3, 5))).toBe(false)
  expect(colorsEqual(undefined, undefined)).toBe(true)
  expect(colorsEqual(black, undefined)).toBe(false)
  expect(colorsEqual(undefined, black)).toBe(false)
})

test("a ramp spaces its styles evenly strictly between the two ends, rounding each channel", () => {
  const ramp = createColorRampTheme(["a", "b", "c"], black, white)
  expect(Object.keys(ramp)).toEqual(["a", "b", "c"])
  expect(ramp.a.toInts()).toEqual([64, 64, 64, 255])
  expect(ramp.b.toInts()).toEqual([128, 128, 128, 255])
  expect(ramp.c.toInts()).toEqual([191, 191, 191, 255])
  expect(createColorRampTheme(["a", "b"], undefined, white)).toEqual({ a: white, b: white })
})
