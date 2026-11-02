import { afterEach, beforeEach, describe, expect, test } from "bun:test"
import { Effect } from "effect"
import os from "node:os"
import path from "node:path"
import { ShellParse } from "../../src/shell/parse"

const run = (command: string, shell = "/bin/bash", cwd = "/work", options?: { portable?: boolean }) =>
  Effect.runPromise(ShellParse.scan(command, shell, cwd, options))
const saves = async (command: string, options?: { portable?: boolean }, shell?: string) =>
  (await run(command, shell, "/work", options)).commands.map((item) => item.save)

// The tree-sitter walk and the portable scanner are two routes to one answer. `bench/subsume` reads one route's copy
// of a case as redundant, as it plants faults only in parse.ts. Kept: a fault planted by hand in scan.ts (a substitution's
// commands dropped, a raw word cooked, PowerShell's input lower-cased) fails the scanner's copy and not the walk's.
describe.each([
  ["the tree-sitter walk", undefined],
  ["the portable scanner", { portable: true }],
])("%s", (_, options) => {
  test("the prefix is as long as the longest known command's arity, or what the command has", async () => {
    expect(await saves("ls -la /tmp", options)).toEqual(["ls *"])
    expect(await saves("git commit -m x", options)).toEqual(["git commit *"])
    expect(await saves("git config user.name x", options)).toEqual(["git config user.name *"])
    expect(await saves("npm run build --x", options)).toEqual(["npm run build *"])
    expect(await saves("aws s3 cp a b", options)).toEqual(["aws s3 cp *"])
    expect(await saves("git", options)).toEqual(["git *"])
    expect(await saves("aws s3", options)).toEqual(["aws s3 *"])
    expect(await saves('git a"b" c', options)).toEqual(['git a"b" *'])
    expect(await saves("git   status x", options)).toEqual(["git status *"])
  })

  test("each command is its own entry, its text the resource, a redirection in that and not in the save", async () => {
    expect(await run("foo bar", "/bin/bash", "/work", options)).toEqual({
      commands: [{ resource: "foo bar", save: "foo *" }],
      directories: [],
    })
    expect((await run("foo bar; baz 2>e x", "/bin/bash", "/work", options)).commands).toEqual([
      { resource: "foo bar", save: "foo *" },
      { resource: "baz 2>e x", save: "baz *" },
    ])
    expect((await run("echo hi > out  ", "/bin/bash", "/work", options)).commands).toEqual([
      { resource: "echo hi > out", save: "echo *" },
    ])
    expect(await saves("git > out status x", options)).toEqual(["git *"])
    expect(await saves("git status && ls | foo x; bar", options)).toEqual(["git status *", "ls *", "foo *", "bar *"])
  })

  test("a substitution's command is seen too, even in a declaration, which is no command itself", async () => {
    expect((await saves("echo $(foo x)", options)).sort()).toEqual(["echo *", "foo *"])
    expect((await run("export A=1", "/bin/bash", "/work", options)).commands).toEqual([])
    expect(await saves("export A=$(foo x)", options)).toEqual(["foo *"])
  })

  test("a directory change is a directory, not a command, its flags dropped and its quotes removed", async () => {
    expect(await run("cd /tmp", "/bin/bash", "/work", options)).toEqual({ commands: [], directories: ["/tmp"] })
    expect((await run("pushd /a && popd /b", "/bin/bash", "/work", options)).directories).toEqual(["/a", "/b"])
    expect((await run("chdir /c", "/bin/bash", "/work", options)).directories).toEqual(["/c"])
    expect((await run('cd -P "/my dir"', "/bin/bash", "/work", options)).directories).toEqual(["/my dir"])
    expect((await run("cd '/my dir'", "/bin/bash", "/work", options)).directories).toEqual(["/my dir"])
  })

  test("the home directory expands; an unknown expression is not guessed", async () => {
    expect((await run("cd ~", "/bin/bash", "/work", options)).directories).toEqual([os.homedir()])
    expect((await run("cd ~/x", "/bin/bash", "/work", options)).directories).toEqual([path.join(os.homedir(), "x")])
    expect((await run("cd $FOO", "/bin/bash", "/work", options)).directories).toEqual([])
    expect((await run('cd "$HOME"', "/bin/bash", "/work", options)).directories).toEqual([])
    expect((await run("cd `pwd`/x", "/bin/bash", "/work", options)).directories).toEqual([])
  })
})

