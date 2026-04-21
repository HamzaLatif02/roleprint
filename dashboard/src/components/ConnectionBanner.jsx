import { useState, useEffect } from 'react'

/**
 * ConnectionBanner — a slim banner that appears at the top of every page
 * when the user is offline, and briefly on reconnection.
 *
 * - Offline:  amber banner, stays until online (not dismissable)
 * - Restored: green banner, auto-dismisses after 3 seconds
 */
export function ConnectionBanner() {
  const [status, setStatus] = useState(null) // null | 'offline' | 'restored'

  useEffect(() => {
    // Set initial state if already offline when component mounts
    if (!navigator.onLine) setStatus('offline')

    const handleOffline = () => setStatus('offline')
    const handleOnline = () => {
      setStatus('restored')
      const id = setTimeout(() => setStatus(null), 3000)
      return id
    }

    window.addEventListener('offline', handleOffline)
    window.addEventListener('online', handleOnline)

    return () => {
      window.removeEventListener('offline', handleOffline)
      window.removeEventListener('online', handleOnline)
    }
  }, [])

  if (!status) return null

  if (status === 'offline') {
    return (
      <div
        role="status"
        aria-live="polite"
        className="shrink-0 flex items-center justify-center gap-2 px-4 py-2
                   bg-amber-muted border-b border-amber-dim/40"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-amber-glow shrink-0" />
        <span className="font-mono text-[10px] tracking-wide text-amber-glow">
          YOU ARE OFFLINE — DATA MAY BE OUT OF DATE
        </span>
      </div>
    )
  }

  if (status === 'restored') {
    return (
      <div
        role="status"
        aria-live="polite"
        className="shrink-0 flex items-center justify-center gap-2 px-4 py-2
                   border-b"
        style={{ background: 'rgba(45,212,191,0.12)', borderColor: 'rgba(45,212,191,0.25)' }}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-teal-signal shrink-0" />
        <span className="font-mono text-[10px] tracking-wide text-teal-signal">
          BACK ONLINE
        </span>
      </div>
    )
  }

  return null
}
