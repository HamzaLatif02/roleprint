import { useState, useCallback, useEffect } from 'react'
import { useApi } from '../hooks/useApi'
import { api } from '../api/client'
import { SkeletonChart } from '../components/Skeleton'
import { ErrorState } from '../components/ErrorState'
import { EmptyState } from '../components/EmptyState'
import { toTitleCase } from '../utils'

function VennOverlap({ pct }) {
  // Visual overlap indicator: two overlapping circles, overlap width proportional to pct
  const overlap = Math.round(pct * 0.8) // 0-80px of circle width (100px) overlaps
  const circleSize = 100
  const gap = circleSize - overlap

  return (
    <div className="flex flex-col items-center py-8">
      <div className="relative flex items-center justify-center" style={{ width: circleSize * 2 - overlap + 24, height: circleSize + 24 }}>
        {/* Left circle */}
        <div
          className="absolute rounded-full border-2 transition-all duration-700"
          style={{
            width: circleSize,
            height: circleSize,
            left: 12,
            borderColor: 'rgba(129,140,248,0.6)',
            background: 'rgba(129,140,248,0.08)',
          }}
        />
        {/* Right circle */}
        <div
          className="absolute rounded-full border-2 transition-all duration-700"
          style={{
            width: circleSize,
            height: circleSize,
            left: gap + 12,
            borderColor: 'rgba(245,166,35,0.6)',
            background: 'rgba(245,166,35,0.08)',
          }}
        />
        {/* Overlap region label */}
        <div
          className="absolute flex flex-col items-center justify-center"
          style={{
            left: gap / 2 + 12,
            width: overlap,
            height: circleSize,
            zIndex: 2,
          }}
        >
          <div className="font-display text-2xl text-amber-glow glow-amber leading-none">{pct}%</div>
          <div className="label-mono text-[8px] text-ink-400 mt-0.5">overlap</div>
        </div>
      </div>
    </div>
  )
}