describe("PowerShell", () => {
  const pwsh = "/opt/ps/pwsh"
  const saved = process.env.PS_TEST_DIR
  beforeEach(() => {
    process.env.PS_TEST_DIR = "/from/env"
  })
  afterEach(() => {
    if (saved === undefined) delete process.env.PS_TEST_DIR
    else process.env.PS_TEST_DIR = saved
  })

  describe.each([
    ["the tree-sitter walk", undefined],
    ["the portable scanner", { portable: true }],
  ])("%s", (_, options) => {
    const directories = async (command: string) => (await run(command, pwsh, "/work", options)).directories

    test("the location commands match in any case; a path flag, in any abbreviation, names the next word", async () => {
      expect(await directories("Set-Location /a")).toEqual(["/a"])
      expect(await directories("PUSH-LOCATION /b")).toEqual(["/b"])
      expect(await directories("Set-Location -Path /a")).toEqual(["/a"])
      expect(await directories("Set-Location -LiteralPath /b")).toEqual(["/b"])
      expect(await directories("Set-Location -lp /c")).toEqual(["/c"])
      expect(await directories("Set-Location -PSPath /d")).toEqual(["/d"])
      for (const flag of ["-l", "-li", "-pa", "-psp", "-pspat", "-literalp", "-Pat:"])
        expect(await directories(`Set-Location ${flag} /e`)).toEqual(["/e"])
    })

    test("a path flag takes one word, whatever it looks like; later words, and another flag's, are directories too", async () => {
      expect(await directories("Set-Location -PassThru /a")).toEqual(["/a"])
      expect(await directories("Set-Location -Path /a /b")).toEqual(["/a", "/b"])
      expect(await directories("Set-Location -Path /a -x")).toEqual(["/a"])
      expect(await directories("Set-Location -Path: -x")).toEqual(["-x"])
      expect(await directories("Set-Location -Path $Other /b")).toEqual(["/b"])
    })

    test("a flag's value after a colon is read, a word with a dash inside is no flag, and quotes are removed", async () => {
      expect(await directories("Set-Location -Path:a")).toEqual(["a"])
      expect(await directories("Set-Location x-Path")).toEqual(["x-Path"])
      expect(await directories("Set-Location -Path:/a")).toEqual(["/a"])
      expect(await directories("Set-Location -PassThru:/b")).toEqual(["/b"])
      expect(await directories('Set-Location "c d"')).toEqual(["c d"])
      expect(await directories("Set-Location 'e f'")).toEqual(["e f"])
    })

    test("a block's commands are seen, a bare foreach and its blocks not being one", async () => {
      const saves = async (command: string) =>
        (await run(command, pwsh, "/work", options)).commands.map((item) => item.save)
      expect(await saves("foreach {x}")).toEqual(["x *"])
      expect(await saves("ForEach-Object {x} {y}")).toEqual(["x *", "y *"])
      expect(await saves("Set-Location (x)")).toEqual(["x *"])
      expect(await directories("Set-Location (x)")).toEqual([])
    })

    test("a command's name is lower-cased only to look up its arity; PowerShell has no declarations", async () => {
      expect((await run("GIT status x", pwsh, "/work", options)).commands[0]?.save).toBe("GIT *")
      expect((await run("Get-Process -Name x", pwsh, "/work", options)).commands).toEqual([
        { resource: "Get-Process -Name x", save: "Get-Process *" },
      ])
      expect((await run("export a b", pwsh, "/work", options)).commands[0]?.save).toBe("export *")
      expect((await run("unset a b", pwsh, "/work", options)).commands[0]?.save).toBe("unset *")
    })

    test("$HOME, $PWD and $PSHOME resolve, in any case; another variable is not guessed", async () => {
      expect(await directories("Set-Location $HOME")).toEqual([os.homedir()])
      expect(await directories("Set-Location $pwd")).toEqual(["/work"])
      expect(await directories("Set-Location ${PSHOME}")).toEqual(["/opt/ps"])
      expect(await directories("Set-Location $Other")).toEqual([])
      expect(await directories("Set-Location $env:PS_TEST_DIR")).toEqual(["/from/env"])
      expect(await directories("Set-Location ${env:PS_TEST_DIR}")).toEqual(["/from/env"])
      expect(await directories("Set-Location $env:PS_TEST_UNSET")).toEqual([])
    })
  })
})

