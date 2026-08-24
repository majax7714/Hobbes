import { describe, expect, it } from 'vitest'

import { diffLines } from './policyDiff'

const base = ['version: 1', 'scope: repo', 'default: escalate', '', 'rules:', '  - pattern: "a"'].join(
  '\n',
)

describe('diffLines', () => {
  it('reports nothing when nothing changed', () => {
    expect(diffLines(base, base).every((r) => r.kind === 'context')).toBe(true)
  })

  it('marks a changed line as a removal and an addition', () => {
    const after = base.replace('default: escalate', 'default: allow')
    const rows = diffLines(base, after)
    expect(rows).toContainEqual({ kind: 'del', text: '-default: escalate' })
    expect(rows).toContainEqual({ kind: 'add', text: '+default: allow' })
  })

  it('shows an added rule without repeating the whole file', () => {
    const after = base + '\n    decision: allow'
    const rows = diffLines(base, after)
    expect(rows.filter((r) => r.kind === 'add')).toEqual([
      { kind: 'add', text: '+    decision: allow' },
    ])
    // Only a little context, not the six unchanged lines above it.
    expect(rows.filter((r) => r.kind === 'context').length).toBeLessThanOrEqual(4)
  })

  it('shows a deletion', () => {
    const after = base.split('\n').filter((l) => l !== 'scope: repo').join('\n')
    expect(diffLines(base, after)).toContainEqual({ kind: 'del', text: '-scope: repo' })
  })

  it('handles a policy written from nothing', () => {
    const rows = diffLines('', base)
    expect(rows.filter((r) => r.kind === 'add').length).toBeGreaterThan(1)
  })

  it('keeps removals before additions so the pair reads as a change', () => {
    const after = base.replace('default: escalate', 'default: deny')
    const rows = diffLines(base, after)
    const del = rows.findIndex((r) => r.kind === 'del')
    const add = rows.findIndex((r) => r.kind === 'add')
    expect(del).toBeLessThan(add)
  })
})
