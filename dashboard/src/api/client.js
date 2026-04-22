// Requests are proxied to Railway via vercel.json rewrites — no env var needed.
const BASE = ''
const TIMEOUT_MS = 10_000

// ── Typed error class ─────────────────────────────────────────────────────────

export class ApiError extends Error {
  /**
   * @param {string} message
   * @param {{ type: string, statusCode: number|null, url: string }} opts
   */
  constructor(message, { type, statusCode, url }) {
    super(message)
    this.name = 'ApiError'
    this.type = type           // 'timeout' | 'offline' | 'notFound' | 'rateLimit' | 'server' | 'client' | 'parse' | 'unknown'
    this.statusCode = statusCode
    this.url = url
  }
}

// ── Core fetch wrapper ────────────────────────────────────────────────────────

async function apiFetch(path, opts = {}) {
  const url = `${BASE}${path}`

  // Manual abort controller so we can apply a timeout
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort('timeout'), TIMEOUT_MS)

  try {
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...opts.headers },
      signal: controller.signal,
      ...opts,
    })
    clearTimeout(timeoutId)

    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      const detail = body.detail || body.message || `HTTP ${res.status}`
      const type =
        res.status === 404 ? 'notFound'
        : res.status === 429 ? 'rateLimit'
        : res.status >= 500 ? 'server'
        : 'client'
      throw new ApiError(detail, { type, statusCode: res.status, url })
    }

    try {
      return await res.json()
    } catch {
      throw new ApiError('Response could not be parsed as JSON', { type: 'parse', statusCode: res.status, url })
    }
  } catch (err) {
    clearTimeout(timeoutId)
    if (err instanceof ApiError) throw err

    // AbortController fires with reason='timeout' or name='AbortError'
    if (err.name === 'AbortError' || err === 'timeout' || controller.signal.aborted) {
      throw new ApiError(`Request timed out after ${TIMEOUT_MS / 1000}s`, { type: 'timeout', statusCode: null, url })
    }
    // Offline / network failure
    if (!navigator.onLine) {
      throw new ApiError('No internet connection', { type: 'offline', statusCode: null, url })
    }
    throw new ApiError(err.message || 'Unknown error', { type: 'unknown', statusCode: null, url })
  }
}

// ── API methods ───────────────────────────────────────────────────────────────

export const api = {
  stats: (roleCategory) => {
    const params = new URLSearchParams()
    if (roleCategory) params.set('role_category', roleCategory)
    const qs = params.toString()
    return apiFetch(`/api/stats/summary${qs ? `?${qs}` : ''}`)
  },

  roles: () => apiFetch('/api/roles'),

  trending: (roleCategory, weeks = 8) => {
    const params = new URLSearchParams({ weeks })
    if (roleCategory) params.set('role_category', roleCategory)
    return apiFetch(`/api/skills/trending?${params}`)
  },

  trendingPaged: (roleCategory, page = 1, pageSize = 15, weeks = 4) => {
    const params = new URLSearchParams({ page, page_size: pageSize, weeks })
    if (roleCategory) params.set('role_category', roleCategory)
    return apiFetch(`/api/skills/trending/paged?${params}`)
  },

  emerging: (lookbackWeeks = 6) =>
    apiFetch(`/api/skills/emerging?lookback_weeks=${lookbackWeeks}`),

  compare: (roles) => {
    const encoded = roles.map(encodeURIComponent).join(',')
    return apiFetch(`/api/skills/compare?roles=${encoded}`)
  },

  sentiment: (roleCategory, weeks = 12) => {
    const params = new URLSearchParams({ weeks })
    if (roleCategory) params.set('role_category', roleCategory)
    return apiFetch(`/api/sentiment/timeline?${params}`)
  },

  skillGap: (roleCategory, userSkills) =>
    apiFetch('/api/skills/gap', {
      method: 'POST',
      body: JSON.stringify({ role_category: roleCategory, user_skills: userSkills }),
    }),

  postings: (roleCategory, page = 1, pageSize = 20) => {
    const params = new URLSearchParams({ page, page_size: pageSize })
    if (roleCategory) params.set('role_category', roleCategory)
    return apiFetch(`/api/postings/recent?${params}`)
  },

  topics: (roleCategory) => {
    const params = new URLSearchParams()
    if (roleCategory) params.set('role_category', roleCategory)
    return apiFetch(`/api/topics?${params}`)
  },
}