describe("PowerShell paths the grammar cannot parse", () => {
  const directories = async (command: string, portable: boolean) =>
    (await run(command, "/opt/ps/pwsh", "/work", { portable })).directories

  test("the portable scanner reads them whole", async () => {
    expect(await directories("Set-Location -- /etc", true)).toEqual(["/etc"])
    expect(await directories("Set-Location $HOME/x", true)).toEqual([`${os.homedir()}/x`])
    expect(await directories("Set-Location $pwd/x", true)).toEqual(["/work/x"])
    expect(await directories("Set-Location $env:PS_TEST_UNSET/x", true)).toEqual(["/x"])
    expect(await directories("Set-Location $Other/x", true)).toEqual([])
    expect(await directories("Set-Location ${HOME}/x", true)).toEqual([`${os.homedir()}/x`])
    expect(await directories("Set-Location -- -x", true)).toEqual(["-x"])
    expect(await directories("Set-Location -- -Path /a", true)).toEqual(["-Path", "/a"])
    expect(await directories("Set-Location a'b'", true)).toEqual(["ab"])
  })

  // A fork defect, pinned: the walk ignores the tree's parse errors, so permission analysis is given no directory for
  // the first and the parent of the real one for the second. A fix changes these.
  test("a fork defect, pinned: the tree-sitter walk loses what follows a parse error", async () => {
    expect(await directories("Set-Location -- /etc", false)).toEqual([])
    expect(await directories("Set-Location $HOME/x", false)).toEqual([os.homedir()])
    expect(await directories("Set-Location ${HOME}/x", false)).toEqual([os.homedir()])
  })
})

describe("a backslash in a directory", () => {
  const directories = async (command: string, portable: boolean) =>
    (await run(command, "/bin/bash", "/work", { portable })).directories

  test("the portable scanner decodes quotes in a word with none", async () => {
    expect(await directories("cd a'b'", true)).toEqual(["ab"])
  })

  // A fork defect, pinned: bash removes the backslash, so the real directories are "a b" and "ab". Both routes keep the
  // source's text, and permission analysis is given a directory that is not the one the command enters.
  test("a fork defect, pinned: the backslash stays in the name", async () => {
    expect(await directories("cd a\\ b", true)).toEqual(["a\\ b"])
    expect(await directories("cd a\\ b", false)).toEqual(["a\\ b"])
    expect(await directories("cd 'a'\\b", true)).toEqual(["'a'\\b"])
    expect(await directories("cd 'a'\\b", false)).toEqual(["a", "\\b"])
  })
})

