// tui/bundle-inputs.ts's two pure steps (DEC-028): the patch it makes to the
// build script, and how it lists what the bundler loaded.
import { expect, test } from "bun:test"
import { listInputs, patchBuild } from "./bundle-inputs"

const BUILD = [
  "for (const item of targets) {",
  "  const result = await Bun.build({",
  "    plugins: [",
  "      appAssetsPlugin,",
  "    ],",
  "  })",
  "}",
].join("\n")

test("the recorder is defined before the loop and is the bundler's first plugin", () => {
  const patched = patchBuild(BUILD, "/tmp/out.txt")!
  expect(patched.indexOf("const hobbesRecorder")).toBeLessThan(patched.indexOf("for (const item of targets) {"))
  expect(patched).toContain("    plugins: [\n      hobbesRecorder,\n      appAssetsPlugin,")
  expect(patched).toContain('writeFileSync("/tmp/out.txt"')
})

test("a build script of another shape is refused, not half patched", () => {
  expect(patchBuild("await Bun.build({ plugins: [a] })", "/tmp/out.txt")).toBeNull()
})

test("the list is repo-relative, the repo's files first, each sorted, without repeats", () => {
  const listed = listInputs(
    ["/r/tui/opencode/node_modules/x/a.js", "/r/tui/opencode/packages/b.ts", "/r/tui/opencode/packages/a.ts", "/r/tui/opencode/packages/a.ts"],
    "/r",
  )
  expect(listed).toEqual(["tui/opencode/packages/a.ts", "tui/opencode/packages/b.ts", "tui/opencode/node_modules/x/a.js"])
})
