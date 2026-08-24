/**
 * Diff — §7's tab 4, the raw line diff, deliberately last: the whole
 * point of the first three tabs is that reaching this one becomes rare.
 * Defaults to uncommitted work, which is what you are looking at when
 * you open it; a base/head pair gives the three-dot review range.
 */

import { useState } from 'react'

import { api } from '../api'
import { Badge, Pane, shortPath } from '../components'
import { useAsync } from '../hooks'
import { parsePatch } from '../lib/diff'
import type { Pin } from '../types'

export function DiffTab({ onOpenPin }: { onOpenPin: (pin: Pin) => void }) {
  const [base, setBase] = useState('')
  const [head, setHead] = useState('')
  const [applied, setApplied] = useState({ base: '', head: '' })
  const refs = useAsync(() => api.refs(), [])
  const diff = useAsync(() => api.diff(applied.base, applied.head), [applied])

  const options = refs.data?.refs ?? []

  return (
    <div className="content" style={{ flexDirection: 'column' }}>
      <div className="toolbar">
        <label className="row" style={{ gap: 5 }}>
          base
          <select value={base} onChange={(e) => setBase(e.target.value)}>
            <option value="">HEAD</option>
            {options.map((r, i) => (
              <option key={`${r.kind}:${r.name}:${i}`} value={r.name}>
                {r.kind === 'commit' ? `${r.name} — ${r.subject ?? ''}` : `${r.kind} ${r.name}`}
              </option>
            ))}
          </select>
        </label>
        <label className="row" style={{ gap: 5 }}>
          head
          <select value={head} onChange={(e) => setHead(e.target.value)}>
            <option value="">(working tree)</option>
            {options.map((r, i) => (
              <option key={`${r.kind}:${r.name}:${i}`} value={r.name}>
                {r.kind === 'commit' ? `${r.name} — ${r.subject ?? ''}` : `${r.kind} ${r.name}`}
              </option>
            ))}
          </select>
        </label>
        <button onClick={() => setApplied({ base, head })}>compare</button>
        <button
          onClick={() => {
            setBase('')
            setHead('')
            setApplied({ base: '', head: '' })
          }}
        >
          reset
        </button>
        <span className="spacer" />
        {diff.data && (
          <>
            <Badge kind="muted">{diff.data.mode}</Badge>
            <span className="mono" style={{ fontSize: 12, color: 'var(--muted)' }}>
              {diff.data.base} → {diff.data.head}
            </span>
            {diff.data.truncated && <Badge kind="stale">patch truncated</Badge>}
          </>
        )}
      </div>

      <div className="content">
        <Pane state={diff}>
          {(d) =>
            d.files.length === 0 ? (
              <div className="empty">
                <h2>No changes</h2>
                <p>
                  Nothing differs between {d.base} and {d.head}.
                </p>
              </div>
            ) : (
              <>
                <div className="sidebar" style={{ width: 300 }}>
                  <div className="section">
                    <h3>{d.files.length} files</h3>
                    <ul className="plain">
                      {d.files.map((f) => (
                        <li key={f.path} className="row" style={{ gap: 6 }}>
                          <a href={`#patch-${cssID(f.path)}`} className="mono" style={{ flex: 1 }}>
                            {shortPath(f.path, 3)}
                          </a>
                          {f.binary ? (
                            <span className="badge muted">bin</span>
                          ) : (
                            <span className="mono" style={{ fontSize: 11 }}>
                              <span style={{ color: 'var(--ok)' }}>+{f.added}</span>{' '}
                              <span style={{ color: 'var(--bad)' }}>−{f.removed}</span>
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
                <div className="main">
                  <div className="patch">
                    {parsePatch(d.patch).map((file) => (
                      <div key={file.path} id={`patch-${cssID(file.path)}`}>
                        <div className="file">
                          <button className="pin" onClick={() => onOpenPin({ path: file.path, line: 1 })}>
                            {file.path}
                          </button>
                        </div>
                        {file.lines.map((line, i) => (
                          <div key={i} className={`ln ${line.kind}`}>
                            {line.text || ' '}
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )
          }
        </Pane>
      </div>
    </div>
  )
}

function cssID(path: string): string {
  return path.replace(/[^a-zA-Z0-9]/g, '-')
}