function SkillTag({ skill, highlight = false }) {
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 font-mono text-xs m-0.5 transition-all ${
        highlight
          ? 'bg-amber-100 dark:bg-amber-faint border border-amber-300/60 dark:border-amber-muted text-amber-800 dark:text-amber-glow'
          : 'bg-void-600 border border-border text-ink-300'
      }`}
    >
      {skill}
    </span>
  )
}

export default function Comparison() {
  const [roleA, setRoleA] = useState('')
  const [roleB, setRoleB] = useState('')
  const [compareRoles, setCompareRoles] = useState(null)

  const fetchRoles = useCallback(() => api.roles(), [])
  const { data: roles } = useApi(fetchRoles)

  const fetchCompare = useCallback(
    () => compareRoles ? api.compare(compareRoles) : Promise.resolve(null),
    [compareRoles ? compareRoles.join(':') : null] // eslint-disable-line react-hooks/exhaustive-deps
  )
  const { data: result, loading, error, refetch } = useApi(fetchCompare, [compareRoles])

  const canCompare = roleA && roleB && roleA !== roleB

  const handleCompare = () => {
    if (canCompare) setCompareRoles([roleA, roleB])
  }

  // Auto-compare when both roles are pre-selected
  useEffect(() => {
    if (roles?.length >= 2 && !roleA && !roleB) {
      setRoleA(roles[0].role_category)
      setRoleB(roles[1]?.role_category ?? '')
    }
  }, [roles]) // eslint-disable-line react-hooks/exhaustive-deps

  const overlap = result ? Math.round(result.overlap_pct) : 0
  const similarity = result ? (result.similarity_score * 100).toFixed(0) : '—'

  const profileA = result?.role_profiles?.[compareRoles?.[0]]
  const profileB = result?.role_profiles?.[compareRoles?.[1]]
  const shared = result?.shared_skills ?? []

  return (
    <div className="p-3 sm:p-5 lg:p-7 max-w-7xl mx-auto">
      <div className="mb-5 sm:mb-6">
        <h1 className="font-display text-2xl sm:text-3xl tracking-widest text-gradient-amber mb-1">COMPARE</h1>
        <p className="font-mono text-xs text-ink-400">Role-to-role skill overlap analysis</p>
      </div>

      {/* Role selectors */}
      <div className="card p-5 mb-5">
        <div className="flex flex-col items-center sm:flex-row sm:items-end gap-0 sm:gap-3">
          <div className="w-full sm:flex-1">
            <label className="label-mono text-[9px] text-ink-400 block mb-1.5">ROLE A</label>
            <select
              value={roleA}
              onChange={(e) => setRoleA(e.target.value)}
              className="w-full"
              aria-label="Select role A"
            >
              <option value="">Select role…</option>
              {(roles ?? []).map((r) => (
                <option key={r.role_category} value={r.role_category} disabled={r.role_category === roleB}>
                  {toTitleCase(r.role_category)}
                </option>
              ))}
            </select>
          </div>

          {/* VS divider */}
          <div className="flex items-center justify-center w-full my-4 sm:w-10 sm:h-9 sm:my-0 sm:shrink-0">
            <span className="font-display text-xl text-ink-400 tracking-widest">VS</span>
          </div>

          <div className="w-full sm:flex-1">
            <label className="label-mono text-[9px] text-ink-400 block mb-1.5">ROLE B</label>
            <select
              value={roleB}
              onChange={(e) => setRoleB(e.target.value)}
              className="w-full"
              aria-label="Select role B"
            >
              <option value="">Select role…</option>
              {(roles ?? []).map((r) => (
                <option key={r.role_category} value={r.role_category} disabled={r.role_category === roleA}>
                  {toTitleCase(r.role_category)}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={handleCompare}
            disabled={!canCompare}
            className={`btn-primary w-full justify-center mt-4 sm:mt-0 sm:w-auto sm:shrink-0 sm:h-9 ${!canCompare ? 'opacity-40 cursor-not-allowed' : ''}`}
          >
            Analyze
          </button>
        </div>
      </div>

      {/* Results */}
      {loading && <SkeletonChart height={400} />}
      {error && !loading && (
        <div className="card overflow-hidden">
          <ErrorState error={error} onRetry={refetch} className="h-64" />
        </div>
      )}

      {result && !loading && (
        <div className="animate-fade-in">
          {/* Score strip */}
          <div className="grid grid-cols-2 gap-3 mb-5">
            <div className="card p-3 sm:p-5 text-center border-glow-amber">
              <div className="label-mono text-[9px] text-ink-400 mb-2">SKILL OVERLAP</div>
              <div className="font-display text-3xl sm:text-5xl text-amber-glow glow-amber">{overlap}%</div>
              <div className="font-mono text-[10px] text-ink-400 mt-1">Jaccard similarity</div>
            </div>
            <div className="card p-3 sm:p-5 text-center">
              <div className="label-mono text-[9px] text-ink-400 mb-2">COSINE SIMILARITY</div>
              <div className="font-display text-3xl sm:text-5xl text-teal-signal">{similarity}%</div>
              <div className="font-mono text-[10px] text-ink-400 mt-1">vector similarity</div>
            </div>
          </div>

          {/* Venn + shared skills */}
          <div className="card p-5 mb-5">
            <h2 className="font-display text-base tracking-widest text-ink-100 mb-1">OVERLAP VISUALISATION</h2>
            <p className="font-mono text-[10px] text-ink-400 mb-4">{shared.length} shared skills</p>

            <div className="flex flex-col lg:flex-row items-center gap-6">
              <VennOverlap pct={overlap} />

              <div className="flex-1 flex flex-wrap gap-1">
                {shared.length === 0 ? (
                  <span className="text-ink-400 font-mono text-xs">No shared skills found</span>
                ) : (
                  shared.map((s) => <SkillTag key={s} skill={s} highlight />)
                )}
              </div>
            </div>
          </div>

          {/* Split panel */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* Role A */}
            <div className="card overflow-hidden">
              <div
                className="px-5 py-4 border-b"
                style={{ borderColor: 'rgba(129,140,248,0.3)', background: 'rgba(129,140,248,0.05)' }}
              >
                <div className="label-mono text-[9px] text-indigo-400 mb-0.5">ROLE A</div>
                <h3 className="font-display text-lg tracking-widest text-indigo-300">
                  {compareRoles?.[0]?.toUpperCase()}
                </h3>
              </div>
              <div className="p-5">
                <div className="mb-4">
                  <div className="label-mono text-[9px] text-ink-400 mb-2">UNIQUE SKILLS</div>
                  <div className="flex flex-wrap">
                    {profileA?.unique_skills?.length === 0 && (
                      <span className="text-ink-400 font-mono text-xs">None unique</span>
                    )}
                    {profileA?.unique_skills?.map((s) => (
                      <SkillTag key={s} skill={s} />
                    ))}
                  </div>
                </div>
                <div>
                  <div className="label-mono text-[9px] text-ink-400 mb-2">TOP SKILLS</div>
                  <div className="flex flex-wrap">
                    {profileA?.top_skills?.map((s) => (
                      <SkillTag key={s} skill={s} highlight={shared.includes(s)} />
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Role B */}
            <div className="card overflow-hidden">
              <div
                className="px-5 py-4 border-b"
                style={{ borderColor: 'rgba(245,166,35,0.3)', background: 'rgba(245,166,35,0.05)' }}
              >
                <div className="label-mono text-[9px] text-amber-dim mb-0.5">ROLE B</div>
                <h3 className="font-display text-lg tracking-widest text-amber-glow">
                  {compareRoles?.[1]?.toUpperCase()}
                </h3>
              </div>
              <div className="p-5">
                <div className="mb-4">
                  <div className="label-mono text-[9px] text-ink-400 mb-2">UNIQUE SKILLS</div>
                  <div className="flex flex-wrap">
                    {profileB?.unique_skills?.length === 0 && (
                      <span className="text-ink-400 font-mono text-xs">None unique</span>
                    )}
                    {profileB?.unique_skills?.map((s) => (
                      <SkillTag key={s} skill={s} />
                    ))}
                  </div>
                </div>
                <div>
                  <div className="label-mono text-[9px] text-ink-400 mb-2">TOP SKILLS</div>
                  <div className="flex flex-wrap">
                    {profileB?.top_skills?.map((s) => (
                      <SkillTag key={s} skill={s} highlight={shared.includes(s)} />
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {!result && !loading && !error && (
        <div className="card">
          <EmptyState
            icon="⚖️"
            title="SELECT TWO ROLES"
            message="Choose two roles above and click Analyze to compare their skill profiles side by side."
            className="h-64"
          />
        </div>
      )}
    </div>
  )
}
