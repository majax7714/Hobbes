import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test"
import { chmodSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs"
import * as realFs from "node:fs/promises"
import { tmpdir } from "node:os"
import path from "node:path"
import { ShellSelect } from "../../src/shell/select"

// `/etc/shells` is the host's, so `list`'s reading of it is given a text of ours. Unset, the real file is read.
// The originals are copied first: once the module is loaded, the mock rewrites `realFs` too, and a mock calling
// `realFs.readFile` calls itself (run beside parse.test.ts, that spun forever, past any test's timeout).
let etcShells: string | undefined
const realReadFile = realFs.readFile
const realModule = { ...realFs }
mock.module("fs/promises", () => ({
  ...realModule,
  readFile: (file: string, encoding?: BufferEncoding) => {
    if (file !== "/etc/shells" || etcShells === undefined) return realReadFile(file, encoding)
    return Promise.resolve(encoding === "utf8" ? etcShells : Buffer.from(etcShells))
  },
}))

const saved = { PATH: process.env.PATH, SHELL: process.env.SHELL, COMSPEC: process.env.COMSPEC }
let bin: string
let other: string

function shell(dir: string, name: string) {
  const file = path.join(dir, name)
  writeFileSync(file, "#!/bin/sh\n")
  chmodSync(file, 0o755)
  return file
}

function withPlatform<T>(platform: NodeJS.Platform, run: () => T): T {
  const real = process.platform
  Object.defineProperty(process, "platform", { value: platform })
  try {
    return run()
  } finally {
    Object.defineProperty(process, "platform", { value: real })
  }
}

beforeEach(() => {
  bin = mkdtempSync(path.join(tmpdir(), "select-bin-"))
  other = mkdtempSync(path.join(tmpdir(), "select-other-"))
  process.env.PATH = bin
  delete process.env.SHELL
  delete process.env.COMSPEC
  etcShells = undefined
  ShellSelect.resolve.reset()
})

afterEach(() => {
  process.env.PATH = saved.PATH
  if (saved.SHELL === undefined) delete process.env.SHELL
  else process.env.SHELL = saved.SHELL
  if (saved.COMSPEC !== undefined) process.env.COMSPEC = saved.COMSPEC
  rmSync(bin, { recursive: true, force: true })
  rmSync(other, { recursive: true, force: true })
})

describe("what a shell is, by its name", () => {
  test("the name is the file's base, lower case; on Windows without the extension, reading backslashes", () => {
    expect(ShellSelect.name("/usr/bin/BASH")).toBe("bash")
    expect(withPlatform("win32", () => ShellSelect.name("C:\\Program Files\\PowerShell\\PWSH.EXE"))).toBe("pwsh")
  })

  test("login shells are the POSIX ones and fish; nu, PowerShell and an unknown shell are not", () => {
    for (const name of ["bash", "dash", "fish", "ksh", "sh", "zsh"])
      expect(ShellSelect.login(`/bin/${name}`)).toBe(true)
    for (const name of ["nu", "pwsh", "elvish"]) expect(ShellSelect.login(`/bin/${name}`)).toBe(false)
  })

  test("only pwsh and powershell are PowerShell", () => {
    expect(ShellSelect.ps("/bin/pwsh")).toBe(true)
    expect(ShellSelect.ps("/bin/powershell")).toBe(true)
    expect(ShellSelect.ps("/bin/bash")).toBe(false)
  })

  test("the arguments that run a command follow the kind of shell", () => {
    expect(ShellSelect.args("/bin/bash", "ls")).toEqual(["-c", "ls"])
    expect(ShellSelect.args("/bin/cmd", "ls")).toEqual(["/c", "ls"])
    expect(ShellSelect.args("/bin/pwsh", "ls")).toEqual(["-NoLogo", "-NoProfile", "-NonInteractive", "-Command", "ls"])
  })
})

describe("gitbash", () => {
  test("is never set off Windows, even when configured; on Windows the configured path wins without a search", () => {
    expect(ShellSelect.gitbash({ gitbash: "/x/bash.exe" })).toBeUndefined()
    expect(withPlatform("win32", () => ShellSelect.gitbash({ gitbash: "C:\\x\\bash.exe" }))).toBe("C:\\x\\bash.exe")
  })

  test("on Windows, it is bin/bash.exe two up from git, if there is a git and that file has content", () => {
    expect(withPlatform("win32", () => ShellSelect.gitbash())).toBeUndefined()
    const cmd = path.join(other, "cmd")
    const binDir = path.join(other, "bin")
    mkdirSync(cmd)
    mkdirSync(binDir)
    shell(cmd, "git")
    process.env.PATH = cmd
    const bash = path.join(binDir, "bash.exe")
    writeFileSync(bash, "")
    expect(withPlatform("win32", () => ShellSelect.gitbash())).toBeUndefined()
    writeFileSync(bash, "x")
    expect(withPlatform("win32", () => ShellSelect.gitbash())).toBe(bash)
  })
})

describe("environment", () => {
  test("is $SHELL if it can be run, bash or /bin/sh if not, and the compatible filter refuses only fish and nu", () => {
    process.env.SHELL = shell(other, "zsh")
    expect(ShellSelect.environment()).toBe(process.env.SHELL)
    const zsh = shell(bin, "zsh")
    process.env.SHELL = "zsh"
    expect(ShellSelect.environment()).toBe(zsh)
    // Gone, or a directory: bash, from the path before the extra bin, or /bin/sh.
    rmSync(zsh)
    process.env.SHELL = path.join(other, "gone")
    expect(ShellSelect.environment()).toBe("/bin/sh")
    const bash = shell(other, "bash")
    expect(ShellSelect.environment(other)).toBe(bash)
    const first = shell(bin, "bash")
    expect(ShellSelect.environment(other)).toBe(first)
    process.env.SHELL = other
    expect(ShellSelect.environment()).toBe(first)
    rmSync(first)
    rmSync(bash)
    const onPath = shell(bin, "bash")
    for (const name of ["fish", "nu"]) {
      process.env.SHELL = shell(other, name)
      expect(ShellSelect.environment(undefined, { compatible: true })).toBe(onPath)
      expect(ShellSelect.environment()).toBe(process.env.SHELL)
    }
    process.env.SHELL = shell(other, "zsh")
    expect(ShellSelect.environment(undefined, { compatible: true })).toBe(process.env.SHELL)
  })

  test("on macOS the fallback is /bin/zsh, even with bash on the path", () => {
    shell(bin, "bash")
    expect(withPlatform("darwin", () => ShellSelect.environment())).toBe("/bin/zsh")
  })
})

describe("the Windows default", () => {
  test("is pwsh, then powershell, then git bash, then $COMSPEC, then cmd.exe", () => {
    const environment = () => withPlatform("win32", () => ShellSelect.resolve({ priority: "config" }))
    expect(environment()).toBe("cmd.exe")
    ShellSelect.resolve.reset()
    process.env.COMSPEC = "C:\\cmd2.exe"
    expect(environment()).toBe("C:\\cmd2.exe")
    ShellSelect.resolve.reset()
    const powershell = shell(bin, "powershell")
    expect(environment()).toBe(powershell)
    ShellSelect.resolve.reset()
    const pwsh = shell(bin, "pwsh")
    expect(environment()).toBe(pwsh)
  })

  test("list holds those it can run, once each", async () => {
    const pwsh = shell(bin, "pwsh")
    const items = await withPlatform("win32", () => ShellSelect.list())
    expect(items.map((item) => item.path)).toEqual([pwsh])
  })
})

// `/tmp/…` is rooted here as on POSIX; a drive path is not, so it is looked up, as a bare name is.
describe("a configured shell on Windows", () => {
  let pwsh: string
  let gitbash: string
  const resolve = (config: string, withGit = false) =>
    withPlatform("win32", () => ShellSelect.resolve({ priority: "config" }, config, withGit ? { gitbash } : undefined))

  beforeEach(() => {
    pwsh = shell(bin, "pwsh")
    gitbash = shell(other, "bash.exe")
  })

  test("a rooted shell is itself, or the default if gone; a rooted bash is git bash, in any case, if there is one", () => {
    const zsh = shell(other, "zsh")
    expect(resolve(zsh)).toBe(zsh)
    expect(resolve(zsh, true)).toBe(zsh)
    expect(resolve(path.join(other, "gone"))).toBe(pwsh)
    const bash = shell(other, "bash")
    expect(resolve(bash)).toBe(bash)
    expect(resolve("/usr/bin/bash", true)).toBe(gitbash)
    expect(resolve("/usr/bin/BASH.EXE", true)).toBe(gitbash)
    // On a drive it is not, an MSYS /x/ being drive X.
    expect(resolve("C:/x/bash", true)).toBe(pwsh)
    expect(resolve("/x/bash", true)).toBe(pwsh)
  })

  test("a bare bash is git bash, then the path's, and a bare other shell the path's", () => {
    expect(resolve("bash", true)).toBe(gitbash)
    expect(resolve("BASH.EXE", true)).toBe(gitbash)
    expect(resolve("bash")).toBe(pwsh)
    expect(resolve("zsh")).toBe(pwsh)
    const bash = shell(bin, "bash")
    const zsh = shell(bin, "zsh")
    expect(resolve("bash")).toBe(bash)
    expect(resolve("zsh")).toBe(zsh)
  })
})

describe("resolve", () => {
  test("each priority keeps its own default, a later $SHELL not read until reset clears them", () => {
    const bash = shell(bin, "bash")
    process.env.SHELL = shell(other, "fish")
    const fish = process.env.SHELL
    expect(ShellSelect.resolve({ priority: "config" })).toBe(fish)
    expect(ShellSelect.resolve({ priority: "compat" })).toBe(bash)
    process.env.SHELL = shell(other, "zsh")
    expect(ShellSelect.resolve({ priority: "config" })).toBe(fish)
    expect(ShellSelect.resolve({ priority: "compat" })).toBe(bash)
    ShellSelect.resolve.reset()
    expect(ShellSelect.resolve({ priority: "compat" })).toBe(process.env.SHELL)
    expect(ShellSelect.resolve({ priority: "config" })).toBe(process.env.SHELL)
    // One kept for a bin directory is not used for another.
    ShellSelect.resolve.reset()
    delete process.env.SHELL
    rmSync(bash)
    const otherBash = shell(other, "bash")
    process.env.PATH = ""
    expect(ShellSelect.resolve({ priority: "config" }, undefined, undefined, bin)).toBe("/bin/sh")
    expect(ShellSelect.resolve({ priority: "config" }, undefined, undefined, other)).toBe(otherBash)
    expect(ShellSelect.resolve({ priority: "compat" }, undefined, undefined, bin)).toBe("/bin/sh")
    expect(ShellSelect.resolve({ priority: "compat" }, undefined, undefined, other)).toBe(otherBash)
  })

  test("a configured shell is used as given, or refused by compat when fish; a configured git bash passes the kept default", () => {
    const fish = shell(other, "fish")
    const bash = shell(bin, "bash")
    expect(ShellSelect.resolve({ priority: "config" }, fish)).toBe(fish)
    expect(ShellSelect.resolve({ priority: "compat" }, fish)).toBe(bash)
    process.env.SHELL = shell(other, "zsh")
    const first = process.env.SHELL
    expect(ShellSelect.resolve({ priority: "config" })).toBe(first)
    process.env.SHELL = shell(other, "ksh")
    expect(ShellSelect.resolve({ priority: "config" }, undefined, { gitbash: "/x" })).toBe(process.env.SHELL)
  })
})

describe("list", () => {
  test("reads /etc/shells, skipping blanks and comments, once each, keeping those that run", async () => {
    const a = shell(other, "zsh")
    const b = shell(other, "fish")
    etcShells = `# a comment\n\n   \n${a}\n${a}\n${b}\n${path.join(other, "gone")}\n`
    expect(await ShellSelect.list()).toEqual([
      { path: a, name: a, acceptable: true },
      { path: b, name: b, acceptable: false },
    ])
  })

  test("a shell also on the path is named by its short name", async () => {
    const a = shell(other, "zsh")
    shell(bin, "zsh")
    etcShells = a
    expect(await ShellSelect.list()).toEqual([{ path: a, name: "zsh", acceptable: true }])
  })

  test("off Windows, a bare line stays as it is written", async () => {
    shell(bin, "zsh")
    etcShells = "zsh"
    expect(await ShellSelect.list()).toEqual([{ path: "zsh", name: "zsh", acceptable: true }])
  })

  test("with no /etc/shells to read, it tries the usual three", async () => {
    etcShells = ""
    const items = await ShellSelect.list()
    expect(items.every((item) => ["/bin/bash", "/bin/zsh", "/bin/sh"].includes(item.path))).toBe(true)
    expect(items.map((item) => item.path)).toContain("/bin/sh")
  })
})
