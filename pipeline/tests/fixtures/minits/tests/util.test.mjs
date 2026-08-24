import test from "node:test";
import assert from "node:assert/strict";

import { normalize } from "../src/util.js";

test("normalize trims and lowercases", () => {
  assert.equal(normalize(" A "), "a");
});

test("normalize keeps inner spaces", () => {
  assert.equal(normalize("a b"), "a b");
});
