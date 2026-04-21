import { useCallback } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  BarChart, Bar, Cell,
} from 'recharts'
import { useApi } from '../hooks/useApi'
import { api } from '../api/client'
import { useApp } from '../context/AppContext'
import { SkeletonChart, SkeletonRow } from '../components/Skeleton'
import { ErrorState, ErrorStateRow } from '../components/ErrorState'
import { ExportButton } from '../components/ExportButton'
import { EmptyState, EmptyStateRow } from '../components/EmptyState'

const PALETTE = ['#f5a623', '#2dd4bf', '#818cf8', '#fb7185', '#4ade80']

function useChartColors() {
  const isDark = document.documentElement.classList.contains('dark')
  return {
    axis: isDark ? '#565878' : '#4b5563',
    grid: isDark ? '#1e2238' : '#e2e5f0',
  }
}

function TrendTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="custom-tooltip min-w-[160px]">
      <div className="label-mono text-[9px] mb-2 text-ink-400">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-3 mb-0.5">
          <span className="text-xs text-ink-200 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full inline-block" style={{ background: p.color }} />
            {p.dataKey}
          </span>
          <span className="font-mono text-xs font-bold" style={{ color: p.color }}>
            {p.value}
          </span>
        </div>
      ))}
    </div>
  )
}

function SparklineCard({ item, color }) {
  const wow = item.wow_change
  const sign = wow > 0 ? '+' : ''
  const prev = item.mention_count / (1 + (wow || 0) / 100)
  const sparkData = [
    { v: Math.round(prev) },
    { v: item.mention_count },
  ]

  return (
    <div className="card card-hover p-4 group relative overflow-hidden">
      {/* Accent line */}
      <div
        className="absolute top-0 left-0 right-0 h-0.5 opacity-50"
        style={{ background: `linear-gradient(90deg, transparent, ${color}, transparent)` }}
      />

      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="font-medium text-ink-100 group-hover:text-amber-glow transition-colors text-sm leading-tight">
            {item.skill}
          </div>
          <div className="font-mono text-[10px] text-ink-400 mt-0.5">{item.role_category}</div>
        </div>
        <span className={wow >= 0 ? 'badge-rising' : 'badge-falling'}>
          {sign}{wow.toFixed(0)}%
        </span>
      </div>

      <div className="flex items-end justify-between gap-2">
        <div>
          <div className="font-display text-2xl" style={{ color }}>
            {item.mention_count}
          </div>
          <div className="label-mono text-[9px] text-ink-400">mentions</div>
        </div>
        {/* Micro sparkline */}
        <div style={{ width: 60, height: 32 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={sparkData}>
              <Line
                type="monotone"
                dataKey="v"
                stroke={color}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="mt-2 h-1 rounded-full overflow-hidden bg-void-600">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{
            width: `${Math.min(100, item.pct_of_postings * 100)}%`,
            background: color,
            opacity: 0.7,
          }}
        />
      </div>
      <div className="label-mono text-[9px] text-ink-400 mt-1">
        {(item.pct_of_postings * 100).toFixed(1)}% of postings
      </div>
    </div>
  )
}

export default function Trends() {
  const { roleFilter } = useApp()
  const { axis, grid } = useChartColors()

  const fetchTrending = useCallback(() => api.trending(roleFilter, 8), [roleFilter])
  const { data: trending, loading: trendingLoading, error: trendingError, refetch: refetchTrending } = useApi(fetchTrending, [roleFilter])

  const fetchEmerging = useCallback(() => api.emerging(6), [])
  const { data: emerging, loading: emergingLoading, error: emergingError, refetch: refetchEmerging } = useApi(fetchEmerging)

  // Top 5 rising skills for cards
  const risingSkills = (trending ?? [])
    .filter((t) => t.is_rising)
    .slice(0, 5)
    .map((t, i) => ({ ...t, color: PALETTE[i] }))

  // Build a simple 2-point "trend" chart from current + estimated prev
  const top5Skills = (trending ?? []).slice(0, 5)
  const chartData = top5Skills.length > 0
    ? [
        {
          week: 'Previous',
          ...Object.fromEntries(
            top5Skills.map((s) => [
              s.skill,
              Math.max(0, Math.round(s.mention_count / (1 + (s.wow_change || 0) / 100))),
            ])
          ),
        },
        {
          week: 'Current',
          ...Object.fromEntries(top5Skills.map((s) => [s.skill, s.mention_count])),
        },
      ]
    : []

  return (
    <div className="p-5 lg:p-7 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="font-display text-3xl tracking-widest text-gradient-amber mb-1">TRENDS</h1>
        <p className="font-mono text-xs text-ink-400">
          Skill momentum{roleFilter ? ` · ${roleFilter}` : ' · all roles'}
        </p>
      </div>

      {/* Top 5 trend chart */}
      <div className="card p-5 mb-5">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="font-display text-base tracking-widest text-ink-100">SKILL MOMENTUM</h2>
            <p className="font-mono text-[10px] text-ink-400 mt-0.5">
              top 5 skills · previous vs current week
            </p>
          </div>
          <ExportButton
            href={trending?.length ? `/api/export/skills/trending${roleFilter ? `?role_category=${encodeURIComponent(roleFilter)}&weeks=8` : '?weeks=8'}` : null}
          />
        </div>

        {trendingLoading ? (
          <div className="skeleton h-60 w-full rounded-lg" />
        ) : trendingError ? (
          <ErrorState error={trendingError} onRetry={refetchTrending} className="h-60" />
        ) : chartData.length === 0 ? (
          <EmptyState
            icon="📈"
            title="NO TREND DATA"
            message="Not enough data to show skill momentum yet. Check back after more postings are scraped."
            className="h-60"
          />
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={chartData} margin={{ top: 4, right: 16, bottom: 0, left: -10 }}>
              <CartesianGrid stroke={grid} />
              <XAxis
                dataKey="week"
                tick={{ fill: axis, fontSize: 11 }}
                axisLine={{ stroke: grid }}
                tickLine={{ stroke: grid }}
              />
              <YAxis
                tick={{ fill: axis, fontSize: 11 }}
                axisLine={{ stroke: grid }}
                tickLine={{ stroke: grid }}
              />
              <Tooltip content={<TrendTooltip />} />
              <Legend />
              {top5Skills.map((s, i) => (
                <Line
                  key={s.skill}
                  type="monotone"
                  dataKey={s.skill}
                  stroke={PALETTE[i]}
                  strokeWidth={2}
                  dot={{ fill: PALETTE[i], r: 4, strokeWidth: 0 }}
                  activeDot={{ r: 6, strokeWidth: 0 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Rising skill cards */}
      <div className="mb-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-display text-base tracking-widest text-ink-100">RISING SKILLS</h2>
          <span className="label-mono text-[9px] text-ink-400">WoW &gt;20% growth</span>
        </div>

        {trendingLoading ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {Array.from({ length: 5 }, (_, i) => (
              <div key={i} className="card p-4 space-y-3">
                <div className="skeleton h-4 w-20 rounded" />
                <div className="skeleton h-8 w-12 rounded" />
                <div className="skeleton h-2 w-full rounded-full" />
              </div>
            ))}
          </div>
        ) : trendingError ? (
          <div className="card">
            <ErrorState error={trendingError} onRetry={refetchTrending} className="h-36" />
          </div>
        ) : risingSkills.length === 0 ? (
          <div className="card">
            <EmptyState
              icon="🚀"
              title="NONE RISING"
              message="No skills with >20% week-over-week growth detected this week."
              className="h-36"
            />
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {risingSkills.map((item) => (
              <SparklineCard key={`${item.skill}:${item.role_category}`} item={item} color={item.color} />
            ))}
          </div>
        )}
      </div>

      {/* Emerging skills table */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-border flex items-center justify-between">
          <div>
            <h2 className="font-display text-base tracking-widest text-ink-100">EMERGING SKILLS</h2>
            <p className="font-mono text-[10px] text-ink-400 mt-0.5">newly prominent · last 6 weeks</p>
          </div>
          <span className="label-mono text-[9px] text-ink-400">
            {emerging?.length ?? '—'} detected
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-void-700">
                <th className="text-left px-5 py-3 label-mono text-[9px] font-normal text-ink-400">SKILL</th>
                <th className="text-left px-4 py-3 label-mono text-[9px] font-normal text-ink-400">ROLE</th>
                <th className="text-right px-4 py-3 label-mono text-[9px] font-normal text-ink-400">GROWTH</th>
                <th className="text-right px-4 py-3 label-mono text-[9px] font-normal text-ink-400">NOW</th>
                <th className="text-right px-4 py-3 label-mono text-[9px] font-normal text-ink-400">BEFORE</th>
                <th className="text-right px-5 py-3 label-mono text-[9px] font-normal text-ink-400">WEEK</th>
              </tr>
            </thead>
            <tbody>
              {emergingLoading ? (
                Array.from({ length: 6 }, (_, i) => (
                  <tr key={i} className="border-b border-border">
                    {Array.from({ length: 6 }, (_, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="skeleton h-3 rounded" style={{ width: j === 0 ? '80px' : '48px' }} />
                      </td>
                    ))}
                  </tr>
                ))
              ) : emergingError ? (
                <ErrorStateRow colSpan={6} error={emergingError} onRetry={refetchEmerging} />
              ) : (emerging ?? []).length === 0 ? (
                <EmptyStateRow
                  colSpan={6}
                  icon="🌱"
                  title="NOTHING EMERGING"
                  message="No newly prominent skills detected in the last 6 weeks."
                />
              ) : (
                (emerging ?? []).map((row, i) => (
                  <tr
                    key={`${row.skill}:${row.role_category}:${i}`}
                    className="border-b border-border odd:bg-void-800 even:bg-void-900 hover:bg-void-700 transition-colors group"
                    style={{ animationDelay: `${i * 40}ms` }}
                  >
                    <td className="px-5 py-3 font-medium text-ink-100 group-hover:text-teal-signal transition-colors">
                      {row.skill}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-ink-400">{row.role_category}</td>
                    <td className="px-4 py-3 text-right">
                      <span className="badge-rising">+{row.growth_pct?.toFixed(0) ?? '—'}%</span>
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-xs text-teal-signal">{row.current_count}</td>
                    <td className="px-4 py-3 text-right font-mono text-xs text-ink-400">{row.old_count}</td>
                    <td className="px-5 py-3 text-right font-mono text-xs text-ink-400">{row.current_week}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
