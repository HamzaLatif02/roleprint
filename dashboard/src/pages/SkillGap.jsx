import { useState, useCallback, useRef, useEffect } from 'react'
import { useApi } from '../hooks/useApi'
import { api } from '../api/client'
import { ErrorState } from '../components/ErrorState'
import { ExportButton } from '../components/ExportButton'
import { EmptyState } from '../components/EmptyState'
import { toTitleCase } from '../utils'

const LS_KEY = 'roleprint:skill-gap:skills'
const LS_ROLE_KEY = 'roleprint:skill-gap:role'
const PLACEHOLDER_SKILLS = ['Python', 'SQL', 'Excel']

// ── Score ring ────────────────────────────────────────────────────────────────

function ScoreRing({ score }) {
  const size = 140
  const stroke = 10
  const r = (size - stroke) / 2
  const circ = 2 * Math.PI * r
  const offset = circ - (score / 100) * circ

  const color =
    score >= 75 ? '#4ade80'
    : score >= 40 ? '#f5a623'
    : '#fb7185'

  const label =
    score >= 75 ? 'Strong match'
    : score >= 40 ? 'Partial match'
    : 'Needs work'

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90" style={{ display: 'block' }}>
          {/* Track */}
          <circle
            cx={size / 2} cy={size / 2} r={r}
            fill="none"
            stroke="currentColor"
            strokeWidth={stroke}
            className="text-void-600"
          />
          {/* Progress */}
          <circle
            cx={size / 2} cy={size / 2} r={r}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circ}
            strokeDashoffset={offset}
            style={{
              transition: 'stroke-dashoffset 0.8s cubic-bezier(0.4,0,0.2,1)',
              filter: `drop-shadow(0 0 6px ${color}80)`,
            }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="font-display text-4xl leading-none"
            style={{ color }}
          >
            {score.toFixed(0)}%
          </span>
          <span className="label-mono text-[9px] text-ink-400 mt-1">match</span>
        </div>
      </div>
      <span
        className="mt-2 label-mono text-[10px] font-semibold"
        style={{ color }}
      >
        {label}
      </span>
    </div>
  )
}

// ── Skill list column ─────────────────────────────────────────────────────────

