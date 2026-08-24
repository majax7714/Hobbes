/**
 * Docs — module docs with stale badges and provenance links (§7 tab 3),
 * plus the inferred invariants awaiting confirmation.
 *
 * Every claim's pins are clickable: the point of P3 provenance is that a
 * sentence can be checked against the line it was written from, in one
 * click, without leaving the surface.
 */

import { useMemo, useState } from 'react'

import { api } from '../api'
import { Badge, Empty, Pane, PinList, StaleBadge } from '../components'
import { useAsync } from '../hooks'
import type { Claim, DocEntry, Pin } from '../types'

export function DocsTab({ onOpenPin }: { onOpenPin: (pin: Pin) => void }) {
  const index = useAsync(() => api.docs(), [])
  const [selected, setSelected] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [showInvariants, setShowInvariants] = useState(false)

  const entries = index.data?.artifacts ?? []
  const modules = useMemo(
    () => entries.filter((e) => e.kind === 'module-doc'),
    [entries],
  )
  const needle = query.trim().toLowerCase()
  const shown = modules.filter((e) => !needle || e.id.toLowerCase().includes(needle))
  const stale = entries.filter((e) => e.status !== 'fresh').length

  if (!index.loading && modules.length === 0 && !index.error) {
    return (
      <Empty title="No narrative artifacts yet" hint="hobbes narrate">
        <p>
          The Docs tab renders the M5 narrative pass: one doc per module node, every claim pinned
          to a <code>file:line</code>, each badged fresh or stale against the blob it was written
          against.
        </p>
      </Empty>
    )
  }

  return (
    <div className="content">
      <div className="sidebar">
        <input
          type="search"
          placeholder="filter modules…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ width: '100%', marginBottom: 8 }}
        />
        <div className="row" style={{ marginBottom: 8 }}>
          <Badge kind={stale ? 'stale' : 'fresh'}>
            {stale ? `${stale} stale` : 'all fresh'}
          </Badge>
          <span className="spacer" />
          <button
            className={showInvariants ? 'on' : ''}
            onClick={() => setShowInvariants((v) => !v)}
          >
            invariants
          </button>
        </div>
        <ul className="plain">
          {shown.map((entry) => (
            <li key={entry.id}>
              <DocRow
                entry={entry}
                on={!showInvariants && selected === entry.id}
                onClick={() => {
                  setSelected(entry.id)
                  setShowInvariants(false)
                }}
              />
            </li>
          ))}
        </ul>
      </div>

      <div className="main">
        {showInvariants ? (
          <InferredInvariants onOpenPin={onOpenPin} />
        ) : selected ? (
          <ModuleDocView key={selected} id={selected} onOpenPin={onOpenPin} />
        ) : (
          <div className="empty">
            <h2>{modules.length} module docs</h2>
            <p>
              Pick one. Claims carry their pins; a stale badge means a cited file changed since the
              doc was written — the line the claim points at may no longer be that line.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

function DocRow({ entry, on, onClick }: { entry: DocEntry; on: boolean; onClick: () => void }) {
  return (
    <button className={`listitem ${on ? 'on' : ''}`} onClick={onClick}>
      <div className="row" style={{ gap: 6 }}>
        <StaleBadge status={entry.status} changed={entry.changed} />
        <span className="mono" style={{ overflowWrap: 'anywhere' }}>
          {entry.id}
        </span>
      </div>
    </button>
  )
}

function ModuleDocView({ id, onOpenPin }: { id: string; onOpenPin: (pin: Pin) => void }) {
  const doc = useAsync(() => api.moduleDoc(id), [id])
  return (
    <Pane state={doc}>
      {(d) => (
        <article className="doc">
          <div className="row wrap" style={{ marginBottom: 8 }}>
            <StaleBadge status={d.status} changed={d.changed} />
            <span className="badge muted" title="repo SHA at generation">
              @{(d.sha ?? '').slice(0, 12)}
            </span>
          </div>
          <h1>{d.id}</h1>
          <p style={{ margin: '0 0 4px' }}>
            <button className="pin" onClick={() => onOpenPin({ path: d.path, line: 1 })}>
              {d.path}
            </button>
          </p>

          {d.status === 'stale' && d.changed.length > 0 && (
            <p className="badge stale" style={{ display: 'block', padding: 8, borderRadius: 6 }}>
              cited files changed since generation: {d.changed.join(', ')} — rerun{' '}
              <code>hobbes narrate</code>
            </p>
          )}

          <h2>purpose</h2>
          <ClaimView claim={d.purpose} onOpenPin={onOpenPin} />

          {d.responsibilities?.length > 0 && (
            <>
              <h2>responsibilities</h2>
              {d.responsibilities.map((c, i) => (
                <ClaimView key={i} claim={c} onOpenPin={onOpenPin} />
              ))}
            </>
          )}

          {d.gotchas?.length > 0 && (
            <>
              <h2>gotchas</h2>
              {d.gotchas.map((c, i) => (
                <ClaimView key={i} claim={c} onOpenPin={onOpenPin} />
              ))}
            </>
          )}
        </article>
      )}
    </Pane>
  )
}

function ClaimView({ claim, onOpenPin }: { claim: Claim; onOpenPin: (pin: Pin) => void }) {
  if (!claim?.text) return null
  return (
    <div className="claim">
      <p>{claim.text}</p>
      <PinList pins={claim.pins ?? []} onOpen={onOpenPin} />
    </div>
  )
}

/**
 * Inferred invariants are inert by design (ADR-019): confirming one is
 * Max moving the record into `.hobbes/invariants/`, which is a physical
 * act, not a button. The surface shows them and says so.
 */
function InferredInvariants({ onOpenPin }: { onOpenPin: (pin: Pin) => void }) {
  const inv = useAsync(() => api.invariants(), [])
  return (
    <Pane state={inv}>
      {(data) => (
        <article className="doc">
          <div className="row wrap" style={{ marginBottom: 8 }}>
            <StaleBadge status={data.status} changed={data.changed} />
            <Badge kind="muted">inferred — not yet confirmed</Badge>
          </div>
          <h1>inferred invariants</h1>
          <p style={{ color: 'var(--muted)' }}>
            Statements the code appears to rely on. They are inert until confirmed, and confirming
            one means moving its record into <code>.hobbes/invariants/</code> by hand — nothing in
            this surface can promote them.
          </p>
          {data.invariants.map((i) => (
            <div key={i.id} className="claim" style={{ marginTop: 14 }}>
              <div className="row wrap" style={{ gap: 6, marginBottom: 2 }}>
                <Badge kind="info">{i.id}</Badge>
                <Badge kind="muted">scope {i.scope}</Badge>
                {i.guarded_by?.length ? (
                  <Badge kind="fresh">guarded by {i.guarded_by.length}</Badge>
                ) : (
                  <Badge kind="stale">no guarding test</Badge>
                )}
              </div>
              <p>{i.statement}</p>
              <PinList pins={i.evidence ?? []} onOpen={onOpenPin} />
            </div>
          ))}
        </article>
      )}
    </Pane>
  )
}
