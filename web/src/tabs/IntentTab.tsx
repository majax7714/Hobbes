/**
 * Intent — the two things that need a human (ADR-026).
 *
 * Everything else Hobbes does is a natural part of the mechanism. This
 * is where the exceptions live: the repo policy, and a verdict on every
 * inferred invariant. Both write real files, and both show you what will
 * land before it lands — if the point is that review stays on your side,
 * seeing the text is the review.
 *
 * Verdicts are keyboard-driven because a first run on a large repo
 * presents its whole queue at once, and the queue must be fast to walk.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'

import { api, ApiError } from '../api'
import { Badge, Empty, PinList } from '../components'
import { useAsync } from '../hooks'
import { diffLines } from '../lib/policyDiff'
import type { Decisions, Intent, PendingInvariant, Pin, Verdict } from '../types'

export function IntentTab({
  onOpenPin,
  onChanged,
}: {
  onOpenPin: (pin: Pin) => void
  /** Tell the shell a decision landed, so its header count follows. */
  onChanged?: () => void
}) {
  const intent = useAsync(() => api.intent().catch(() => null), [])
  const decisions = useAsync(() => api.decisions(), [])
  const [notice, setNotice] = useState<string | null>(null)

  const refresh = useCallback(() => {
    intent.reload()
    decisions.reload()
    onChanged?.()
  }, [intent, decisions, onChanged])

  const state = decisions.data
  const pending = state?.pending_invariants ?? []

  return (
    <div className="content" style={{ flexDirection: 'column' }}>
      <div className="toolbar">
        {state?.ready ? (
          <Badge kind="fresh">ready to develop</Badge>
        ) : (
          <Badge kind="escalate">
            {(state?.blockers ?? []).length || '…'} thing
            {(state?.blockers ?? []).length === 1 ? '' : 's'} awaiting you
          </Badge>
        )}
        {(state?.blockers ?? []).map((blocker) => (
          <span key={blocker} style={{ color: 'var(--muted)', fontSize: 12.5 }}>
            {blocker}
          </span>
        ))}
        <span className="spacer" />
        {notice && (
          <>
            <span style={{ fontSize: 12.5 }}>{notice}</span>
            <button onClick={() => setNotice(null)}>dismiss</button>
          </>
        )}
        <button onClick={refresh}>reload</button>
      </div>

      <div className="main">
        <IntentPanel
          intent={intent.data}
          loading={intent.loading}
          onSaved={(message) => {
            setNotice(message)
            refresh()
          }}
        />
        <InvariantQueue
          pending={pending}
          decided={state?.decided ?? []}
          onOpenPin={onOpenPin}
          onDecided={(message) => {
            setNotice(message)
            refresh()
          }}
        />
      </div>
    </div>
  )
}

