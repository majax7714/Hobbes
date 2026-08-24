import { describe, expect, it } from 'vitest'

import { buildTestIndex, caseOf, groupByFile, testFileOf } from './testIndex'
import type { Behavior, Graph, TestCase } from '../types'

const graph: Graph = {
  schema_version: 3,
  sha: 'abc',
  dirty: false,
  languages: ['python'],
  nodes: [
    { id: 'app.core', kind: 'module', path: 'src/app/core.py' },
    { id: 'app.api', kind: 'module', path: 'src/app/api.py' },
    { id: 'app', kind: 'package', path: 'src/app/__init__.py' },
    { id: 'ext:requests', kind: 'external' },
    { id: 'env:MODE', kind: 'env' },
  ],
  module_edges: [],
  symbols: [],
  symbol_edges: [],
}

const tests: TestCase[] = [
  {
    id: 'tests/test_core.py::test_run',
    file: 'tests/test_core.py',
    line: 4,
    framework: 'pytest',
    reaches: ['app.core.run'],
    reaches_modules: ['app.core'],
  },
  {
    id: 'tests/test_core.py::test_run_twice',
    file: 'tests/test_core.py',
    line: 9,
    framework: 'pytest',
    reaches: ['app.core.run'],
    reaches_modules: ['app.core', 'app'],
  },
  {
    id: 'src/flow.test.ts::flow > routes',
    file: 'src/flow.test.ts',
    line: 3,
    framework: 'vitest',
    reaches: [],
    reaches_modules: [],
  },
]

const behaviors: Behavior[] = [
  {
    test: 'tests/test_core.py::test_run',
    text: 'running twice is idempotent',
    pins: [{ path: 'tests/test_core.py', line: 5 }],
    doc_id: 'tests.test_core',
    status: 'fresh',
  },
]

describe('buildTestIndex', () => {
  const index = buildTestIndex(graph, tests, behaviors)

  it('inverts the reach map into "what guards this module"', () => {
    expect(index.covered.map((c) => c.module.id)).toEqual(['app.core', 'app'])
    expect(index.covered[0].tests.map((t) => t.test.id)).toEqual([
      'tests/test_core.py::test_run',
      'tests/test_core.py::test_run_twice',
    ])
  })

  it('ranks the most-guarded module first', () => {
    expect(index.covered[0].tests.length).toBeGreaterThanOrEqual(index.covered[1].tests.length)
  })

  it('reports unguarded own-code modules and nothing else', () => {
    // ext:/env: nodes are not coverage gaps, so they must not appear.
    expect(index.unguarded.map((n) => n.id)).toEqual(['app.api'])
  })

  it('collects tests that reach nothing as orphans', () => {
    expect(index.orphans.map((o) => o.test.id)).toEqual(['src/flow.test.ts::flow > routes'])
  })

  it('attaches the narrative one-liner where narration has run', () => {
    const [first, second] = index.covered[0].tests
    expect(first.behavior?.text).toBe('running twice is idempotent')
    expect(second.behavior).toBeUndefined()
    expect(index.described).toBe(1)
    expect(index.total).toBe(3)
  })

  it('works with no narrative pass at all', () => {
    const bare = buildTestIndex(graph, tests, [])
    expect(bare.described).toBe(0)
    expect(bare.covered.length).toBe(2)
  })
})

describe('test naming', () => {
  it('splits file and case for pytest and JS ids alike', () => {
    expect(testFileOf(tests[0])).toBe('tests/test_core.py')
    expect(caseOf(tests[0])).toBe('test_run')
    expect(caseOf(tests[2])).toBe('flow > routes')
  })

  it('falls back to the id when a test has no file', () => {
    const noFile = { ...tests[0], file: '' }
    expect(testFileOf(noFile)).toBe('tests/test_core.py')
  })
})

describe('groupByFile', () => {
  const files = groupByFile(tests, behaviors)

  it('groups by file, sorted, keeping the per-test framework (schema v3)', () => {
    expect(files.map((f) => f.file)).toEqual(['src/flow.test.ts', 'tests/test_core.py'])
    expect(files[0].framework).toBe('vitest')
    expect(files[1].framework).toBe('pytest')
  })

  it('carries behaviors through the grouping', () => {
    const core = files.find((f) => f.file === 'tests/test_core.py')!
    expect(core.tests.filter((t) => t.behavior).length).toBe(1)
  })
})
