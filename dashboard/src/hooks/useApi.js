import { useState, useEffect, useCallback, useRef } from 'react'

/**
 * Generic data-fetching hook.
 * Returns { data, loading, error, refetch }.
 *
 * `fetcher` should be a stable function reference (wrap in useCallback at call site,
 * or pass a string key + deps to rerun on change).
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
      setError(err.message ?? 'Unknown error')
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
