import { expect, test } from "bun:test"
import { base64Decode, base64Encode, checksum, sampledChecksum } from "../src/encode"

test("base64Encode is URL-safe and unpadded, and base64Decode reverses it", () => {
  const text = "ü>?~"
  expect(base64Encode(text)).toBe("w7w-P34")
  expect(base64Decode("w7w-P34")).toBe(text)
  expect(base64Encode("???")).toBe("Pz8_")
  expect(base64Decode("Pz8_")).toBe("???")
})

test("checksum is FNV-1a in base 36, and nothing for empty content", () => {
  expect(checksum("")).toBeUndefined()
  expect(checksum("a")).toBe((0xe40c292c).toString(36))
  expect(checksum("ab")).not.toBe(checksum("ba"))
})

test("sampledChecksum hashes the whole text up to the limit", () => {
  expect(sampledChecksum("")).toBeUndefined()
  expect(sampledChecksum("abc", 3)).toBe(checksum("abc"))
})

test("sampledChecksum over the limit samples five 4 KiB windows centred on its quarters", () => {
  const text = Array.from({ length: 20_001 }, (_, index) => String.fromCharCode(97 + (index % 26))).join("")
  const sampled = sampledChecksum(text, 10_000)!
  const windows = [0, 2952, 7952, 12952, 13857].map((start) => checksum(text.slice(start, start + 4096)))
  expect(sampled).toBe(`20001:${windows.join(":")}`)
  // Quarters of 20,001 are fractional: the points round down.
  // A change outside every window does not move it; one inside does.
  const outside = text.slice(0, 19000) + "#" + text.slice(19001)
  const inside = text.slice(0, 9000) + "#" + text.slice(9001)
  expect(sampledChecksum(outside, 10_000)).toBe(sampled)
  expect(sampledChecksum(inside, 10_000)).not.toBe(sampled)
})
