/**
 * The behavioral index (architecture §4.2): the joins that turn
 * tests.json plus the narrative test docs into the four questions the
 * raw suite cannot answer.
 *
 * Pure, and tested as such — the tab renders what these return.
 */

import type { Behavior, Graph, GraphNode, TestCase } from '../types'

/** One test with the behavior it guards, when narration has run. */
export interface GuardingTest {
  test: TestCase
  behavior?: Behavior
}

/** One module and the tests that statically reach it (§4.2 q2). */
export interface ModuleCoverage {
  module: GraphNode
  tests: GuardingTest[]
}

export interface TestIndex {
  /** Modules with at least one guarding test, most-guarded first. */
  covered: ModuleCoverage[]
  /** Modules no test reaches — the coverage gap that matters (§4.2 q3). */
  unguarded: GraphNode[]
  /** Tests that reach no module at all: they guard nothing we can see. */
  orphans: GuardingTest[]
  /** How many tests carry a narrative one-liner (§4.2 q1). */
  described: number
  total: number
}

/**
 * `module` and `package` nodes are the repo's own code — the only nodes
 * a test can meaningfully guard. External, env, and infra nodes are not
 * coverage gaps, so listing them as unguarded would be noise.
 */
const OWN_CODE = new Set(['module', 'package'])

export function buildTestIndex(
  graph: Graph,
  tests: TestCase[],
  behaviors: Behavior[],
): TestIndex {
  const byTestID = new Map(behaviors.map((b) => [b.test, b]))
  const guarding = new Map<string, GuardingTest[]>()
  const orphans: GuardingTest[] = []
  let described = 0

  for (const test of tests) {
    const entry: GuardingTest = { test, behavior: byTestID.get(test.id) }
    if (entry.behavior) described++
    const modules = test.reaches_modules ?? []
    if (modules.length === 0) {
      orphans.push(entry)
      continue
    }
    for (const id of modules) {
      if (!guarding.has(id)) guarding.set(id, [])
      guarding.get(id)!.push(entry)
    }
  }

  const own = graph.nodes.filter((n) => OWN_CODE.has(n.kind))
  const covered: ModuleCoverage[] = []
  const unguarded: GraphNode[] = []
  for (const module of own) {
    const hits = guarding.get(module.id)
    if (hits && hits.length > 0) {
      covered.push({ module, tests: hits.slice().sort((a, b) => cmp(a.test.id, b.test.id)) })
    } else {
      unguarded.push(module)
    }
  }
  covered.sort((a, b) => b.tests.length - a.tests.length || cmp(a.module.id, b.module.id))
  unguarded.sort((a, b) => cmp(a.id, b.id))
  orphans.sort((a, b) => cmp(a.test.id, b.test.id))

  return { covered, unguarded, orphans, described, total: tests.length }
}

function cmp(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0
}

/**
 * testFileOf is the display name for a test: pytest ids are
 * `path::Class::case` and JS ids are `path::describe > case`, so the
 * path is everything before the first separator.
 */
export function testFileOf(test: TestCase): string {
  return test.file || test.id.split('::')[0]
}

/** caseOf is the test's name without its file — what reads in a list. */
export function caseOf(test: TestCase): string {
  const cut = test.id.indexOf('::')
  return cut < 0 ? test.id : test.id.slice(cut + 2)
}

/** Tests grouped by file, for the per-file view. */
export interface TestFile {
  file: string
  framework: string
  tests: GuardingTest[]
}

export function groupByFile(tests: TestCase[], behaviors: Behavior[]): TestFile[] {
  const byTestID = new Map(behaviors.map((b) => [b.test, b]))
  const files = new Map<string, TestFile>()
  for (const test of tests) {
    const file = testFileOf(test)
    if (!files.has(file)) {
      // Framework is per-test since schema v3 (a repo can mix pytest and
      // vitest); the file's label is whatever its tests agree on.
      files.set(file, { file, framework: test.framework ?? 'unknown', tests: [] })
    }
    files.get(file)!.tests.push({ test, behavior: byTestID.get(test.id) })
  }
  return [...files.values()].sort((a, b) => cmp(a.file, b.file))
}
