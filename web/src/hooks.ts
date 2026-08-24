/**
 * Data-loading hooks. The surface polls rather than subscribing
 * (ADR-022): the server would have to watch the filesystem to push, and
 * on a local box a cheap interval is the simpler correct thing.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiError } from './api'

export interface Async<T> {
  data: T | null
  error: ApiError | null
  loading: boolean
  reload: () => void
}

/** useAsync runs `load` on mount and whenever `deps` change. */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[] = []): Async<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(true)
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    let live = true
    setLoading(true)
    load()
      .then((value) => {
        if (!live) return
        setData(value)
        setError(null)
      })
      .catch((err: unknown) => {
        if (!live) return
        setError(err instanceof ApiError ? err : new ApiError(0, String(err)))
      })
      .finally(() => {
        if (live) setLoading(false)
      })
    return () => {
      live = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce])

  const reload = useCallback(() => setNonce((n) => n + 1), [])
  return { data, error, loading, reload }
}

/**
 * usePoll re-runs `load` every `ms` while `active`. The first result
 * arrives immediately; later errors leave the last good value in place,
 * so a momentary read failure does not blank a live monitor.
 */
export function usePoll<T>(load: () => Promise<T>, ms: number, active = true): Async<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(true)
  const [nonce, setNonce] = useState(0)
  const saved = useRef(load)
  saved.current = load

  useEffect(() => {
    if (!active) return
    let live = true
    const tick = async () => {
      try {
        const value = await saved.current()
        if (!live) return
        setData(value)
        setError(null)
      } catch (err: unknown) {
        if (!live) return
        setError(err instanceof ApiError ? err : new ApiError(0, String(err)))
      } finally {
        if (live) setLoading(false)
      }
    }
    void tick()
    const timer = setInterval(tick, ms)
    return () => {
      live = false
      clearInterval(timer)
    }
  }, [ms, active, nonce])

  const reload = useCallback(() => setNonce((n) => n + 1), [])
  return { data, error, loading, reload }
}
