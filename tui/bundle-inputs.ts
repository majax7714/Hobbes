// The files the TUI binary is built from (DEC-028): every file Bun's bundler
// loads when `tui/build.sh` builds the binary, as repo-relative paths, one per
// line, with `node_modules` files after them.
//
//   ~/.watterson/bun/1.4.2/bun tui/bundle-inputs.ts > inputs.txt
//   ~/.watterson/bun/1.4.2/bun tui/bundle-inputs.ts --target=opencode-windows-x64 > inputs.txt
//
// It runs a copy of `packages/cli/script/build.ts` with one more bundler
// plugin, first in the list, whose onLoad records each path and returns
// nothing, so the other plugins load the file as they would. The copy sits
// beside the original (its imports are relative) and is removed afterwards.
// The build itself runs as `tui/build.sh` runs it and writes `dist/`; a
// target other than this box's stops at native packages not installed for
// it, after the bundler has loaded the repo's files.
import path from "node:path"

/** *source* (`build.ts`) with a recorder plugin first in the bundler's list,
 * writing every path it loads to *out* when the build exits; or null when the
 * script no longer has the shape this patches. */
export function patchBuild(source: string, out: string): string | null {
  const loop = "for (const item of targets) {"
  const plugins = "    plugins: [\n"
  if (!source.includes(loop) || !source.includes(plugins)) return null
  const recorder = `const hobbesInputs = new Set<string>()
const hobbesRecorder: BunPlugin = {
  name: "hobbes-bundle-inputs",
  setup(build) {
    build.onLoad({ filter: /.*/ }, (args) => void hobbesInputs.add(args.path))
  },
}
process.on("exit", () => require("fs").writeFileSync(${JSON.stringify(out)}, [...hobbesInputs].join("\\n")))
`
  return source.replace(loop, recorder + loop).replace(plugins, `${plugins}      hobbesRecorder,\n`)
}

/** *loaded* (absolute paths) relative to *repo*, the repo's own files first,
 * then `node_modules` files, each sorted, without repeats. */
export function listInputs(loaded: string[], repo: string): string[] {
  const relative = [...new Set(loaded.map((p) => path.relative(repo, p)))]
  return [
    ...relative.filter((p) => !p.includes("node_modules/")).sort(),
    ...relative.filter((p) => p.includes("node_modules/")).sort(),
  ]
}

async function main() {
  const here = import.meta.dirname
  const repo = path.dirname(here)
  const cli = path.join(here, "opencode", "packages", "cli")
  const source = await Bun.file(path.join(cli, "script", "build.ts")).text()
  const out = path.join(cli, "script", `.bundle-inputs-${process.pid}.txt`)
  const patched = patchBuild(source, out)
  if (patched === null) {
    console.error("bundle-inputs: build.ts no longer has the shape this script patches; update it")
    process.exit(1)
  }
  const copy = path.join(cli, "script", `.bundle-inputs-${process.pid}.ts`)
  await Bun.write(copy, patched)
  const env = Object.fromEntries(
    (await Bun.file(path.join(here, "build.env")).text())
      .split("\n")
      .filter((line) => /^\w+=/.test(line))
      .map((line) => line.split("=", 2)),
  )
  const target = process.argv.find((arg) => arg.startsWith("--target="))
  const proc = Bun.spawnSync(
    ["bun", "run", copy, ...(target ? [target] : ["--single"]), "--skip-web-ui", "--skip-install"],
    {
      cwd: cli,
      env: { ...process.env, OPENCODE_CHANNEL: "watterson", OPENCODE_VERSION: env.version },
      stdout: "ignore",
      stderr: "pipe",
    },
  )
  await Bun.file(copy).delete()
  const file = Bun.file(out)
  if (!(await file.exists())) {
    console.error(`bundle-inputs: the build recorded nothing (exit ${proc.exitCode}):\n${proc.stderr.toString().slice(-2000)}`)
    process.exit(1)
  }
  const loaded = (await file.text()).split("\n").filter(Boolean)
  await file.delete()
  console.log(listInputs(loaded, repo).join("\n"))
  if (proc.exitCode !== 0) {
    console.error(`bundle-inputs: the build stopped (exit ${proc.exitCode}) after the bundler loaded ${loaded.length} files`)
  }
}

if (import.meta.main) await main()
