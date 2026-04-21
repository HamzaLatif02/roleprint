// Requests are proxied to Railway via vercel.json rewrites — no env var needed.
const BASE = ''

async function apiFetch(path, opts = {}) {
  const url = `${BASE}${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json()
}

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
