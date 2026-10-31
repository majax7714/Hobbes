import { expect, test } from "bun:test"
import {
  DEFAULT_STATE_ARROW_HEAD_STYLE,
  DEFAULT_STATE_BORDER_STYLE,
  normalizeStateMinStateGap,
} from "../../src/state/options"

test("the minimum state gap is truncated toward zero and at least 1; a missing or non-finite one is 5", () => {
  expect(
    [undefined, Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY, 0, -3.7, 0.9, 12.7, 30].map(
      normalizeStateMinStateGap,
    ),
  ).toEqual([5, 5, 5, 5, 1, 1, 1, 12, 30])
  expect([DEFAULT_STATE_BORDER_STYLE, DEFAULT_STATE_ARROW_HEAD_STYLE]).toEqual(["rounded", "filled"])
})