/** The policy editor. Writes .hobbes/policies/repo.policy directly. */
function IntentPanel({
  intent,
  loading,
  onSaved,
}: {
  intent: Intent | null
  loading: boolean
  onSaved: (message: string) => void
}) {
  const [draft, setDraft] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setDraft(null)
  }, [intent?.blob])

  if (loading) return <div className="doc">loading intent…</div>
  if (!intent) {
    return (
      <div className="doc">
        <Empty title="No repo policy yet" hint="hobbes init">
          <p>Intent is the repo policy. Scaffold it and reload.</p>
        </Empty>
      </div>
    )
  }

  const text = draft ?? intent.text
  const dirty = draft !== null && draft !== intent.text

  async function save(confirm: boolean) {
    setBusy(true)
    setError(null)
    try {
      await api.saveIntent(dirty ? text : null, confirm)
      onSaved(confirm ? 'intent confirmed' : 'policy saved')
      setDraft(null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="doc" style={{ maxWidth: '72rem' }}>
      <div className="row wrap" style={{ gap: 8, marginBottom: 8 }}>
        <h1 style={{ margin: 0 }}>intent</h1>
        {intent.confirmed ? (
          <Badge kind="fresh">confirmed</Badge>
        ) : (
          <Badge kind="escalate">never confirmed</Badge>
        )}
        {intent.changed_since_confirm && (
          <Badge kind="stale">edited outside the surface since</Badge>
        )}
        <span className="mono" style={{ fontSize: 12, color: 'var(--dim)' }}>
          {intent.path}
        </span>
      </div>

      <p style={{ color: 'var(--muted)', margin: '0 0 10px', maxWidth: '46rem' }}>
        What a session may do. <code>default: escalate</code> means an unlisted command
        parks and waits for you rather than running — allow the loop you want run
        unattended, deny what should never happen, and leave the rest to ask.
      </p>

      {!intent.confirmed && (
        <p className="badge escalate" style={{ display: 'block', padding: 8, borderRadius: 6 }}>
          This policy has never been confirmed. Read it, then confirm — “I never looked”
          and “I read it and it's fine” must not look alike.
        </p>
      )}

      <textarea
        className="policy-editor"
        spellCheck={false}
        value={text}
        onChange={(e) => setDraft(e.target.value)}
      />

      {dirty && <PolicyDiff before={intent.text} after={text} />}
      {error && <p className="err">{error}</p>}

      <div className="row wrap" style={{ gap: 8, marginTop: 10 }}>
        <button className="go" disabled={busy} onClick={() => save(true)}>
          {dirty ? 'save and confirm' : intent.confirmed ? 're-confirm' : 'confirm'}
        </button>
        <button disabled={!dirty || busy} onClick={() => save(false)}>
          save without confirming
        </button>
        <button disabled={!dirty || busy} onClick={() => setDraft(null)}>
          discard edits
        </button>
        <span style={{ color: 'var(--dim)', fontSize: 12 }}>
          verify with <code>hobbes policy resolve "some command"</code>
        </span>
      </div>
    </section>
  )
}

/** A line-level diff of what will be written, shown before writing it. */
function PolicyDiff({ before, after }: { before: string; after: string }) {
  const rows = useMemo(() => diffLines(before, after), [before, after])
  return (
    <div className="section" style={{ marginTop: 12 }}>
      <h3>what will be written</h3>
      <div className="patch" style={{ border: '1px solid var(--line)', borderRadius: 6 }}>
        {rows.map((row, i) => (
          <div key={i} className={`ln ${row.kind}`}>
            {row.text || ' '}
          </div>
        ))}
      </div>
    </div>
  )
}

/** Approve / deny / edit, one card at a time, keyboard-driven. */
function InvariantQueue({
  pending,
  decided,
  onOpenPin,
  onDecided,
}: {
  pending: PendingInvariant[]
  decided: Decisions['decided']
  onOpenPin: (pin: Pin) => void
  onDecided: (message: string) => void
}) {
  const [editing, setEditing] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = useCallback(
    async (key: string, verdict: Verdict) => {
      setBusy(true)
      setError(null)
      try {
        await api.decide(key, verdict)
        setEditing(null)
        onDecided(`invariant ${verdict.verdict}`)
      } catch (err) {
        setError(err instanceof ApiError ? err.message : String(err))
      } finally {
        setBusy(false)
      }
    },
    [onDecided],
  )

  // The first pending card takes a/d/e so a long queue is walkable
  // without the mouse.
  const first = pending[0]
  useEffect(() => {
    if (!first || editing) return
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null
      if (target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return
      if (e.key === 'a') void submit(first.key, { verdict: 'approved' })
      else if (e.key === 'd') void submit(first.key, { verdict: 'denied' })
      else if (e.key === 'e') setEditing(first.key)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [first, editing, submit])

  return (
    <section className="doc" style={{ maxWidth: '72rem', paddingTop: 0 }}>
      <div className="row wrap" style={{ gap: 8, marginBottom: 8 }}>
        <h1 style={{ margin: 0 }}>invariants</h1>
        {pending.length === 0 ? (
          <Badge kind="fresh">nothing awaiting a verdict</Badge>
        ) : (
          <Badge kind="escalate">{pending.length} awaiting</Badge>
        )}
      </div>

      <p style={{ color: 'var(--muted)', margin: '0 0 12px', maxWidth: '46rem' }}>
        Statements the code appears to rely on. A verdict holds until you change it; only
        invariants whose <em>text</em> is new get asked again. Approving writes a real
        record into <code>.hobbes/invariants/</code>.
      </p>

      {error && <p className="err">{error}</p>}

      {pending.length > 0 && (
        <p style={{ color: 'var(--dim)', fontSize: 12, margin: '0 0 10px' }}>
          keys: <strong>a</strong> approve · <strong>d</strong> deny · <strong>e</strong> edit
          (first card)
        </p>
      )}

      {pending.map((item, index) => (
        <InvariantCard
          key={item.key}
          item={item}
          first={index === 0}
          editing={editing === item.key}
          busy={busy}
          onEdit={() => setEditing(item.key)}
          onCancel={() => setEditing(null)}
          onSubmit={(verdict) => submit(item.key, verdict)}
          onOpenPin={onOpenPin}
        />
      ))}

      {decided.length > 0 && (
        <details style={{ marginTop: 18 }}>
          <summary style={{ color: 'var(--muted)', cursor: 'pointer' }}>
            {decided.length} already decided
          </summary>
          <ul className="plain" style={{ marginTop: 8 }}>
            {decided.map((d) => (
              <li key={d.key} className="row wrap" style={{ gap: 8 }}>
                <Badge kind={d.verdict === 'denied' ? 'broken' : 'fresh'}>{d.verdict}</Badge>
                {d.record && <span className="badge muted">{d.record}</span>}
                <span style={{ color: 'var(--muted)', fontSize: 12.5 }}>
                  {d.source_statement}
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  )
}

function InvariantCard({
  item,
  first,
  editing,
  busy,
  onEdit,
  onCancel,
  onSubmit,
  onOpenPin,
}: {
  item: PendingInvariant
  first: boolean
  editing: boolean
  busy: boolean
  onEdit: () => void
  onCancel: () => void
  onSubmit: (verdict: Verdict) => void
  onOpenPin: (pin: Pin) => void
}) {
  const [statement, setStatement] = useState(item.statement)
  const [scope, setScope] = useState(item.scope)
  const [target, setTarget] = useState('soft')
  const [rule, setRule] = useState('')

  return (
    <div className={`card ${first ? 'pending' : ''}`} style={{ marginBottom: 12 }}>
      <div className="row wrap" style={{ gap: 6, marginBottom: 6 }}>
        <Badge kind="muted">{item.id}</Badge>
        <Badge kind="info">scope {item.scope}</Badge>
        {item.guarded_by.length > 0 ? (
          <Badge kind="fresh">guarded by {item.guarded_by.length}</Badge>
        ) : (
          <Badge kind="stale">no guarding test</Badge>
        )}
        {first && <span className="badge escalate">a / d / e</span>}
      </div>

      {editing ? (
        <>
          <label className="field">
            <span>statement</span>
            <textarea
              rows={3}
              value={statement}
              onChange={(e) => setStatement(e.target.value)}
              spellCheck={false}
            />
          </label>
          <div className="row wrap" style={{ gap: 10, margin: '8px 0' }}>
            <label className="field inline">
              <span>scope</span>
              <input value={scope} onChange={(e) => setScope(e.target.value)} />
            </label>
            <label className="field inline">
              <span>checked by</span>
              <select value={target} onChange={(e) => setTarget(e.target.value)}>
                <option value="soft">soft — a reviewer judges it</option>
                <option value="import-linter">import-linter</option>
                <option value="dep-cruiser">dep-cruiser</option>
                <option value="semgrep">semgrep</option>
                <option value="rego">rego</option>
              </select>
            </label>
          </div>
          {target !== 'soft' && (
            <label className="field">
              <span>compile.rule (YAML)</span>
              <textarea
                rows={5}
                spellCheck={false}
                placeholder={'kind: forbidden-import\nimporters: ["*"]\nimported: [ext:requests]'}
                value={rule}
                onChange={(e) => setRule(e.target.value)}
              />
            </label>
          )}
          <div className="row wrap" style={{ gap: 6, marginTop: 8 }}>
            <button
              className="go"
              disabled={busy}
              onClick={() =>
                onSubmit({ verdict: 'edited', statement, scope, target, rule_yaml: rule })
              }
            >
              save as edited
            </button>
            <button disabled={busy} onClick={onCancel}>
              cancel
            </button>
            <span style={{ color: 'var(--dim)', fontSize: 12 }}>
              validate after with <code>hobbes invariants check</code>
            </span>
          </div>
        </>
      ) : (
        <>
          <p style={{ margin: '0 0 6px' }}>{item.statement}</p>
          {item.nearest_confirmed && (
            <div
              className="card"
              style={{
                border: '1px solid var(--line)',
                borderLeft: '3px solid var(--warn, #b8860b)',
                padding: '6px 10px',
                margin: '0 0 8px',
              }}
            >
              <div className="row wrap" style={{ gap: 6, marginBottom: 4 }}>
                <Badge kind="escalate">
                  possible restatement of {item.nearest_confirmed.id}
                </Badge>
              </div>
              <p style={{ margin: 0, color: 'var(--muted)', fontSize: 13 }}>
                {item.nearest_confirmed.statement}
              </p>
              <p style={{ margin: '4px 0 0', color: 'var(--dim)', fontSize: 12 }}>
                Read the confirmed record before approving: a reworded duplicate
                once re-introduced a claim its original had been corrected to
                remove. If this proposal adds nothing, deny it.
              </p>
            </div>
          )}
          <PinList pins={item.evidence} onOpen={onOpenPin} />
          <div className="row wrap" style={{ gap: 6, marginTop: 8 }}>
            <span className="spacer" />
            <button className="go" disabled={busy} onClick={() => onSubmit({ verdict: 'approved' })}>
              approve
            </button>
            <button disabled={busy} onClick={onEdit}>
              edit
            </button>
            <button className="danger" disabled={busy} onClick={() => onSubmit({ verdict: 'denied' })}>
              deny
            </button>
          </div>
        </>
      )}
    </div>
  )
}
