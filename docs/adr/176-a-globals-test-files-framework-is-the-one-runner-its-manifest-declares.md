# ADR-176 — A globals-style test file's framework is the one runner its manifest declares

**Date:** 2026-10-03 · **Status:** accepted (Max, 2026-10-03: "strict manifest rule", then, on the
measurement, "label, harness ignores it") and built (0.2.110-beta).

The extraction order's item 9 (`currently-open.md`), C-13: a TS/JS test file that calls `describe`/`it`/`test`
without importing a framework reports `framework: "unknown"`. The note said "jest globals". Measured, it is
wider (BUILDLOG, 2026-10-03, forty-first session): the `unknown` files are mocha's (ajv 68, hack-chat 36),
jest's (npq 47, xmpp.js 15) and vitest's with `globals: true` (hono 110, preact 40). hono also has a
`bun:test` file, which a looser rule would mislabel.

## What the field drives

`tests.json`'s `framework`, and through it the derive harness (`derive/harness.py`, `commands`): a `vitest` or
`node:test` row is run by that runner from the nearest `package.json`; every other value is grouped with no
root and not run. A `vitest` label from this rule would therefore have made the harness run the file with
vitest. That is why the vitest arm needs the config's `globals: true`, and why decision 4 keeps a declared
label out of the harness.

## Decision

For a test file the helper reports as `unknown` (test-named, calling the globals, importing none of
`vitest`, `@jest/globals`, `node:test`), the ingest names the framework only when all of these hold:
1. **The file imports no other test runner.** No static import, `require` or dynamic import of `bun:test`,
   `@playwright/test`, `mocha`, `jasmine`, `ava`, `tap`, `uvu`, `@japa/runner` or a Deno `@std/testing`
   module, and no specifier ending in `:test` or `/test`. Otherwise the file stays `unknown`.
2. **Exactly one runner is declared.** Walking up from the file's directory to the repo root, the first
   `package.json` whose `dependencies` or `devDependencies` name any of `jest`, `vitest`, `mocha` or
   `jasmine` must name exactly one of them. None, or two or more, leaves `unknown`.
3. **vitest only with its globals on.** If that one runner is `vitest`, a `vitest.config.*` or `vite.config.*`
   beside that `package.json` must set `globals: true` (read as text). Otherwise `unknown`.

The test row carries `framework_from`, the manifest's repo-relative path, so a reader can tell the declared
runner from an imported one. The rule never infers jest-versus-vitest from the calls themselves.

4. **The harness runs only an imported runner** (Max's route on the measurement below). A row with
   `framework_from` is grouped as `<runner> (declared)` with no command, and its tests read `unsupported`,
   the same as any framework the harness has no runner for. Nothing the harness runs changes.

## Not decided here

- Express's mocha suite (`test/*.js`) is not inventoried at all, because the files are not test-named. That is
  a separate limit, registered as **C-194** and surfaced by one `js-tests` degradation record per ingest
  naming each `package.json` that declares a runner while no file under it is test-named.
- The rule does not read a runner's include or exclude globs or its workspace projects. A file the declared
  runner's config excludes would still be labelled. That residue is registered on C-13.

## Measurement (`~/.hobbes/bench/c13-globals-2026-10-03/`: `sim.py`, `RESULTS.md`, `real.sh`)

The rule as worded, simulated over each cell's existing `unknown` files, then checked file by file against
the globs of the runner each repo's own test script runs:

| cell | unknown | named | runner | run by its config | not |
|---|---|---|---|---|---|
| hack-chat | 36 | 36 | mocha | 36 | 0 |
| ajv | 68 | 68 | mocha | 68 | 0 |
| npq | 47 | 47 | jest | 47 | 0 |
| xmpp.js | 15 | 10 | jest | 6 | 4 (no jest config matches) |
| preact | 40 | 40 | vitest | 37 | 3 (`test/ts/*.test.tsx`, tsc type tests) |
| hono | 110 | 109 | vitest | 108 | 1 (`common.case.test.tsx`, excluded) |

Refused: hono's `bun:test` file, and 5 xmpp.js files importing its `@xmpp/test` helper (a `/test` specifier).
The 4 vitest files outside vitest's globs would have read "no test files" had the harness run them, so Max
chose decision 4. **Built and run on the real cells** (local clones at each cell's HEAD, lane A, `real.sh`):
every file's built framework equals the simulation's (326 of 326). Express's ingest writes the `js-tests`
record for its root `package.json` (mocha). The rule writes only `tests.json`'s `framework` and
`framework_from` and that one record; it draws no edge.
