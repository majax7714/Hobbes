import { expect, test } from "bun:test"
import fs from "fs/promises"
import os from "os"
import path from "path"
import { Effect } from "effect"
import { Global } from "../src/global"

test("Path.home is OPENCODE_TEST_HOME when set, read on each access", () => {
  const before = process.env.OPENCODE_TEST_HOME
  try {
    process.env.OPENCODE_TEST_HOME = "/elsewhere"
    expect(Global.Path.home).toBe("/elsewhere")
    delete process.env.OPENCODE_TEST_HOME
    expect(Global.Path.home).toBe(os.homedir())
  } finally {
    if (before === undefined) delete process.env.OPENCODE_TEST_HOME
    else process.env.OPENCODE_TEST_HOME = before
  }
})

test("every global path is opencode's own, and bin, log and repos sit under cache and data", () => {
  for (const dir of [Global.Path.data, Global.Path.cache, Global.Path.config, Global.Path.state, Global.Path.tmp])
    expect(path.basename(dir)).toBe("opencode")
  expect(Global.Path.bin).toBe(path.join(Global.Path.cache, "bin"))
  expect(Global.Path.log).toBe(path.join(Global.Path.data, "log"))
  expect(Global.Path.repos).toBe(path.join(Global.Path.data, "repos"))
})

test("layerWith creates every directory and canonicalizes a default tmp", async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "global-test-"))
  try {
    const dirs = Object.fromEntries(
      ["data", "config", "state", "log", "bin", "repos"].map((key) => [key, path.join(root, "link", key)]),
    )
    await fs.mkdir(path.join(root, "real"))
    await fs.symlink(path.join(root, "real"), path.join(root, "link"))
    const read = Effect.gen(function* () {
      return yield* Global.Service
    })
    const service = await Effect.runPromise(read.pipe(Effect.provide(Global.layerWith(dirs))))
    for (const dir of Object.values(dirs)) expect((await fs.stat(dir)).isDirectory()).toBe(true)
    expect(service.tmp).toBe(await fs.realpath(Global.Path.tmp))

    const tmp = path.join(root, "link", "tmp")
    const given = await Effect.runPromise(read.pipe(Effect.provide(Global.layerWith({ ...dirs, tmp }))))
    expect(given.tmp).toBe(tmp)
    expect((await fs.stat(tmp)).isDirectory()).toBe(true)
  } finally {
    await fs.rm(root, { recursive: true, force: true })
  }
})
