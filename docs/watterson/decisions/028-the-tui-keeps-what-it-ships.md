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
Bun plugin that records every file the bundler loads. On linux-x64 it loads
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
   a `node` or `workerd` variant the bundler's `bun` condition passed over;
5. the build or install runs it: the root `script/`, `packages/script/`,
   `packages/cli/script/`, and `packages/core/script/fix-node-pty.ts`
   (the root `postinstall`);
6. it is a manifest, config, type declaration or licence: every package's
   `package.json`, `tsconfig*.json`, `bunfig.toml`, `*.d.ts`, `LICENSE`,
   `README.md`, `AGENTS.md`; the root files; `patches/`; `.github/`.

Everything else goes. Two packages go whole, because they served only
removed tests and codegen: `http-recorder` and `httpapi-codegen`. Their
`workspace:*` dependencies in `ai`, `core` and `client` go with them.
`packages/ui` keeps only its sounds (`src/assets/audio/`, which the TUI
imports as `@opencode/ui/audio/*`), and its manifest is cut to that one
export. The lint plugin `script/oxlint/` and `.oxlintrc.json` go.

## Consequences
- 4,306 files → 1,987; TS/JS 2,627 → 1,686; 32.8 MB → 17.9 MB of tracked
  content. What was committed stays in history.
- The binary is built from the same inputs: re-recorded on the trimmed
  tree, the bundler loads the same 1,455 repo files and the same
  `node_modules` files.
- opencode's own tests for `core`, `cli`, `server`, `client`, `codemode`,
  `schema`, `util` and the rest are gone. Only the TUI's suite remains. A
  change to one of those packages now has no upstream tests to run against;
  it brings its own.
- Regenerating `client`'s API code (`httpapi-codegen`) is no longer
  possible. The generated code is kept as source.
- A file the TUI later needs back is in history (`git show <commit>^:<path>`).

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
