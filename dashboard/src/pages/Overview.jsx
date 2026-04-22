import { useCallback, useState, useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { useApi } from '../hooks/useApi'
import { api } from '../api/client'
import { useApp } from '../context/AppContext'
import { useWindowWidth } from '../hooks/useWindowWidth'
import { SkeletonStat, SkeletonChart } from '../components/Skeleton'
import { ErrorState, ErrorStateRow } from '../components/ErrorState'
import { ExportButton } from '../components/ExportButton'
import { EmptyState, EmptyStateRow } from '../components/EmptyState'
import { getRelativeTime } from '../utils'

function useChartColors() {
  const isDark = document.documentElement.classList.contains('dark')
  return {
    axis: isDark ? '#565878' : '#374151',
    grid: isDark ? '#1e2238' : '#e5e7eb',
  }
}

const AMBER = '#f5a623'
const TEAL = '#2dd4bf'

// ── Pagination ────────────────────────────────────────────────────────────────

function buildPageList(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const pages = [1]
  const start = Math.max(2, current - 2)
  const end = Math.min(total - 1, current + 2)
  if (start > 2) pages.push(null)
  for (let i = start; i <= end; i++) pages.push(i)
  if (end < total - 1) pages.push(null)
  pages.push(total)
  return pages
}

function SkillsPaginationBar({ page, totalPages, totalCount, pageSize, onPage, onPageSize, loading }) {
  const start = totalCount === 0 ? 0 : (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, totalCount)
  const pageList = buildPageList(page, totalPages)

  const btnBase =
    'min-w-[28px] h-7 flex items-center justify-center rounded-lg font-mono text-xs ' +
    'border transition-all duration-100 disabled:opacity-40 disabled:cursor-not-allowed'
  const btnInactive = btnBase + ' border-border text-ink-400 hover:border-border-bright hover:text-ink-200 bg-transparent'
  const btnActive   = btnBase + ' border-amber-300/60 dark:border-amber-dim bg-amber-100 dark:bg-amber-muted text-amber-700 dark:text-amber-glow'
  const btnEllipsis = btnBase + ' border-transparent text-ink-500 cursor-default'

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-3 sm:px-5 py-3 border-t border-border">
      {/* Count + page size */}
      <div className="flex items-center gap-3 shrink-0">
        <span className="font-mono text-[10px] text-ink-400">
          {totalCount === 0
            ? 'No skills'
            : `Showing ${start.toLocaleString()}–${end.toLocaleString()} of ${totalCount.toLocaleString()} skills`}
        </span>
        <select
          value={pageSize}
          onChange={(e) => onPageSize(Number(e.target.value))}
          className="text-xs py-1 px-2 h-7"
          aria-label="Skills per page"
        >
          {[10, 15, 25].map((n) => (
            <option key={n} value={n}>{n} / page</option>
          ))}
        </select>
      </div>

      {/* Page buttons — desktop */}
      <div className="hidden sm:flex items-center gap-1">
        <button
          onClick={() => onPage(page - 1)}
          disabled={page <= 1 || loading}
          className={btnInactive + ' px-2'}
          aria-label="Previous page"
        >
          ‹
        </button>
        {pageList.map((p, i) =>
          p === null ? (
            <span key={`e${i}`} className={btnEllipsis + ' px-1'}>…</span>
          ) : (
            <button
              key={p}
              onClick={() => p !== page && onPage(p)}
              disabled={loading}
              className={p === page ? btnActive + ' px-2' : btnInactive + ' px-2'}
              aria-current={p === page ? 'page' : undefined}
            >
              {p}
            </button>
          )
        )}
        <button
          onClick={() => onPage(page + 1)}
          disabled={page >= totalPages || loading}
          className={btnInactive + ' px-2'}
          aria-label="Next page"
        >
          ›
        </button>
      </div>

      {/* Simplified nav — mobile */}
      <div className="flex sm:hidden items-center gap-2">
        <button
          onClick={() => onPage(page - 1)}
          disabled={page <= 1 || loading}
          className={btnInactive + ' px-3'}
          aria-label="Previous page"
        >
          ‹
        </button>
        <span className="font-mono text-xs text-ink-400 whitespace-nowrap">
          Page {page} of {totalPages}
        </span>
        <button
          onClick={() => onPage(page + 1)}
          disabled={page >= totalPages || loading}
          className={btnInactive + ' px-3'}
          aria-label="Next page"
        >
          ›
        </button>
      </div>
    </div>
  )
}

