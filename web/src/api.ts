/**
 * The API client. Reads dominate; the only writes are the escalation
 * verdicts (ADR-022) and the two decision surfaces — intent and
 * invariants (ADR-026). Every failure carries the server's hint, the
 * command that would produce the missing data, so tabs can render "not
 * ingested yet" as guidance rather than as an error.
 */

import type {
  Behavior,
  DecidedInvariant,
  Decisions,
  DiffResult,
  DocEntry,
  Escalation,
  FlightPage,
  Graph,
  Intent,
  Interfaces,
  Invariants,
  ModuleDoc,
  Overview,
  RefInfo,
  SessionSummary,
  SourceFile,
  Tests,
  Verdict,
} from './types'

/** ApiError carries the server's hint alongside the message. */
export class ApiError extends Error {
  status: number
  hint: string
  constructor(status: number, message: string, hint = '') {
    super(message)
    this.status = status
    this.hint = hint
  }
}

/**
 * Artifact schema versions this build can render (ADR-028).
 *
 * The server gates too, but the SPA restates the schema in types.ts and is
 * what would actually mis-render: an unknown version reaching the tabs
 * shows as an empty graph rather than as the mismatch it is. Cheap to
 * check on this side as well, and it keeps `npm run dev` against an older
 * server honest.
 */
export const SUPPORTED_SCHEMA = [3, 4]

function checkSchema(name: string, body: unknown): void {
  const found = (body as { schema_version?: number })?.schema_version
  if (found === undefined || SUPPORTED_SCHEMA.includes(found)) return
  throw new ApiError(
    409,
    `${name} is schema v${found}, but this build reads ${SUPPORTED_SCHEMA.join(', ')}`,
    'the surface and the pipeline are different versions — rebuild, then re-run `hobbes ingest`',
  )
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: { Accept: 'application/json' } })
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`
    let hint = ''
    try {
      const body = await res.json()
      if (body?.error) message = body.error
      if (body?.hint) hint = body.hint
    } catch {
      // A non-JSON error body (a proxy, say) leaves the status text.
    }
    throw new ApiError(res.status, message, hint)
  }
  return (await res.json()) as T
}

async function send<T>(path: string, method: 'POST' | 'PUT', payload?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  })
  const body: { error?: string; hint?: string } = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new ApiError(res.status, body.error ?? `${res.status} ${res.statusText}`, body.hint ?? '')
  }
  return body as T
}

const post = <T>(path: string) => send<T>(path, 'POST')

export const api = {
  overview: () => get<Overview>('/api/overview'),
  graph: async () => {
    const g = await get<Graph>('/api/graph')
    checkSchema('graph.json', g)
    return g
  },
  tests: async () => {
    const t = await get<Tests>('/api/tests')
    checkSchema('tests.json', t)
    return t
  },
  interfaces: () => get<Interfaces>('/api/interfaces'),

  docs: () => get<{ artifacts: DocEntry[] }>('/api/docs'),
  moduleDoc: (id: string) => get<ModuleDoc>(`/api/docs/module/${encodePath(id)}`),
  behaviors: () => get<{ behaviors: Behavior[]; hint?: string }>('/api/behaviors'),
  invariants: () => get<Invariants>('/api/docs/invariants'),

  source: (path: string) => get<SourceFile>(`/api/source?path=${encodeURIComponent(path)}`),
  refs: () => get<{ refs: RefInfo[]; head: string }>('/api/refs'),
  diff: (base = '', head = '') =>
    get<DiffResult>(
      `/api/diff?base=${encodeURIComponent(base)}&head=${encodeURIComponent(head)}`,
    ),

  sessions: () => get<{ sessions: SessionSummary[]; log_dir: string }>('/api/sessions'),
  flight: (id: string, after = 0) =>
    get<FlightPage>(`/api/sessions/${encodeURIComponent(id)}/flight?after=${after}`),
  escalations: (all = false) =>
    get<{ escalations: Escalation[] }>(`/api/escalations${all ? '?all=1' : ''}`),
  resolve: (id: string, verdict: 'approve' | 'deny') =>
    post<{ escalation: Escalation }>(`/api/escalations/${encodeURIComponent(id)}/${verdict}`),

  // The two decision surfaces (ADR-026) — the only writes besides
  // escalation verdicts, and each lands in a file a human can read.
  intent: () => get<Intent>('/api/intent'),
  saveIntent: (text: string | null, confirm: boolean) =>
    send<Intent>('/api/intent', 'PUT', { text: text ?? '', confirm }),
  decisions: () => get<Decisions>('/api/decisions'),
  decide: (key: string, verdict: Verdict) =>
    send<{ decision: DecidedInvariant }>(
      `/api/decisions/${encodeURIComponent(key)}`,
      'POST',
      verdict,
    ),
}

/**
 * Module ids may contain "/" (TS/JS ids are repo-relative paths,
 * ADR-021), and the route matches the rest of the path — so each
 * segment is escaped but the separators are kept.
 */
export function encodePath(id: string): string {
  return id.split('/').map(encodeURIComponent).join('/')
}