function SkillColumn({ title, count, skills, accentColor, dimmed = false }) {
  return (
    <div className={`card overflow-hidden ${dimmed ? 'opacity-75' : ''}`}>
      <div
        className="px-4 py-3 border-b border-border flex items-center justify-between"
        style={{ background: `${accentColor}0a` }}
      >
        <div>
          <h3
            className="font-display text-sm tracking-widest"
            style={{ color: accentColor }}
          >
            {title}
          </h3>
        </div>
        <span
          className="label-mono text-[9px] px-2 py-0.5 rounded-full border"
          style={{ color: accentColor, borderColor: `${accentColor}40`, background: `${accentColor}12` }}
        >
          {count}
        </span>
      </div>
      <div className="p-3 space-y-1.5 max-h-80 overflow-y-auto">
        {skills.length === 0 ? (
          <p className="text-ink-500 font-mono text-xs py-4 text-center">None</p>
        ) : (
          skills.map((item) => (
            <div
              key={item.skill}
              className="skill-item-row flex items-center justify-between px-3 py-2 rounded-lg transition-colors"
              style={{ background: `${accentColor}08` }}
            >
              <span className={`text-sm font-medium ${dimmed ? 'text-ink-400' : 'text-ink-100'}`}>
                {item.skill}
              </span>
              <span
                className="label-mono text-[9px] px-1.5 py-0.5 rounded border ml-2 shrink-0"
                style={{
                  color: accentColor,
                  borderColor: `${accentColor}30`,
                  background: `${accentColor}10`,
                }}
              >
                {item.pct.toFixed(1)}%
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

// ── Skill chip ────────────────────────────────────────────────────────────────

function SkillChip({ skill, onRemove }) {
  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-mono bg-void-600 border border-border text-ink-200 group hover:border-amber-dim transition-colors">
      {skill}
      <button
        onClick={() => onRemove(skill)}
        className="text-ink-500 hover:text-amber-glow transition-colors leading-none ml-0.5"
        aria-label={`Remove ${skill}`}
      >
        ×
      </button>
    </span>
  )
}

// ── Skeleton for results ──────────────────────────────────────────────────────

function ResultsSkeleton() {
  return (
    <div className="animate-pulse space-y-5 mt-6">
      <div className="card p-6 flex flex-col items-center gap-3">
        <div className="skeleton w-36 h-36 rounded-full" />
        <div className="skeleton h-4 w-48 rounded" />
        <div className="skeleton h-3 w-64 rounded" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[0, 1, 2].map((i) => (
          <div key={i} className="card p-4 space-y-2">
            <div className="skeleton h-5 w-32 rounded" />
            {Array.from({ length: 5 }, (_, j) => (
              <div key={j} className="skeleton h-8 rounded-lg" />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function SkillGap() {
  useEffect(() => { document.title = 'Skill Gap — Roleprint' }, [])
  const inputRef = useRef(null)

  // Persist role selection
  const [selectedRole, setSelectedRole] = useState(
    () => localStorage.getItem(LS_ROLE_KEY) ?? ''
  )
  // Persist skill list
  const [skills, setSkills] = useState(() => {
    try {
      const stored = localStorage.getItem(LS_KEY)
      return stored ? JSON.parse(stored) : PLACEHOLDER_SKILLS
    } catch {
      return PLACEHOLDER_SKILLS
    }
  })
  const [inputValue, setInputValue] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('missing')

  // Persist on change
  useEffect(() => {
    localStorage.setItem(LS_KEY, JSON.stringify(skills))
  }, [skills])
  useEffect(() => {
    localStorage.setItem(LS_ROLE_KEY, selectedRole)
  }, [selectedRole])

  const fetchRoles = useCallback(() => api.roles(), [])
  const { data: roles } = useApi(fetchRoles)

  const addSkill = () => {
    const val = inputValue.trim()
    if (!val) return
    if (skills.some((s) => s.toLowerCase() === val.toLowerCase())) {
      setInputValue('')
      return
    }
    setSkills((prev) => [...prev, val])
    setInputValue('')
    inputRef.current?.focus()
  }

  const removeSkill = (skill) => {
    setSkills((prev) => prev.filter((s) => s !== skill))
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      addSkill()
    }
  }

  const handleAnalyse = async () => {
    if (!selectedRole || skills.length === 0) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await api.skillGap(selectedRole, skills)
      setResult(data)
      setActiveTab('missing')
    } catch (err) {
      setError({
        type: err.type ?? (!navigator.onLine ? 'offline' : err.name === 'AbortError' ? 'timeout' : 'unknown'),
        message: err.message ?? 'Unknown error',
        statusCode: err.statusCode ?? null,
        url: err.url ?? '/api/skills/gap',
        timestamp: new Date(),
      })
    } finally {
      setLoading(false)
    }
  }

  const canAnalyse = selectedRole && skills.length > 0 && !loading

  const scoreColor =
    result?.match_score >= 75 ? '#4ade80'
    : result?.match_score >= 40 ? '#f5a623'
    : '#fb7185'

  return (
    <div className="p-3 sm:p-5 lg:p-7 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-5 sm:mb-6">
        <h1 className="font-display text-2xl sm:text-3xl tracking-widest text-gradient-amber mb-1">SKILL GAP</h1>
        <p className="font-mono text-xs text-ink-400">
          Compare your skills against real job posting data
        </p>
      </div>

      {/* Input panel */}
      <div className="card p-5 mb-5">
        {/* Role selector */}
        <div className="mb-4">
          <label className="label-mono text-[9px] text-ink-500 block mb-1.5">TARGET ROLE</label>
          <select
            value={selectedRole}
            onChange={(e) => setSelectedRole(e.target.value)}
            className="w-full sm:w-64"
            aria-label="Select target role"
          >
            <option value="">Select a role…</option>
            {(roles ?? []).map((r) => (
              <option key={r.role_category} value={r.role_category}>
                {toTitleCase(r.role_category)}
              </option>
            ))}
          </select>
        </div>

        {/* Skill input */}
        <div className="mb-3">
          <label className="label-mono text-[9px] text-ink-500 block mb-1.5">YOUR SKILLS</label>
          <div className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="e.g. Python, dbt, Tableau…"
              className="flex-1 px-3 py-2 rounded-lg bg-void-700 border border-border text-ink-100 text-sm font-mono placeholder-ink-500 focus:outline-none focus:border-amber-dim transition-colors"
              aria-label="Add a skill"
            />
            <button
              onClick={addSkill}
              disabled={!inputValue.trim()}
              className="btn-primary disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
            >
              Add
            </button>
          </div>
          <p className="font-mono text-[10px] text-ink-500 mt-1.5">Press Enter or click Add</p>
        </div>

        {/* Skill chips */}
        {skills.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-4 p-3 rounded-lg bg-void-700 border border-border min-h-[44px]">
            {skills.map((skill) => (
              <SkillChip key={skill} skill={skill} onRemove={removeSkill} />
            ))}
          </div>
        )}

        {skills.length === 0 && (
          <div className="mb-4 p-3 rounded-lg bg-void-700 border border-border text-ink-500 font-mono text-xs text-center">
            Add at least one skill above
          </div>
        )}

        {/* Analyse button */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          <button
            onClick={handleAnalyse}
            disabled={!canAnalyse}
            className={`btn-primary w-full sm:w-auto justify-center ${!canAnalyse ? 'opacity-40 cursor-not-allowed' : ''}`}
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                Analysing…
              </span>
            ) : (
              'Analyse Gap'
            )}
          </button>
          {result && !loading && (
            <span className="label-mono text-[9px] text-ink-500">
              Based on {result.total_postings_analysed.toLocaleString()} postings
            </span>
          )}
        </div>
      </div>

      {/* Error */}
      {error && !loading && (
        <ErrorState error={error} onRetry={handleAnalyse} className="h-48" />
      )}

      {/* Loading skeleton */}
      {loading && <ResultsSkeleton />}

      {/* Results */}
      {result && !loading && (
        <div className="animate-fade-in space-y-5">
          {/* Match score card */}
          <div className="card p-6">
            <div className="flex flex-col md:flex-row items-center gap-6">
              <ScoreRing score={result.match_score} />

              <div className="flex-1 text-center md:text-left">
                <p className="font-display text-xl tracking-widest text-ink-100 mb-1">
                  {result.matched_skills.length} of {result.matched_skills.length + result.missing_skills.length} TOP SKILLS MATCHED
                </p>
                <p className="font-mono text-xs text-ink-400 mb-4">
                  for <span className="text-ink-200">{toTitleCase(result.role_category)}</span>
                  {' '}· top 30 in-demand skills · latest week
                </p>

                {/* Mini progress bar */}
                <div className="w-full max-w-sm mx-auto md:mx-0">
                  <div className="h-2 rounded-full bg-void-600 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-1000"
                      style={{
                        width: `${result.match_score}%`,
                        background: scoreColor,
                        boxShadow: `0 0 8px ${scoreColor}60`,
                      }}
                    />
                  </div>
                  <div className="flex justify-between mt-1">
                    <span className="label-mono text-[9px] text-ink-500">0%</span>
                    <span className="label-mono text-[9px] text-ink-500">100%</span>
                  </div>
                </div>
              </div>

              {/* Quick stat pills */}
              <div className="flex md:flex-col gap-2 shrink-0">
                <div className="text-center px-4 py-2 rounded-lg bg-green-50 dark:bg-void-700 border border-green-200/60 dark:border-border">
                  <div className="font-display text-2xl text-green-600 dark:text-green-400">{result.matched_skills.length}</div>
                  <div className="label-mono text-[9px] text-green-700/70 dark:text-ink-500">matched</div>
                </div>
                <div className="text-center px-4 py-2 rounded-lg bg-red-50 dark:bg-void-700 border border-red-200/60 dark:border-border">
                  <div className="font-display text-2xl text-red-600 dark:text-rose-400">{result.missing_skills.length}</div>
                  <div className="label-mono text-[9px] text-red-700/70 dark:text-ink-500">missing</div>
                </div>
                <div className="text-center px-4 py-2 rounded-lg bg-gray-100 dark:bg-void-700 border border-gray-200/60 dark:border-border">
                  <div className="font-display text-2xl text-gray-500 dark:text-ink-300">{result.bonus_skills.length}</div>
                  <div className="label-mono text-[9px] text-gray-500/70 dark:text-ink-500">bonus</div>
                </div>
              </div>
            </div>
          </div>

          {/* No data state */}
          {result.matched_skills.length === 0 && result.missing_skills.length === 0 && (
            <div className="card">
              <EmptyState
                icon="📭"
                title="NO ROLE DATA"
                message="No skill data available for this role yet — check back after the next scrape run."
                className="h-48"
              />
            </div>
          )}

          {/* Three-column breakdown */}
          {(result.matched_skills.length > 0 || result.missing_skills.length > 0) && (
            <>
              {/* Mobile tab switcher */}
              <div className="flex md:hidden border border-border rounded-lg overflow-hidden">
                {[
                  { id: 'matched', label: `Have (${result.matched_skills.length})`, color: '#4ade80' },
                  { id: 'missing', label: `Learn (${result.missing_skills.length})`, color: '#fb7185' },
                  { id: 'bonus',   label: `Bonus (${result.bonus_skills.length})`,   color: '#94a3b8' },
                ].map((tab, i) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`flex-1 py-2.5 font-mono text-[10px] transition-colors border-r last:border-r-0 border-border ${
                      activeTab === tab.id ? 'bg-void-700' : 'bg-void-800 text-ink-400 hover:text-ink-200'
                    }`}
                    style={activeTab === tab.id ? { color: tab.color } : {}}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Mobile: show active tab only */}
              <div className="md:hidden">
                {activeTab === 'matched' && (
                  <SkillColumn title="✓ SKILLS YOU HAVE" count={`${result.matched_skills.length} matched`} skills={result.matched_skills} accentColor="#4ade80" />
                )}
                {activeTab === 'missing' && (
                  <SkillColumn title="✗ SKILLS TO LEARN" count={`${result.missing_skills.length} missing`} skills={result.missing_skills} accentColor="#fb7185" />
                )}
                {activeTab === 'bonus' && (
                  <SkillColumn title="~ BONUS SKILLS" count={`${result.bonus_skills.length} bonus`} skills={result.bonus_skills} accentColor="#94a3b8" dimmed />
                )}
              </div>

              {/* Desktop: all 3 columns side by side */}
              <div className="hidden md:grid md:grid-cols-3 gap-4">
                <SkillColumn title="✓ SKILLS YOU HAVE" count={`${result.matched_skills.length} matched`} skills={result.matched_skills} accentColor="#4ade80" />
                <SkillColumn title="✗ SKILLS TO LEARN" count={`${result.missing_skills.length} missing`} skills={result.missing_skills} accentColor="#fb7185" />
                <SkillColumn title="~ BONUS SKILLS"    count={`${result.bonus_skills.length} bonus`}   skills={result.bonus_skills}   accentColor="#94a3b8" dimmed />
              </div>

              <div className="flex justify-end pt-1">
                <ExportButton
                  href={`/api/export/skills/gap?role_category=${encodeURIComponent(result.role_category)}&user_skills=${encodeURIComponent(skills.join(','))}`}
                  label="Export Results"
                />
              </div>
            </>
          )}
        </div>
      )}

      {/* Empty state before first analysis */}
      {!result && !loading && !error && (
        <div className="card border-dashed">
          <EmptyState
            icon="🎯"
            title="READY TO ANALYSE"
            message="Select a target role, add the skills you already have, then click Analyse Gap to see what you're missing."
            className="h-56"
          />
        </div>
      )}
    </div>
  )
}