// The two routes differ on these, each pinned, so a change to either is seen. The walk gives no directory where the
// scanner decodes one, and a grant the normalised spacing would not match keeps the source's spacing on the scanner only.
describe("where the two routes differ", () => {
  const both = async (command: string, shell: string) => {
    const [walk, portable] = await Promise.all([
      run(command, shell, "/work", { portable: false }),
      run(command, shell, "/work", { portable: true }),
    ])
    return { walk, portable }
  }

  test("an ANSI-quoted directory, and an escaped dollar in a PowerShell one", async () => {
    const { walk: ansiWalk, portable: ansi } = await both("cd $'/x y'", "/bin/bash")
    expect(ansiWalk.directories).toEqual([])
    expect(ansi.directories).toEqual(["/x y"])
    for (const command of ["Set-Location a`$b", 'Set-Location "a`$b"']) {
      const { walk, portable } = await both(command, "/opt/ps/pwsh")
      expect(walk.directories).toEqual([])
      expect(portable.directories).toEqual(["a$b"])
    }
  })

  test("a PowerShell foreach not followed by blocks alone", async () => {
    for (const command of ["foreach x", "foreach"]) {
      const { walk, portable } = await both(command, "/opt/ps/pwsh")
      expect(walk.commands).toEqual([])
      expect(portable.commands).toEqual([{ resource: command, save: "foreach *" }])
    }
  })

  test("a PowerShell redirection is left out of the walk's save, and kept in the scanner's", async () => {
    const { walk, portable } = await both("git > out status x", "/opt/ps/pwsh")
    expect(walk.commands[0]?.save).toBe("git status *")
    expect(portable.commands[0]?.save).toBe("git > out status *")
  })

  test("a PowerShell call operator is in the scanner's save, not the walk's", async () => {
    const { walk, portable } = await both("& foo bar", "/opt/ps/pwsh")
    expect(walk.commands[0]?.save).toBe("foo *")
    expect(portable.commands[0]?.save).toBe("& foo *")
  })

  test("spacing a PowerShell save would lose", async () => {
    const wide = await both("git   status x", "/opt/ps/pwsh")
    expect(wide.walk.commands[0]?.save).toBe("git status *")
    expect(wide.portable.commands[0]?.save).toBe("git   status *")
    const continued = await both("git `\n status x", "/opt/ps/pwsh")
    expect(continued.walk.commands[0]?.save).toBe("git status *")
    expect(continued.portable.commands[0]?.save).toBe("git `\n status *")
    expect((await both("git status   x", "/opt/ps/pwsh")).portable.commands[0]?.save).toBe("git status *")
    expect((await both("git   status   x", "/opt/ps/pwsh")).portable.commands[0]?.save).toBe("git   status   *")
    expect((await both("git   status `\n x", "/opt/ps/pwsh")).portable.commands[0]?.save).toBe("git   status `\n *")
    expect((await both("git   status>out x", "/opt/ps/pwsh")).portable.commands[0]?.save).toBe("git   status>out *")
  })
})

describe("the arity table", () => {
  const save = async (command: string) => (await saves(command, { portable: true }))[0]

  test("these keep the name alone", async () => {
    const names =
      "cat chmod chown cp echo env grep kill killall ln ls mkdir mv ps pwd rm rmdir sleep source tail touch which"
    for (const name of names.split(" ")) expect(await save(`${name} a b`)).toBe(`${name} *`)
  })

  test("these keep one word more", async () => {
    const names =
      "bazel brew bun cargo cdk cf cmake composer consul crictl deno docker eksctl firebase flyctl git go gradle helm heroku hugo ip kind kubectl kustomize make mc minikube mongosh mysql mvn ng npm npx nvm nx openssl pip pipenv pnpm poetry podman psql pulumi python pyenv rake rbenv redis-cli rustup serverless skaffold sls sst swift systemctl terraform tmux turbo ufw vault vercel volta wp yarn"
    for (const name of names.split(" ")) expect(await save(`${name} a b`)).toBe(`${name} a *`)
  })

  test("these keep two words more", async () => {
    for (const name of "aws az doctl gcloud gh sfdx".split(" "))
      expect(await save(`${name} a b c`)).toBe(`${name} a b *`)
  })

  test("these subcommands keep one word past themselves", async () => {
    const names = [
      "bun run",
      "bun x",
      "cargo add",
      "cargo run",
      "consul kv",
      "deno task",
      "docker builder",
      "docker compose",
      "docker container",
      "docker image",
      "docker network",
      "docker volume",
      "eksctl create",
      "git config",
      "git remote",
      "git stash",
      "ip addr",
      "ip link",
      "ip netns",
      "ip route",
      "kind create",
      "kubectl kustomize",
      "kubectl rollout",
      "consul kv",
      "mc admin",
      "npm exec",
      "npm init",
      "npm run",
      "npm view",
      "openssl req",
      "openssl x509",
      "pnpm dlx",
      "pnpm exec",
      "pnpm run",
      "podman container",
      "podman image",
      "pulumi stack",
      "terraform workspace",
      "vault auth",
      "vault kv",
      "yarn dlx",
      "yarn run",
    ]
    for (const name of names) expect(await save(`${name} a b`)).toBe(`${name} a *`)
  })
})

