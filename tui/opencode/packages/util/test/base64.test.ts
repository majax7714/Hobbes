import { expect, test } from "bun:test"

// Bun has the native codecs, so only a copy loaded without them runs this module's own fallback;
// the copy reads them once, at load.
const native = await import("../src/base64")
const saved = { encode: Uint8Array.prototype.toBase64, decode: Uint8Array.fromBase64 }
// @ts-expect-error the fallback is for runtimes without them
delete Uint8Array.prototype.toBase64
// @ts-expect-error the fallback is for runtimes without them
delete Uint8Array.fromBase64
const { base64ToBytes, bytesToBase64 } = await import("../src/base64?fallback")
Uint8Array.prototype.toBase64 = saved.encode
Uint8Array.fromBase64 = saved.decode

test("the fallback round-trips bytes through standard base64, across its 32 KiB chunks", () => {
  expect(bytesToBase64(new Uint8Array([9, 251, 255, 62, 63]))).toBe("Cfv/Pj8=")
  expect([...base64ToBytes("Cfv/Pj8=")]).toEqual([9, 251, 255, 62, 63])
  const large = Uint8Array.from({ length: 0x8000 * 2 + 3 }, (_, index) => (index * 7) % 256)
  const encoded = bytesToBase64(large)
  expect(encoded).toBe(Buffer.from(large).toString("base64"))
  expect(base64ToBytes(encoded)).toEqual(large)
})

test("with the native codecs, the same bytes come out", () => {
  expect(native.bytesToBase64(new Uint8Array([9, 251, 255, 62, 63]))).toBe("Cfv/Pj8=")
  expect([...native.base64ToBytes("Cfv/Pj8=")]).toEqual([9, 251, 255, 62, 63])
})
