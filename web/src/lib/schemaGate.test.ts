/**
 * The SPA's half of the version gate (ADR-028).
 *
 * The server gates too, but this side is what would actually mis-render:
 * types.ts restates the artifact schema, so an unknown version reaching a
 * tab shows as an empty graph rather than as the mismatch it is.
 */
import { describe, expect, it, vi, afterEach } from 'vitest'

import { api, ApiError, SUPPORTED_SCHEMA } from '../api'

function mockFetch(body: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: async () => body,
    })),
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('artifact schema gate', () => {
  it('accepts every version this build claims to read', async () => {
    for (const schema_version of SUPPORTED_SCHEMA) {
      mockFetch({ schema_version, nodes: [], module_edges: [] })
      const graph = await api.graph()
      expect(graph.schema_version).toBe(schema_version)
    }
  })

  it('refuses a newer version rather than rendering it half-read', async () => {
    mockFetch({ schema_version: 99, nodes: [], module_edges: [] })
    await expect(api.graph()).rejects.toBeInstanceOf(ApiError)
  })

  it('refuses an older version too', async () => {
    mockFetch({ schema_version: 2, nodes: [], module_edges: [] })
    await expect(api.graph()).rejects.toThrow(/schema v2/)
  })

  it('names both sides so the fix is obvious', async () => {
    mockFetch({ schema_version: 99, tests: [] })
    await expect(api.tests()).rejects.toThrow(/reads 3, 4/)
  })

  it('leaves an unversioned body alone — the server already refused those', async () => {
    mockFetch({ nodes: [], module_edges: [] })
    await expect(api.graph()).resolves.toBeTruthy()
  })
})
