# 028: The TUI's code keeps what the binary ships, and the TUI's own tests

- Status: accepted; built (see note)
- Date: 2026-10-29
- Amends: DEC-027 (the first cut, to the build's 20 packages). Keeps
  DEC-026's stance: upstream is not tracked.
- Open work: 11d in `docs/watterson/open-work.md` (trim further).

## Context
After DEC-027, `tui/opencode/` was 4,306 files, 2,627 of them TS/JS, which
is most of this repo's TS/JS and most of its ingest time (lane A TS 40 s,
lane B TypeScript 131 s cold, 2026-10-29). The user (2026-10-29): keep the
TUI and keep ingesting it, but find whether all of it is needed. "I don't
think we're gonna be pulling opencode's code anymore; the only reason we're
using it is to not have to recreate the functionality." So nothing argues
for keeping files only to ease an upstream sync.

What the binary needs was measured, not read: a copy of the build script
(`packages/cli/script/build.ts`, as `tui/build.sh` runs it) with one more
Bun plugin that records every file the bundler loads (`tui/bundle-inputs.ts`
does it again: `~/.watterson/bun/1.4.2/bun tui/bundle-inputs.ts`). On linux-x64 it loads
1,455 of the fork's files. windows-x64 loads the same 1,455; the cross
build stops later, at native packages not installed for it. 1,226 of the
2,627 TS/JS files are never loaded: opencode's own tests (757, of which 186
are the TUI's), the web UI (`packages/ui`, 214), scripts and lint (113),
and source nothing imports (142).

## Decision
The user picked the widest of three cuts (2026-10-29). A tracked file under
`tui/opencode/` stays if any of these holds:
1. the bundler loads it (any file type: code, themes, sounds, prompts);
2. it is the TUI's test suite (`packages/tui/test/`), or something those
   tests import;
3. a kept file imports it, type-only imports included (a type import is
   erased before bundling, so the bundler never sees it);
4. a package declares it as an entry point (`exports`, `imports`, `bin`):
   a `node` or `workerd` variant the bundler's `bun` condition passed over,
   and every file a wildcard export matches (`"./*": "./src/*.ts"`; the
   `*` spans `/`, so that is all of the package's `src`), except in `ui`;
5. a kept package script runs it, or a file it runs imports it: the build,
   the install's `postinstall` (`core/script/fix-node-pty.ts`), the lint
   and typecheck tools;
6. it is a manifest, config, type declaration or licence: every package's
   `package.json`, `tsconfig*.json`, `bunfig.toml`, `*.d.ts`, `LICENSE`,
   `README.md`, `AGENTS.md`; the root files; `patches/`; `.github/`.

Everything else goes, and so does every script, preload, config and lint
step that names only what went (a package script whose file is gone, a
`test` script with no tests left, `core`'s test preload, `util`'s
`typecheck:dist`, `cli`'s `build:node`, `ai`'s `tsconfig.types.json`).
**Nothing a kept config names may be missing:**
`pipeline/tests/test_watterson_tui_refs.py` walks every kept
`package.json` (its scripts' files, its exports, imports and bin), every
`bunfig.toml` preload and every `tsconfig*.json` (its parent, its inputs),
and checks that a package with a `test` script has tests. Two packages go whole, because they served only
removed tests and codegen: `http-recorder` and `httpapi-codegen`. Their
`workspace:*` dependencies in `ai`, `core` and `client` go with them.
`packages/ui` keeps only its sounds (`src/assets/audio/`, which the TUI
imports as `@opencode/ui/audio/*`), and its manifest is cut to that one
export. oxlint goes: `script/oxlint/`, `.oxlintrc.json`, its step in the
root `lint` script, and its three devDependencies.

## Consequences
- 4,306 files → 2,018; TS/JS 2,627 → 1,720; 32.8 MB → 18.0 MB of tracked
  content. What was committed stays in history.
- The binary is built from the same inputs: re-recorded on the trimmed
  tree, the bundler loads the same 1,455 repo files and the same
  `node_modules` files.
- opencode's own tests for `core`, `cli`, `server`, `client`, `codemode`,
  `schema`, `util` and the rest are gone, with their test scripts and
  `core`'s preload. Only the TUI's suite remains, and `bun turbo test` runs
  it alone. A change to one of those packages brings its own tests, and its
  test setup back from history.
- Gone with their scripts: each library package's own `build` (a publish
  build; the binary is built by `cli`'s), `client`'s and `protocol`'s
  codegen, `core`'s migrations generator, benchmarks and
  `update-models-snapshot` (the snapshot itself is loaded and kept),
  `cli`'s Node build and `dev:vite`.
- `hobbes review` would fail on the 222 modules whose only guards were those
  tests: they are accepted by name in `.hobbes/accepted-lost-guards.yaml`
  (ADR-185, Max: "register for now … add our own tests"), and our own
  tests for them are open work.
- Regenerating `client`'s API code (`httpapi-codegen`) is no longer
  possible. The generated code is kept as source.
- A file the TUI later needs back is in history (`git show <commit>^:<path>`).

### Note, 2026-10-29: the review of PR #6
The review found the first cut's rules worked file by file and nothing
checked what kept configs name: package scripts, a test preload, a
tsconfig's inputs, `cli`'s Node build and `ai`'s wildcard-exported
barrels (`@opencode/ai/providers`) all named deleted files. That is what
the reference test above now holds, and what rules 4 and 5 were widened
for. Then: those test 5 of 5; `bun turbo typecheck` 16 of 16;
`bun turbo test` 1 task (the TUI's), 1,492 pass, 2 skip, 0 fail;
`tui/build.sh` builds 2.0.29; `tui/bundle-inputs.ts` gives the same 1,455
repo files and the same `node_modules` files as before the trim;
`bun.lock` lost 59 more lines (oxlint's three packages).

### Note, 2026-10-29: built
- `bun install` pruned `bun.lock` by 302 lines (26 packages). Its 7 added
  lines are re-hoisted entries at versions already locked.
- `tui/build.sh` (frozen lockfile) builds; `opencode --version` 2.0.29.
- `bun turbo typecheck`: 16 of 16. It took three passes to get there: the
  first deletion broke 22 type-only imports and `ai`'s test-only
  `tsconfig.types.json`, so rules 3 and 4 were added and that pass dropped.
- TUI tests (`bun test --timeout 30000`, as `docs/build-and-test.md` runs
  them): 1,492 pass, 2 skip, 0 fail, 108,521 expect() calls, the same as
  before the trim. The first pass loaded 78 fewer tests (a core test helper,
  a theme JSON and a `node` variant were gone), which is where rules 2 and 4
  came from.
- This repo's ingest, cold (index cache off), one run each, before (`main`
  at `6cb09d4`) → after: 194.9 s → 157.6 s; lane A TS 40.4 → 29.6 s; lane B
  TypeScript 130.6 → 107.2 s; peak RSS 6.4 → 5.3 GB (the TS helper's).
- Every deleted path is the commit's own list
  (`git show --stat --diff-filter=D <commit>`), summarised in
  `tui/opencode/NOTICE.md`.
