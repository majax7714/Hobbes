/**
 * Sessions — the live agent monitor (§7 tab 5): what each session ran,
 * how policy decided, and the escalation queue with approve/deny in the
 * browser (build plan M7).
 *
 * Polling, per ADR-022. A verdict here goes through the same
 * escalation.Resolve the CLI uses, so an expired record still refuses
 * approval; the surface reports that refusal rather than papering over
 * it.
 */

import { useEffect, useState } from 'react'

import { api, ApiError } from '../api'
import { Badge } from '../components'
import { usePoll } from '../hooks'
import type { Escalation, FlightEvent } from '../types'

const POLL_MS = 2500

export function SessionsTab() {
  const [selected, setSelected] = useState<string | null>(null)
  const sessions = usePoll(() => api.sessions(), POLL_MS)
  const escalations = usePoll(() => api.escalations(true), POLL_MS)
  const [notice, setNotice] = useState<string | null>(null)

  const list = sessions.data?.sessions ?? []
  const pending = (escalations.data?.escalations ?? []).filter(
    (e) => e.effective_status === 'pending',
  )
  const resolved = (escalations.data?.escalations ?? []).filter(
    (e) => e.effective_status !== 'pending',
  )

  // Land on the most recently active session rather than an empty pane.
  useEffect(() => {
    if (!selected && list.length > 0) setSelected(list[0].id)
  }, [list, selected])

  async function resolve(id: string, verdict: 'approve' | 'deny') {
    try {
      const res = await api.resolve(id, verdict)
      setNotice(`${id} ${res.escalation.status} by ${res.escalation.approver || 'you'}`)
    } catch (err) {
      setNotice(err instanceof ApiError ? err.message : String(err))
    } finally {
      escalations.reload()
      sessions.reload()
    }
  }

  return (
    <div className="content">
      <div className="sidebar">
        <div className="section">
          <h3>sessions ({list.length})</h3>
          {list.length === 0 && (
            <p style={{ color: 'var(--muted)' }}>
              No sessions yet. <code>hobbes-session start</code> writes a flight log here.
            </p>
          )}
          <ul className="plain">
            {list.map((s) => (
              <li key={s.id}>
                <button
                  className={`listitem ${selected === s.id ? 'on' : ''}`}
                  onClick={() => setSelected(s.id)}
                >
                  <div className="row" style={{ gap: 6 }}>
                    <i className={`dot ${s.active ? 'live' : ''}`} />
                    <span className="mono" style={{ flex: 1, overflowWrap: 'anywhere' }}>
                      {s.id}
                    </span>
                    {s.pending > 0 && <Badge kind="escalate">{s.pending}</Badge>}
                  </div>
                  <div className="row" style={{ gap: 6, marginTop: 3, fontSize: 11.5 }}>
                    <Badge kind="muted">{s.role || 'unknown'}</Badge>
                    <span style={{ color: 'var(--ok)' }}>{s.allowed}✓</span>
                    <span style={{ color: 'var(--bad)' }}>{s.denied}✕</span>
                    <span style={{ color: 'var(--escalate)' }}>{s.escalated}⏸</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="main">
        {notice && (
          <div className="toolbar">
            <span>{notice}</span>
            <span className="spacer" />
            <button onClick={() => setNotice(null)}>dismiss</button>
          </div>
        )}

        <div className="section" style={{ padding: '10px 12px 0' }}>
          <h3>
            escalations awaiting you ({pending.length})
          </h3>
          {pending.length === 0 ? (
            <p style={{ color: 'var(--muted)', margin: 0 }}>Nothing parked.</p>
          ) : (
            pending.map((e) => <EscalationCard key={e.id} card={e} onResolve={resolve} />)
          )}
          {resolved.length > 0 && (
            <details style={{ margin: '8px 0 14px' }}>
              <summary style={{ color: 'var(--muted)', cursor: 'pointer' }}>
                {resolved.length} resolved
              </summary>
              {resolved.map((e) => (
                <EscalationCard key={e.id} card={e} onResolve={resolve} />
              ))}
            </details>
          )}
        </div>

        {selected && <Flight session={selected} />}
      </div>
    </div>
  )
}

function EscalationCard({
  card,
  onResolve,
}: {
  card: Escalation
  onResolve: (id: string, verdict: 'approve' | 'deny') => void
}) {
  const pending = card.effective_status === 'pending'
  return (
    <div className={`card ${pending ? 'pending' : ''}`}>
      <div className="row wrap" style={{ gap: 6 }}>
        <Badge kind={statusBadge(card.effective_status)}>{card.effective_status}</Badge>
        <span className="mono" style={{ fontSize: 11.5, color: 'var(--muted)' }}>
          {card.session} · {card.role}
        </span>
        <span className="spacer" />
        {pending && card.seconds_left > 0 && (
          <span className="badge muted" title={`expires ${card.expires_at}`}>
            {formatLeft(card.seconds_left)} left
          </span>
        )}
        {card.approver && <span className="badge muted">by {card.approver}</span>}
      </div>
      <div className="cmd">{card.command}</div>
      <div className="row wrap" style={{ gap: 6 }}>
        <span className="badge muted" title="the decisive policy rule">
          {card.policy_rule}
        </span>
        {card.reason && <span style={{ color: 'var(--muted)', fontSize: 12 }}>{card.reason}</span>}
        <span className="spacer" />
        <button className="go" disabled={!card.resolvable} onClick={() => onResolve(card.id, 'approve')}>
          approve
        </button>
        <button className="danger" disabled={!card.resolvable} onClick={() => onResolve(card.id, 'deny')}>
          deny
        </button>
      </div>
    </div>
  )
}

function statusBadge(status: string): string {
  if (status === 'approved') return 'fresh'
  if (status === 'denied' || status === 'expired') return 'broken'
  return 'escalate'
}

function formatLeft(seconds: number): string {
  if (seconds < 90) return `${seconds}s`
  return `${Math.round(seconds / 60)}m`
}

/**
 * Flight tails one session's log on the server's line cursor, so a poll
 * fetches only what is new. Switching sessions resets the cursor.
 */
function Flight({ session }: { session: string }) {
  const [events, setEvents] = useState<FlightEvent[]>([])
  const [cursor, setCursor] = useState(0)

  useEffect(() => {
    setEvents([])
    setCursor(0)
  }, [session])

  const page = usePoll(() => api.flight(session, cursor), POLL_MS)

  useEffect(() => {
    const got = page.data
    // A page is applied only if it starts exactly where this tail is.
    // The cursor update re-runs this effect with the same page still in
    // hand, and without the check that appends every page twice.
    if (!got || got.session !== session || got.after !== cursor) return
    if (got.next === cursor) return
    setEvents((prev) => [...prev, ...got.events])
    setCursor(got.next)
  }, [page.data, session, cursor])

  return (
    <div className="section" style={{ padding: '0 0 20px' }}>
      <h3 style={{ padding: '0 12px' }}>
        flight log — {session} ({events.length} events)
      </h3>
      {page.error && <p className="err" style={{ padding: '0 12px' }}>{page.error.message}</p>}
      {events.length === 0 && !page.error && (
        <p style={{ color: 'var(--muted)', padding: '0 12px' }}>No events recorded yet.</p>
      )}
      <div className="flight">
        {events.map((ev, i) => (
          <div className="ev" key={`${ev.ts}-${i}`}>
            <span style={{ color: 'var(--dim)' }}>{clock(ev.ts)}</span>
            <span className={ev.decision}>{ev.decision}</span>
            <span style={{ overflowWrap: 'anywhere' }}>
              {ev.argv?.join(' ')}
              <span className="rule"> — {ev.policy_rule}</span>
            </span>
            <span style={{ color: ev.exit === 0 ? 'var(--dim)' : 'var(--bad)' }}>
              {ev.exit === null || ev.exit === undefined ? '' : `exit ${ev.exit}`}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function clock(ts: string): string {
  const t = new Date(ts)
  return Number.isNaN(t.valueOf()) ? ts.slice(11, 19) : t.toLocaleTimeString()
}
