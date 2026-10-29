import { expect, test } from "bun:test"
import { retry } from "../src/retry"

function failing(errors: unknown[], value = "ok") {
  let calls = 0
  return {
    get calls() {
      return calls
    },
    run: async () => {
      calls++
      if (calls <= errors.length) throw errors[calls - 1]
      return value
    },
  }
}

function recordingWaits() {
  const waits: number[] = []
  const original = globalThis.setTimeout
  globalThis.setTimeout = ((fn: () => void, ms: number) => {
    waits.push(ms)
    return original(fn, 0)
  }) as typeof setTimeout
  return { waits, restore: () => (globalThis.setTimeout = original) }
}

test("every listed message is transient, matched case-insensitively", async () => {
  const messages = [
    "Load failed", "Network connection was lost", "Network request failed", "Failed to fetch",
    "ECONNRESET", "ECONNREFUSED", "EPIPE", "ETIMEDOUT", "Socket hang up",
  ]
  for (const message of messages) expect(await retry(failing([new Error(`x ${message} y`)]).run, { delay: 1 })).toBe("ok")
})

test("a code is read only from an Error", async () => {
  const plain = { code: "ECONNRESET" }
  await expect(retry(failing([plain]).run, { delay: 1 })).rejects.toBe(plain)
})

test("zero attempts never call and reject with nothing", async () => {
  const op = failing([])
  await expect(retry(op.run, { attempts: 0 })).rejects.toBeUndefined()
  expect(op.calls).toBe(0)
})

test("throws a non-transient error at once", async () => {
  const error = new Error("bad request")
  const op = failing([error])
  await expect(retry(op.run, { delay: 1 })).rejects.toBe(error)
  expect(op.calls).toBe(1)
})

test("finds the transient signal in a code or down the cause chain, five deep at most", async () => {
  const coded = Object.assign(new Error("transport"), { code: "ECONNRESET" })
  const nest = (depth: number) => {
    let error: Error = new Error("ETIMEDOUT")
    for (let index = 0; index < depth; index++) error = new Error("wrapped", { cause: error })
    return error
  }
  const op = failing([coded, nest(5), "network request failed"])
  expect(await retry(op.run, { attempts: 4, delay: 1 })).toBe("ok")
  const deep = nest(6)
  await expect(retry(failing([deep]).run, { delay: 1 })).rejects.toBe(deep)
})

test("retryIf replaces the transient check", async () => {
  const op = failing([new Error("anything")])
  expect(await retry(op.run, { delay: 1, retryIf: () => true })).toBe("ok")
})

test("the delay grows by the factor and stops at maxDelay", async () => {
  const clock = recordingWaits()
  try {
    const op = failing(Array.from({ length: 4 }, () => new Error("EPIPE")))
    await retry(op.run, { attempts: 5, delay: 10, factor: 3, maxDelay: 100 })
  } finally {
    clock.restore()
  }
  expect(clock.waits).toEqual([10, 30, 90, 100])
})

test("the defaults are three attempts, 500 ms doubling, then the last attempt's error", async () => {
  const clock = recordingWaits()
  const errors = [1, 2, 3].map((n) => new Error(`EPIPE ${n}`))
  const op = failing(errors)
  try {
    await expect(retry(op.run)).rejects.toBe(errors[2])
  } finally {
    clock.restore()
  }
  expect(op.calls).toBe(3)
  expect(clock.waits).toEqual([500, 1000])
})