describe("the dialect a shell's name picks", () => {
  const scanned = async (command: string, shell: string) =>
    Effect.runPromise(ShellParse.scanPortable(command, shell, "/work")).then(
      () => true,
      () => false,
    )

  // Zsh's parameter flag evaluates; bash reads it as a word. Dash has no arrays, so a subscript's expansion splits.
  test("bash's, zsh's, and for any other name POSIX's", async () => {
    expect(await scanned("echo ${(e)x}", "/bin/bash")).toBe(true)
    expect(await scanned("echo ${(e)x}", "/bin/zsh")).toBe(false)
    expect(await scanned("a[$b]=1", "/bin/zsh")).toBe(true)
    expect(await scanned("a[$b]=1", "/bin/dash")).toBe(false)
  })
})

describe("on Windows", () => {
  const onWindows = async <T>(run: () => Promise<T>) => {
    const real = process.platform
    Object.defineProperty(process, "platform", { value: "win32" })
    try {
      return await run()
    } finally {
      Object.defineProperty(process, "platform", { value: real })
    }
  }

  test("~\\ is the home directory too", async () => {
    const result = await onWindows(() => run("Set-Location ~\\x", "/opt/ps/pwsh", "/work", { portable: true }))
    expect(result.directories).toEqual([path.join(os.homedir(), "x")])
  })

  test("an environment variable's name is matched in any case", async () => {
    process.env.PS_TEST_CASE = "/cased"
    try {
      const result = await onWindows(() =>
        run("Set-Location $env:Ps_Test_Case", "/opt/ps/pwsh", "/work", { portable: true }),
      )
      expect(result.directories).toEqual(["/cased"])
    } finally {
      delete process.env.PS_TEST_CASE
    }
  })

  test("off Windows, ~\\ is an ordinary name and the variable's case matters", async () => {
    process.env.PS_TEST_CASE = "/cased"
    try {
      const options = { portable: true }
      expect((await run("Set-Location ~\\x", "/opt/ps/pwsh", "/work", options)).directories).toEqual(["~\\x"])
      expect((await run("Set-Location $env:ps_test_case", "/opt/ps/pwsh", "/work", options)).directories).toEqual([])
    } finally {
      delete process.env.PS_TEST_CASE
    }
  })
})

describe("scan's routes", () => {
  test("a command the portable scanner cannot read fails, naming why", async () => {
    const failure = await Effect.runPromise(Effect.flip(ShellParse.scanPortable("echo <<EOF", "/bin/bash", "/work")))
    expect(String(failure)).toContain("Portable shell scanner cannot analyze command")
  })

  test("with no bash parser built, scan takes the portable route", async () => {
    const result = await Effect.runPromise(
      ShellParse.scan("cd $'/x'", "/bin/bash", "/work", { wasm: { runtime: "", bash: "", powershell: "" } }),
    )
    expect(result.directories).toEqual(["/x"])
  })
})
