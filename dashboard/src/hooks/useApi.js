import { useState, useEffect, useCallback, useRef } from 'react'

/**
 * Generic data-fetching hook.
 * Returns { data, loading, error, refetch }.
 *
 * `error` is a structured object: { type, message, statusCode, url, timestamp }
 *   type: 'timeout' | 'offline' | 'notFound' | 'rateLimit' | 'server' | 'client' | 'parse' | 'unknown'
 *
 * `fetcher` should be a stable function reference (wrap in useCallback at call site).
 */
export function useApi(fetcher, deps = []) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const abortRef = useRef(null)

  const execute = useCallback(async () => {
    if (abortRef.current) abortRef.current = false
    const currentId = {}
    abortRef.current = currentId

    setLoading(true)
    setError(null)
    try {
      const result = await fetcher()
      if (abortRef.current !== currentId) return
      setData(result)
    } catch (err) {
      if (abortRef.current !== currentId) return

      // Build a typed error object whether or not this came from ApiError
      const isApiError = err && err.name === 'ApiError'
      let type = isApiError ? err.type : 'unknown'

      // Override type based on network state if not already typed
      if (!isApiError) {
        if (err.name === 'AbortError') type = 'timeout'
        else if (!navigator.onLine) type = 'offline'
      }

      setError({
        type,
        message: err.message ?? 'Unknown error',
        statusCode: err.statusCode ?? null,
        url: err.url ?? null,
        timestamp: new Date(),
      })
    } finally {
      if (abortRef.current === currentId) setLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    execute()
    return () => { abortRef.current = null }
  }, [execute])

  return { data, loading, error, refetch: execute }
}
