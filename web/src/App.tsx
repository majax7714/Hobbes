/**
 * The shell: repo header, Intent plus the five tabs in §7's review
 * order, and the source-peek drawer every provenance link opens.
 *
 * The heavy artifacts (graph, tests, behaviors) load once here and are
 * shared: the Graph tab wants tests to answer "what guards this", and
 * the Tests tab wants the graph to know which modules exist.
 */

import { useCallback, useEffect, useState } from 'react'

import { api } from './api'
import { Badge, Empty, SourcePeek } from './components'
import { useAsync } from './hooks'
import { DiffTab } from './tabs/DiffTab'
import { DocsTab } from './tabs/DocsTab'
import { GraphTab } from './tabs/GraphTab'
import { IntentTab } from './tabs/IntentTab'
import { SessionsTab } from './tabs/SessionsTab'
import { TestsTab } from './tabs/TestsTab'
import type { Pin } from './types'

type TabName = 'intent' | 'graph' | 'tests' | 'docs' | 'diff' | 'sessions'

export function App() {
  const [tab, setTab] = useState<TabName>('graph')
  const [pin, setPin] = useState<Pin | null>(null)

  const overview = useAsync(() => api.overview(), [])
  // Decisions gate the repo (ADR-026), so the shell knows about them:
  // the count lives in the header, and a repo that still owes one opens
  // on Intent rather than making you find it.
  const decisions = useAsync(() => api.decisions().catch(() => null), [])
  const graph = useAsync(() => api.graph().catch(() => null), [])
  const tests = useAsync(() => api.tests().catch(() => null), [])
  const interfaces = useAsync(() => api.interfaces().catch(() => null), [])
  const behaviors = useAsync(() => api.behaviors().catch(() => ({ behaviors: [] })), [])

  const openPin = useCallback((p: Pin) => setPin(p), [])
  const closePin = useCallback(() => setPin(null), [])

  const reloadAll = useCallback(() => {
    overview.reload()
    graph.reload()
    tests.reload()
    interfaces.reload()
    behaviors.reload()
  }, [overview, graph, tests, interfaces, behaviors])

  // The graph tab drives selection from other tabs ("show me this
  // module"), which is the join §7 asks for between the views.
  const [pendingModule, setPendingModule] = useState<string | null>(null)
  const selectModule = useCallback((id: string) => {
    setPendingModule(id)
    setTab('graph')
  }, [])
  useEffect(() => {
    if (tab !== 'graph') setPendingModule(null)
  }, [tab])

  const [landed, setLanded] = useState(false)
  useEffect(() => {
    if (landed || !decisions.data) return
    setLanded(true)
    if (!decisions.data.ready) setTab('intent')
  }, [decisions.data, landed])

  const o = overview.data
  const counts = o?.counts ?? {}

  return (
    <div className="app">
      <div className="topbar">
        <span className="brand">HOBBES</span>
        {o && (
          <>
            <span className="repo">
              {o.repo}
              {o.branch && <span className="sha"> · {o.branch}</span>}
              {o.head && <span className="sha"> @{o.head.slice(0, 12)}</span>}
            </span>
            {o.dirty && <Badge kind="stale">dirty tree</Badge>}
            {o.behind && (
              <Badge kind="stale">
                artifacts @{(o.sha ?? '').slice(0, 8)} — re-ingest
              </Badge>
            )}
            {o.languages.map((l) => {
              // C-31: the language list is not a capability list. Each
              // badge carries its verification depth, and a single-repo
              // or unverified language is badged as such, not as a peer.
              const row = o.verification_base?.[l]
              const kind = !row || row.depth === 'multi-repo' ? 'muted' : 'stale'
              const title = row
                ? `${row.note} — a sample, not the language (C-31, architecture §3.8)`
                : undefined
              return (
                <span key={l} title={title}>
                  <Badge kind={kind}>
                    {l}
                    {row && ` · ${row.repos} repo${row.repos === 1 ? '' : 's'}`}
                  </Badge>
                </span>
              )
            })}
            {counts.extraction_errors > 0 && (
              <Badge kind="broken">{counts.extraction_errors} extraction errors</Badge>
            )}
            {counts.docs_stale > 0 && <Badge kind="stale">{counts.docs_stale} stale docs</Badge>}
            {decisions.data && !decisions.data.ready && (
              <Badge kind="escalate">
                {decisions.data.blockers.length} awaiting you
              </Badge>
            )}
          </>
        )}
        <span className="spacer" />
        <button onClick={reloadAll} title="artifacts are read per request; this re-reads them">
          reload
        </button>
      </div>

      <nav className="tabs">
        {(
          [
            ['intent', 'Intent', decisions.data?.pending_invariants.length],
            ['graph', 'Graph', counts.nodes],
            ['tests', 'Tests', counts.tests],
            ['docs', 'Docs', counts.docs],
            ['diff', 'Diff', undefined],
            ['sessions', 'Sessions', undefined],
          ] as [TabName, string, number | undefined][]
        ).map(([key, label, count]) => (
          <button key={key} className={tab === key ? 'on' : ''} onClick={() => setTab(key)}>
            {label}
            {count !== undefined && <span className="count">{count}</span>}
          </button>
        ))}
      </nav>

      <div className="content">
        {tab === 'intent' && <IntentTab onOpenPin={openPin} onChanged={decisions.reload} />}

        {tab === 'graph' &&
          (graph.data ? (
            <GraphTab
              key={pendingModule ?? 'graph'}
              graph={graph.data}
              tests={tests.data}
              onOpenPin={openPin}
              initialSelection={pendingModule}
            />
          ) : (
            <NotIngested loading={graph.loading} hint={o?.hint} />
          ))}

        {tab === 'tests' &&
          (graph.data && tests.data ? (
            <TestsTab
              graph={graph.data}
              tests={tests.data}
              behaviors={behaviors.data?.behaviors ?? []}
              interfaces={interfaces.data}
              onOpenPin={openPin}
              onSelectModule={selectModule}
            />
          ) : (
            <NotIngested loading={tests.loading} hint={o?.hint} />
          ))}

        {tab === 'docs' && <DocsTab onOpenPin={openPin} />}
        {tab === 'diff' && <DiffTab onOpenPin={openPin} />}
        {tab === 'sessions' && <SessionsTab />}
      </div>

      {pin && <SourcePeek pin={pin} onClose={closePin} />}
    </div>
  )
}

function NotIngested({ loading, hint }: { loading: boolean; hint?: string }) {
  if (loading) return <div className="empty">loading…</div>
  return (
    <Empty title="This repo has not been ingested" hint={hint ?? 'hobbes ingest'}>
      <p>
        The surface renders the deterministic skeleton first — the module graph, the test
        inventory, the interface list. Run the extractor and reload.
      </p>
    </Empty>
  )
}
