import { useState, useEffect, useCallback } from 'react'

const TIMEOUT_MS = 10_000

/**
 * Direct URL-based fetch hook with typed error handling.
 * Returns { data, loading, error, statusCode, retry }.
 *
 * `error` is a structured object: { type, message }
 * `statusCode` is the HTTP status (or null for network errors).
 */
export function useFetch(url, options = {}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statusCode, setStatusCode] = useState(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(url, {
        signal: AbortSignal.timeout(TIMEOUT_MS),
        ...options,
      })
      setStatusCode(response.status)
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        const detail = body.detail || body.message || `Request failed (${response.status})`
        const type =
          response.status === 404 ? 'notFound'
          : response.status === 429 ? 'rateLimit'
          : response.status >= 500 ? 'server'
          : 'client'
        throw Object.assign(new Error(detail), { type, statusCode: response.status })
      }
      const json = await response.json()
      setData(json)
    } catch (err) {
      let type = 'unknown'
      if (err.name === 'TimeoutError' || err.name === 'AbortError') {
        type = 'timeout'
      } else if (!navigator.onLine) {
        type = 'offline'
      } else if (err.type) {
        type = err.type
      }
      setError({ type, message: err.message })
    } finally {
      setLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  return { data, loading, error, statusCode, retry: fetchData }
}