function StatBar({ data, loading, error, refetch }) {
  const stats = [
    {
      label: 'Total Postings',
      value: data?.total_postings,
      sub: `${data?.processed_postings ?? '—'} processed`,
      color: AMBER,
    },
    {
      label: 'Roles Tracked',
      value: data?.roles_tracked,
      sub: 'distinct categories',
      color: TEAL,
    },
    {
      label: 'Weeks of Data',
      value: data?.weeks_of_data,
      sub: 'historical depth',
      color: '#818cf8',
    },
    {
      label: 'Last Updated',
      value: getRelativeTime(data?.last_scraped) ?? '—',
      sub: data?.last_scraped
        ? new Date(data.last_scraped).toLocaleString('en-GB', {
            day: 'numeric', month: 'short', year: 'numeric',
            hour: '2-digit', minute: '2-digit', timeZoneName: 'short',
          })
        : '—',
      sub2: data?.sources?.join(' · ') ?? '—',
      color: '#fb7185',
      mono: true,
    },
  ]

  if (loading) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        {Array.from({ length: 4 }, (_, i) => <SkeletonStat key={i} />)}
      </div>
    )
  }
  if (error) {
    return (
      <div className="mb-6">
        <ErrorState error={error} onRetry={refetch} className="h-40" />
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
      {stats.map((s) => (
        <div
          key={s.label}
          className="card card-hover p-3 sm:p-5 group relative overflow-hidden"
          style={{ borderColor: `${s.color}20` }}
        >
          <div className="label-mono text-[9px] mb-1.5 sm:mb-2" style={{ color: `${s.color}99` }}>
            {s.label.toUpperCase()}
          </div>
          <div
            className={`leading-none mb-1 sm:mb-1.5 ${
              s.mono ? 'font-mono text-base sm:text-xl font-bold' : 'font-display text-2xl sm:text-4xl'
            }`}
            style={{ color: s.color, textShadow: `0 0 20px ${s.color}30` }}
          >
            {s.value ?? '—'}
          </div>
          <div className="font-mono text-[9px] sm:text-[10px] text-ink-400 truncate">{s.sub}</div>
          {s.sub2 && (
            <div className="font-mono text-[9px] text-ink-500 truncate mt-0.5 hidden sm:block">{s.sub2}</div>
          )}
          <div
            className="absolute bottom-0 left-0 right-0 h-0.5 rounded-b-xl opacity-0 group-hover:opacity-100 transition-opacity"
            style={{ background: `linear-gradient(90deg, transparent, ${s.color}60, transparent)` }}
          />
        </div>
      ))}
    </div>
  )
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="custom-tooltip">
      <div className="font-mono text-xs text-ink-400 mb-1">{label}</div>
      <div className="font-display text-xl" style={{ color: AMBER }}>
        {payload[0].value}
      </div>
      <div className="label-mono text-[9px] text-ink-400">mentions this week</div>
    </div>
  )
}

