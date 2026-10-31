// Points the harnesses at the real merman package for `harnesses.test.ts`; imported before them, so their
// `cli.ts` reads it (pinned.py runs them inside a mirror and leaves it unset).
process.env.PINNED_PACKAGE ??= new URL("../../tui/opencode/packages/merman", import.meta.url).pathname
export const harnessPackage = process.env.PINNED_PACKAGE
