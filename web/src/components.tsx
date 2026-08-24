/**
 * The small shared pieces: stale badges, provenance links, the source
 * peek those links open, and the empty/error states that render a
 * missing artifact as the command that produces it (ADR-022).
 */

import { useEffect } from 'react'

import { api } from './api'
import { useAsync } from './hooks'
import type { Badge as BadgeKind, Pin } from './types'

export function Badge({ kind, children }: { kind: string; children: React.ReactNode }) {
  return <span className={`badge ${kind}`}>{children}</span>
}

/** StaleBadge renders ADR-019's verdict, and says what moved. */
export function StaleBadge({ status, changed }: { status: BadgeKind; changed?: string[] }) {
  const title =
    status === 'stale' && changed?.length
      ? `cited files changed since generation:\n${changed.join('\n')}\nrerun \`hobbes narrate\``
      : status === 'fresh'
        ? 'every cited file still matches the blob this was written against'
        : undefined
  return (
    <span className={`badge ${status}`} title={title}>
      {status}
    </span>
  )
}

/**
 * PinLink is P3 made clickable: a claim's `file:line` opens the file at
 * that line. Provenance that cannot be followed is just a citation
 * format.
 */
export function PinLink({ pin, onOpen }: { pin: Pin; onOpen: (pin: Pin) => void }) {
  return (
    <button className="pin" onClick={() => onOpen(pin)} title={`${pin.path}:${pin.line}`}>
      {shortPath(pin.path)}:{pin.line}
    </button>
  )
}

export function PinList({ pins, onOpen }: { pins: Pin[]; onOpen: (pin: Pin) => void }) {
  if (!pins?.length) return null
  return (
    <div className="pins">
      [
      {pins.map((pin, i) => (
        <span key={`${pin.path}:${pin.line}:${i}`}>
          {i > 0 && ', '}
          <PinLink pin={pin} onOpen={onOpen} />
        </span>
      ))}
      ]
    </div>
  )
}

/** shortPath keeps the tail, which is the part that identifies a file. */
export function shortPath(path: string, segments = 3): string {
  const parts = path.split('/')
  return parts.length <= segments ? path : '…/' + parts.slice(-segments).join('/')
}

/**
 * SourcePeek shows a pinned file with the cited line highlighted. It is
 * the end of every provenance link in the surface, which is why it
 * reads the repo through the server rather than trusting the artifact.
 */
export function SourcePeek({ pin, onClose }: { pin: Pin; onClose: () => void }) {
  const { data, error, loading } = useAsync(() => api.source(pin.path), [pin.path])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  useEffect(() => {
    if (!data) return
    // Land the cited line near the middle rather than at the very top,
    // so its context is visible without scrolling.
    document.getElementById(`peek-line-${pin.line}`)?.scrollIntoView({ block: 'center' })
  }, [data, pin.line])

  return (
    <aside className="peek">
      <header>
        <strong>{pin.path}</strong>
        <span className="badge info">line {pin.line}</span>
        <span className="spacer" />
        {data?.truncated && <Badge kind="stale">truncated</Badge>}
        <button onClick={onClose}>close ⌫</button>
      </header>
      <div className="code">
        {loading && <div style={{ padding: '8px 16px' }}>reading…</div>}
        {error && (
          <div style={{ padding: '8px 16px' }} className="err">
            {error.message}
          </div>
        )}
        {data?.lines.map((line, i) => {
          const n = i + 1
          return (
            <div key={n} id={`peek-line-${n}`} className={n === pin.line ? 'hit' : undefined}>
              <span className="no">{n}</span>
              <span>{line || ' '}</span>
            </div>
          )
        })}
      </div>
    </aside>
  )
}

/** Empty renders a missing artifact as guidance, not as a failure. */
export function Empty({
  title,
  hint,
  children,
}: {
  title: string
  hint?: string
  children?: React.ReactNode
}) {
  return (
    <div className="empty">
      <h2>{title}</h2>
      {children}
      {hint && (
        <p>
          Fix: <code>{hint.replace(/`/g, '')}</code>
        </p>
      )}
    </div>
  )
}

/** Pane wraps a tab's load: spinner, guided empty state, or content. */
export function Pane<T>({
  state,
  empty,
  children,
}: {
  state: { data: T | null; error: { message: string; hint: string } | null; loading: boolean }
  empty?: string
  children: (data: T) => React.ReactNode
}) {
  if (state.error) {
    return <Empty title={state.error.message} hint={state.error.hint || undefined} />
  }
  if (!state.data) {
    return <div className="empty">{state.loading ? 'loading…' : (empty ?? 'nothing to show')}</div>
  }
  return <>{children(state.data)}</>
}