function SkillsChart({ data, loading, error, refetch, roleFilter }) {
  const { axis, grid } = useChartColors()
  const width = useWindowWidth()
  const isMobile = width < 640

  if (loading) return <SkeletonChart height={280} />
  if (error) return (
    <div className="card overflow-hidden">
      <ErrorState error={error} onRetry={refetch} className="h-72" />
    </div>
  )

  const allSkills = data ?? []
  // Show fewer bars on mobile so each bar is readable
  const chartData = allSkills.slice(0, isMobile ? 5 : 10)

  return (
    <div className="card p-3 sm:p-5 h-full flex flex-col">
      {/* Header */}
      <div className="mb-4 sm:mb-5 shrink-0">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h2 className="font-display text-base tracking-widest text-ink-100">TOP SKILLS</h2>
            <p className="font-mono text-[10px] text-ink-400 mt-0.5">current week · by mention count</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <div className="label-mono text-[9px] text-ink-400">
              {chartData.length} of {allSkills.length}
            </div>
            <ExportButton
              href={allSkills.length ? `/api/export/skills/trending${roleFilter ? `?role_category=${encodeURIComponent(roleFilter)}&weeks=4` : '?weeks=4'}` : null}
            />
          </div>
        </div>
        {/* Legend — below title on all screens */}
        <div className="flex items-center gap-3 mt-2">
          <div className="flex items-center gap-1.5 label-mono text-[9px] text-ink-400">
            <span className="w-2.5 h-2.5 rounded-sm inline-block" style={{ background: AMBER }} />
            skill
          </div>
          <div className="flex items-center gap-1.5 label-mono text-[9px] text-teal-signal">
            <span className="w-2.5 h-2.5 rounded-sm inline-block" style={{ background: TEAL }} />
            rising &gt;20% WoW
          </div>
        </div>
      </div>

      {chartData.length === 0 ? (
        <EmptyState
          icon="📊"
          title="NO SKILLS YET"
          message="No skill data available for this selection. Try clearing the role filter or check back after the next scrape run."
          className="h-60"
        />
      ) : (
        <div className="flex-1 min-h-[260px] sm:min-h-[300px] overflow-visible">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              margin={{ top: 4, right: 8, bottom: 60, left: -10 }}
              barCategoryGap="30%"
            >
              <CartesianGrid vertical={false} stroke={grid} />
              <XAxis
                dataKey="skill"
                tick={{
                  angle: -45,
                  textAnchor: 'end',
                  dy: 4,
                  fill: axis,
                  fontSize: isMobile ? 10 : 11,
                }}
                height={70}
                interval={0}
                axisLine={{ stroke: grid }}
                tickLine={{ stroke: grid }}
              />
              <YAxis
                tick={{ fill: axis, fontSize: isMobile ? 10 : 11 }}
                axisLine={{ stroke: grid }}
                tickLine={{ stroke: grid }}
                width={isMobile ? 28 : 40}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(245,166,35,0.04)' }} />
              <Bar dataKey="mention_count" radius={[3, 3, 0, 0]}>
                {chartData.map((entry) => (
                  <Cell
                    key={entry.skill}
                    fill={entry.is_rising ? TEAL : AMBER}
                    fillOpacity={0.85}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

function RisingPill({ item }) {
  const wow = item.wow_change
  const sign = wow > 0 ? '+' : ''
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-border last:border-0">
      <div className="flex items-center gap-2 min-w-0">
        <div className="w-1.5 h-1.5 rounded-full bg-teal-signal shrink-0" />
        <span className="text-sm text-ink-100 font-medium truncate">{item.skill}</span>
        <span className="label-mono text-[9px] text-ink-400 hidden sm:block shrink-0">{item.role_category}</span>
      </div>
      <div className="flex items-center gap-2 shrink-0 ml-2">
        <span className="font-mono text-xs text-ink-300 hidden sm:block">{item.mention_count}</span>
        <span className={wow >= 0 ? 'badge-rising' : 'badge-falling'}>
          {sign}{wow.toFixed(0)}%
        </span>
      </div>
    </div>
  )
}

export default function Overview() {
  const { roleFilter } = useApp()

  const fetchStats = useCallback(() => api.stats(roleFilter), [roleFilter])
  const { data: stats, loading: statsLoading, error: statsError, refetch: refetchStats } = useApi(fetchStats, [roleFilter])

  const fetchTrending = useCallback(() => api.trending(roleFilter, 4), [roleFilter])
  const { data: trending, loading: trendingLoading, error: trendingError, refetch: refetchTrending } = useApi(fetchTrending, [roleFilter])

  const rising = (trending ?? []).filter((t) => t.is_rising).slice(0, 8)

  // All Skills — paginated separately from the chart/rising data
  const [skillsPage, setSkillsPage] = useState(1)
  const [skillsPageSize, setSkillsPageSize] = useState(15)
  useEffect(() => { setSkillsPage(1) }, [roleFilter, skillsPageSize]) // eslint-disable-line

  const fetchSkillsPage = useCallback(
    () => api.trendingPaged(roleFilter, skillsPage, skillsPageSize),
    [roleFilter, skillsPage, skillsPageSize]
  )
  const { data: skillsData, loading: skillsLoading, error: skillsError, refetch: refetchSkillsPage } = useApi(fetchSkillsPage, [roleFilter, skillsPage, skillsPageSize])

  const pagedSkills = skillsData?.data ?? []
  const skillsTotal = skillsData?.total_count ?? 0
  const skillsTotalPages = skillsData?.total_pages ?? 1

  return (
    <div className="p-3 sm:p-5 lg:p-7 max-w-7xl mx-auto">
      {/* Page header */}
      <div className="mb-5 sm:mb-6">
        <h1 className="font-display text-2xl sm:text-3xl tracking-widest text-gradient-amber mb-1">OVERVIEW</h1>
        <p className="font-mono text-xs text-ink-400">
          Job market snapshot{roleFilter ? ` · ${roleFilter}` : ' · all roles'}
        </p>
      </div>

      {/* Stats */}
      <StatBar data={stats} loading={statsLoading} error={statsError} refetch={refetchStats} />

      {/* Global empty state */}
      {!statsLoading && !statsError && stats?.total_postings === 0 && (
        <EmptyState
          icon="🌅"
          title="WARMING UP"
          message="The database is empty — no postings have been scraped yet. Run the scraper to start collecting data."
          className="h-72"
        />
      )}

      {/* Charts row */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 sm:gap-5 xl:items-stretch">
        {/* Main bar chart */}
        <div className="xl:col-span-2 flex flex-col">
          <SkillsChart
            data={trending}
            loading={trendingLoading}
            error={trendingError}
            refetch={refetchTrending}
            roleFilter={roleFilter}
          />
        </div>

        {/* Rising skills panel */}
        <div className="card p-3 sm:p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="font-display text-base tracking-widest text-ink-100">RISING</h2>
              <p className="font-mono text-[10px] text-ink-400 mt-0.5">wow &gt; 20% growth</p>
            </div>
            <span className="badge-rising text-xs">↑ {rising.length}</span>
          </div>

          {trendingLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 6 }, (_, i) => (
                <div key={i} className="flex items-center justify-between py-2.5 border-b border-border">
                  <div className="w-28 h-3.5 skeleton rounded" />
                  <div className="w-12 h-5 skeleton rounded" />
                </div>
              ))}
            </div>
          ) : trendingError ? (
            <ErrorState error={trendingError} onRetry={refetchTrending} className="h-40" />
          ) : rising.length === 0 ? (
            <EmptyState
              icon="📈"
              title="NONE RISING"
              message="No skills detected with >20% week-over-week growth this week."
              className="h-40"
            />
          ) : (
            <div>
              {rising.map((item) => (
                <RisingPill key={`${item.skill}:${item.role_category}`} item={item} />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* All Skills table */}
      <div className="card mt-4 sm:mt-5 overflow-hidden">
        <div className="px-3 sm:px-5 py-4 border-b border-border flex items-center justify-between">
          <h2 className="font-display text-base tracking-widest text-ink-100">ALL SKILLS</h2>
          <span className="label-mono text-[9px] text-ink-400">
            {skillsLoading ? 'Loading…' : `${skillsTotal.toLocaleString()} skills tracked`}
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-void-700">
                <th className="text-left px-3 sm:px-5 py-3 label-mono text-[9px] font-normal text-ink-400">SKILL</th>
                <th className="text-left px-4 py-3 label-mono text-[9px] font-normal text-ink-400 hidden sm:table-cell">ROLE</th>
                <th className="text-right px-4 py-3 label-mono text-[9px] font-normal text-ink-400">MENTIONS</th>
                <th className="text-right px-4 py-3 label-mono text-[9px] font-normal text-ink-400 hidden sm:table-cell">PCT</th>
                <th className="text-right px-3 sm:px-5 py-3 label-mono text-[9px] font-normal text-ink-400">WoW</th>
              </tr>
            </thead>
            <tbody className={skillsLoading ? 'opacity-50 pointer-events-none' : ''}>
              {skillsLoading && pagedSkills.length === 0 ? (
                Array.from({ length: skillsPageSize }, (_, i) => (
                  <tr key={i} className="border-b border-border">
                    {Array.from({ length: 5 }, (_, j) => (
                      <td key={j} className={`px-4 py-3 ${j === 1 || j === 3 ? 'hidden sm:table-cell' : ''}`}>
                        <div className="skeleton h-3 rounded" style={{ width: j === 0 ? '80px' : j === 1 ? '100px' : '48px' }} />
                      </td>
                    ))}
                  </tr>
                ))
              ) : skillsError ? (
                <ErrorStateRow colSpan={5} error={skillsError} onRetry={refetchSkillsPage} />
              ) : pagedSkills.length === 0 ? (
                <EmptyStateRow
                  colSpan={5}
                  icon="🗂"
                  title="NO SKILLS TRACKED"
                  message={roleFilter
                    ? 'No skills found for this role. Try clearing the role filter.'
                    : 'No skills have been extracted yet. The pipeline needs to process some postings first.'}
                />
              ) : (
                pagedSkills.map((row) => {
                  const wow = row.wow_change
                  const sign = wow > 0 ? '+' : ''
                  return (
                    <tr
                      key={`${row.skill}:${row.role_category}`}
                      className="border-b border-border odd:bg-void-800 even:bg-void-900 hover:bg-void-700 transition-colors group"
                    >
                      <td className="px-3 sm:px-5 py-3 font-medium text-ink-100 group-hover:text-amber-glow transition-colors">
                        {row.skill}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-ink-400 hidden sm:table-cell">{row.role_category}</td>
                      <td className="px-4 py-3 text-right font-mono text-xs text-ink-200">{row.mention_count}</td>
                      <td className="px-4 py-3 text-right font-mono text-xs text-ink-300 hidden sm:table-cell">
                        {(row.pct_of_postings * 100).toFixed(1)}%
                      </td>
                      <td className="px-3 sm:px-5 py-3 text-right">
                        <span className={wow > 20 ? 'badge-rising' : wow < -10 ? 'badge-falling' : 'badge-neutral'}>
                          {sign}{wow.toFixed(1)}%
                        </span>
                      </td>
                    </tr>
                  )
                })
              )}
              {/* Skeleton overlay rows while navigating pages */}
              {skillsLoading && pagedSkills.length > 0 && (
                Array.from({ length: skillsPageSize }, (_, i) => (
                  <tr key={`sk${i}`} className="border-b border-border">
                    {Array.from({ length: 5 }, (_, j) => (
                      <td key={j} className={`px-4 py-3 ${j === 1 || j === 3 ? 'hidden sm:table-cell' : ''}`}>
                        <div className="skeleton h-3 rounded" style={{ width: j === 0 ? '80px' : j === 1 ? '100px' : '48px' }} />
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination bar — always visible */}
        {!skillsError && (
          <SkillsPaginationBar
            page={skillsPage}
            totalPages={skillsTotalPages}
            totalCount={skillsTotal}
            pageSize={skillsPageSize}
            onPage={setSkillsPage}
            onPageSize={setSkillsPageSize}
            loading={skillsLoading}
          />
        )}
      </div>
    </div>
  )
}
