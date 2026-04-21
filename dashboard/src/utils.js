/**
 * Convert a string to Title Case.
 * "data analyst" → "Data Analyst"
 */
export const toTitleCase = (str) =>
  str.replace(/\w\S*/g, (txt) => txt.charAt(0).toUpperCase() + txt.slice(1).toLowerCase())

/**
 * Convert an ISO timestamp string to a human-readable relative time.
 * Returns null when isoString is falsy.
 *
 * Examples:
 *   30 seconds ago  → "just now"
 *   45 minutes ago  → "45 minutes ago"
 *   3 hours ago     → "3 hours ago"
 *   2 days ago      → "2 days ago"
 */
export const getRelativeTime = (isoString) => {
  if (!isoString) return null
  const diff = Date.now() - new Date(isoString).getTime()
  const minutes = Math.floor(diff / 1000 / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`
  return `${days} day${days === 1 ? '' : 's'} ago`
}

/**
 * Return the staleness colour class for a last_scraped ISO timestamp.
 *   < 8 h  → green
 *   8-24 h → amber
 *   > 24 h → red / unknown → muted
 */
export const stalenessColor = (isoString) => {
  if (!isoString) return 'text-ink-500'
  const hours = (Date.now() - new Date(isoString).getTime()) / 1000 / 3600
  if (hours < 8) return 'text-green-400'
  if (hours < 24) return 'text-amber-glow'
  return 'text-rose-400'
}
