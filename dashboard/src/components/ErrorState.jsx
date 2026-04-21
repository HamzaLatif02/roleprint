import { useState, useEffect } from 'react'

// ── Error type → human copy ───────────────────────────────────────────────────

const CONTENT = {
  timeout: {
    title: 'Request timed out',
    message: 'The server took too long to respond. This can happen when the backend is restarting — wait 30 seconds and try again.',
  },
  offline: {
    title: 'No internet connection',
    message: 'Check your connection and try again.',
  },
  server: {
    title: 'Server error',
    message: 'Something went wrong on our end. This has been logged. Try again in a few minutes.',
  },
  notFound: {
    title: 'Data not found',
    message: 'This data does not exist yet. It may not have been collected for the selected role.',
  },
  rateLimit: {
    title: 'Too many requests',
    message: 'You are making requests too quickly. Wait a moment and try again.',
  },
  parse: {
    title: 'Unexpected response',
    message: 'The server returned data in an unexpected format. Try again — this is usually transient.',
  },
  client: {
    title: 'Request error',
    message: 'The request could not be completed. Check the selected filters and try again.',
  },
  unknown: {
    title: 'Could not load data',
    message: 'An unexpected error occurred. Try refreshing the page.',
  },
}

function technicalDetail(error) {
  if (!error) return null
  const { type, statusCode, url, message } = error
  if (type === 'timeout')   return url ? `Timed out: ${url}` : 'Request exceeded timeout limit'
  if (type === 'offline')   return 'navigator.onLine = false'
  if (type === 'notFound')  return url ? `HTTP 404 — ${url}` : 'HTTP 404'
  if (type === 'rateLimit') return `HTTP 429 — Too Many Requests`
  if (type === 'server')    return statusCode ? `HTTP ${statusCode} — ${message}` : message
  if (type === 'parse')     return 'JSON parse error'
  return message || 'No details available'
}

function RelativeTime({ date }) {
  const [label, setLabel] = useState('')

  useEffect(() => {
    if (!date) return
    const update = () => {
      const seconds = Math.round((Date.now() - date) / 1000)
      if (seconds < 5)  setLabel('just now')
      else if (seconds < 60) setLabel(`${seconds}s ago`)
      else if (seconds < 3600) setLabel(`${Math.round(seconds / 60)}m ago`)
      else setLabel(`${Math.round(seconds / 3600)}h ago`)
    }
    update()
    const id = setInterval(update, 10_000)
    return () => clearInterval(id)
  }, [date])

  return <>{label}</>
}

// ── Component ─────────────────────────────────────────────────────────────────

/**
 * ErrorState — shown when a fetch fails. Replaces the empty area a chart
 * or list would occupy.
 *
 * Props:
 *   error     — structured error object from useApi: { type, message, statusCode, url, timestamp }
 *               OR a plain object with just { type, message } for manually managed state
 *   onRetry   — callback to re-run the failed fetch
 *   className — controls wrapper height; defaults to 'h-64'
 */
export function ErrorState({ error, onRetry, className = 'h-64' }) {
  const [retrying, setRetrying] = useState(false)

  const type = error?.type ?? 'unknown'
  const { title, message } = CONTENT[type] ?? CONTENT.unknown
  const technical = technicalDetail(error)

  const handleRetry = async () => {
    if (!onRetry || retrying) return
    setRetrying(true)
    try {
      await onRetry()
    } finally {
      setRetrying(false)
    }
  }

  return (
    <div className={`error-card flex flex-col items-center justify-center text-center px-6 py-4 ${className}`}>
      {/* Icon */}
      <div className="text-3xl mb-3 select-none" aria-hidden="true">⚠</div>

      {/* Title */}
      <h3 className="font-display text-sm tracking-widest text-rose-signal mb-1.5">
        {title.toUpperCase()}
      </h3>

      {/* Human message */}
      <p className="font-mono text-xs text-ink-300 max-w-xs leading-relaxed mb-4">
        {message}
      </p>

      {/* Retry button */}
      {onRetry && (
        <button
          onClick={handleRetry}
          disabled={retrying}
          className="inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-mono
                     border border-rose-signal/30 text-rose-signal
                     hover:bg-rose-signal/10 transition-colors
                     disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {retrying ? (
            <>
              <svg className="animate-spin w-3 h-3 shrink-0" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              Retrying…
            </>
          ) : (
            <>↺ Try again</>
          )}
        </button>
      )}

      {/* Last attempted + technical detail */}
      <div className="mt-3 space-y-0.5">
        {error?.timestamp && (
          <p className="font-mono text-[10px] text-ink-500">
            Last attempted: <RelativeTime date={error.timestamp} />
          </p>
        )}
        {technical && (
          <p className="font-mono text-[10px] text-ink-500 max-w-xs truncate" title={technical}>
            {technical}
          </p>
        )}
      </div>
    </div>
  )
}

/**
 * ErrorStateRow — for use inside a <tbody> when a table fetch fails.
 * Wraps ErrorState in a <tr><td> so table markup stays valid.
 */
export function ErrorStateRow({ colSpan, error, onRetry }) {
  return (
    <tr>
      <td colSpan={colSpan} className="py-2">
        <ErrorState error={error} onRetry={onRetry} className="h-48" />
      </td>
    </tr>
  )
}
