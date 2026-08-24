/**
 * Tests — the behavioral index (§4.2). Three views over the same join:
 * what guards each module, what each test guards, and the coverage gap
 * that matters more than line coverage (modules no test reaches).
 *
 * The one-line behavior summaries come from the M5 narrative pass and
 * carry their own stale badge; without a narrate pass the tab still
 * works, showing static reach alone.
 */

import { useMemo, useState } from 'react'

import { Badge, StaleBadge, shortPath } from '../components'
import { buildTestIndex, caseOf, groupByFile } from '../lib/testIndex'
import type { Behavior, Graph, Interfaces, Pin, Tests } from '../types'

type View = 'modules' | 'files' | 'gaps' | 'routes'

export function TestsTab({
  graph,
  tests,
  behaviors,
  interfaces,
  onOpenPin,
  onSelectModule,
}: {
  graph: Graph
  tests: Tests
  behaviors: Behavior[]
  interfaces: Interfaces | null
  onOpenPin: (pin: Pin) => void
  onSelectModule: (id: string) => void
}) {
  const [view, setView] = useState<View>('modules')
  const [query, setQuery] = useState('')

  const index = useMemo(() => buildTestIndex(graph, tests.tests, behaviors), [graph, tests, behaviors])
  const files = useMemo(() => groupByFile(tests.tests, behaviors), [tests, behaviors])
  const needle = query.trim().toLowerCase()
  const match = (s: string) => !needle || s.toLowerCase().includes(needle)

  return (
    <div className="content" style={{ flexDirection: 'column' }}>
      <div className="toolbar">
        {(
          [
            ['modules', `guarded modules (${index.covered.length})`],
            ['files', `test files (${files.length})`],
            ['gaps', `unguarded (${index.unguarded.length})`],
            ['routes', `routes (${interfaces?.routes.length ?? 0})`],
          ] as [View, string][]
        ).map(([key, label]) => (
          <button key={key} className={view === key ? 'on' : ''} onClick={() => setView(key)}>
            {label}
          </button>
        ))}
        <span className="spacer" />
        <input
          type="search"
          placeholder="filter…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <span className="badge muted" title="tests carrying a narrative one-liner">
          {index.described}/{index.total} described
        </span>
        {index.orphans.length > 0 && (
          <span className="badge stale" title="these tests reach no module the extractor knows">
            {index.orphans.length} reach nothing
          </span>
        )}
      </div>

      <div className="main">
        {view === 'modules' && (
          <table className="grid">
            <thead>
              <tr>
                <th>module</th>
                <th className="num">tests</th>
                <th>behaviors guarded</th>
              </tr>
            </thead>
            <tbody>
              {index.covered
                .filter((c) => match(c.module.id))
                .map((c) => (
                  <tr key={c.module.id}>
                    <td>
                      <button className="pin" onClick={() => onSelectModule(c.module.id)}>
                        {c.module.id}
                      </button>
                    </td>
                    <td className="num">{c.tests.length}</td>
                    <td>
                      <ul className="plain">
                        {c.tests.slice(0, 6).map(({ test, behavior }) => (
                          <li key={test.id}>
                            <button
                              className="pin"
                              onClick={() => onOpenPin({ path: test.file, line: test.line })}
                            >
                              {caseOf(test)}
                            </button>
                            {behavior ? (
                              <>
                                {' — '}
                                {behavior.text}{' '}
                                {behavior.status === 'stale' && (
                                  <StaleBadge status="stale" />
                                )}
                              </>
                            ) : null}
                          </li>
                        ))}
                        {c.tests.length > 6 && (
                          <li style={{ color: 'var(--muted)' }}>+{c.tests.length - 6} more</li>
                        )}
                      </ul>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        )}

        {view === 'files' && (
          <table className="grid">
            <thead>
              <tr>
                <th>test file</th>
                <th>framework</th>
                <th className="num">cases</th>
                <th>guards</th>
              </tr>
            </thead>
            <tbody>
              {files
                .filter((f) => match(f.file))
                .map((f) => {
                  const modules = [
                    ...new Set(f.tests.flatMap((t) => t.test.reaches_modules ?? [])),
                  ].sort()
                  return (
                    <tr key={f.file}>
                      <td>
                        <button
                          className="pin"
                          onClick={() => onOpenPin({ path: f.file, line: 1 })}
                        >
                          {shortPath(f.file, 4)}
                        </button>
                      </td>
                      <td>
                        <Badge kind={f.framework === 'unknown' ? 'stale' : 'muted'}>
                          {f.framework}
                        </Badge>
                      </td>
                      <td className="num">{f.tests.length}</td>
                      <td>
                        {modules.length === 0 ? (
                          <span style={{ color: 'var(--muted)' }}>nothing</span>
                        ) : (
                          modules.slice(0, 8).map((m) => (
                            <button key={m} className="pin" onClick={() => onSelectModule(m)}>
                              {m}
                            </button>
                          ))
                        )}
                        {modules.length > 8 && (
                          <span style={{ color: 'var(--muted)' }}> +{modules.length - 8}</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
            </tbody>
          </table>
        )}

        {view === 'gaps' && (
          <>
            <p className="empty" style={{ paddingBottom: 0 }}>
              Modules no test statically reaches — behavioral coverage, the metric §4.2 puts above
              line coverage. Static reach is honest but coarse: an entry point pulls in everything
              it can call, so a module here is genuinely unreached, while a module listed as
              guarded may only be reachable, not asserted on.
            </p>
            <table className="grid">
              <thead>
                <tr>
                  <th>module</th>
                  <th>kind</th>
                  <th>path</th>
                </tr>
              </thead>
              <tbody>
                {index.unguarded
                  .filter((n) => match(n.id))
                  .map((n) => (
                    <tr key={n.id}>
                      <td>
                        <button className="pin" onClick={() => onSelectModule(n.id)}>
                          {n.id}
                        </button>
                      </td>
                      <td>
                        <Badge kind="muted">{n.kind}</Badge>
                      </td>
                      <td>
                        {n.path && (
                          <button className="pin" onClick={() => onOpenPin({ path: n.path!, line: 1 })}>
                            {n.path}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </>
        )}

        {view === 'routes' && (
          <table className="grid">
            <thead>
              <tr>
                <th>method</th>
                <th>path</th>
                <th>handler</th>
                <th>framework</th>
                <th>guarded by</th>
              </tr>
            </thead>
            <tbody>
              {(interfaces?.routes ?? [])
                .filter((r) => match(r.path) || match(r.handler))
                .map((r, i) => {
                  const guards = tests.tests.filter((t) => t.reaches?.includes(r.handler))
                  return (
                    <tr key={`${r.method}|${r.path}|${i}`}>
                      <td>
                        <Badge kind="info">{r.method}</Badge>
                      </td>
                      <td className="mono">{r.path}</td>
                      <td>
                        <button className="pin" onClick={() => onOpenPin({ path: r.file, line: r.line })}>
                          {r.handler}
                        </button>
                      </td>
                      <td>
                        <Badge kind="muted">{r.framework}</Badge>
                      </td>
                      <td className="num">{guards.length}</td>
                    </tr>
                  )
                })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
