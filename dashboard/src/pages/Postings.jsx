import { useState, useEffect, useCallback, useRef } from 'react'
import { useApi } from '../hooks/useApi'
import { api } from '../api/client'
import { useApp } from '../context/AppContext'
import { ErrorState } from '../components/ErrorState'
import { toTitleCase } from '../utils'

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: '2-digit' })
}

const SOURCE_COLORS = {
  reed:      { dot: '#f5a623', label: 'Reed' },
  remoteok:  { dot: '#2dd4bf', label: 'RemoteOK' },
  adzuna:    { dot: '#818cf8', label: 'Adzuna' },
}

function SourceBadge({ source }) {
  const s = SOURCE_COLORS[source?.toLowerCase()] ?? { dot: '#565878', label: source ?? '—' }
  return (
    <span className="inline-flex items-center gap-1 font-mono text-[10px] text-ink-400">
      <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: s.dot }} />
      {s.label}
    </span>
  )
}

function SentimentBadge({ score }) {
  if (score === null || score === undefined) {
    return <span className="badge-neutral">—</span>
  }
  const label = score > 0.05 ? `+${score.toFixed(2)}` : score.toFixed(2)
  if (score > 0.05) return <span className="badge-rising">{label}</span>
  if (score < -0.05) return <span className="badge-falling">{label}</span>
  return <span className="badge-neutral">{label}</span>
}

function SkillPills({ skills }) {
  if (!skills?.length) return <span className="text-ink-500 font-mono text-[10px]">—</span>
  const visible = skills.slice(0, 3)
  const extra = skills.length - visible.length
  return (
    <div className="flex flex-wrap gap-1">
      {visible.map((s) => (
        <span
          key={s}
          className="px-1.5 py-0.5 rounded font-mono text-[9px] bg-void-600 border border-border text-ink-300"
        >
          {s}
        </span>
      ))}
      {extra > 0 && (
        <span className="px-1.5 py-0.5 rounded font-mono text-[9px] bg-void-600 border border-border text-ink-500">
          +{extra}
        </span>
      )}
    </div>
  )
}

// ── Pagination helpers ────────────────────────────────────────────────────────

/**
 * Build the list of page tokens to render.
 * null = ellipsis gap.
 */
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

function PaginationBar({ page, totalPages, totalCount, pageSize, onPage, onPageSize, loading }) {
  const start = totalCount === 0 ? 0 : (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, totalCount)
  const pageList = buildPageList(page, totalPages)

  const btnBase =
    'min-w-[32px] h-8 flex items-center justify-center rounded-lg font-mono text-xs ' +
    'border transition-all duration-100 disabled:opacity-40 disabled:cursor-not-allowed'
  const btnInactive = btnBase + ' border-border text-ink-400 hover:border-border-bright hover:text-ink-200 bg-transparent'
  const btnActive   = btnBase + ' border-amber-dim bg-amber-muted text-amber-glow'
  const btnEllipsis = btnBase + ' border-transparent text-ink-500 cursor-default'

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-5 py-3 border-t border-border">
      {/* Count */}
      <div className="flex items-center gap-3 shrink-0">
        <span className="font-mono text-[10px] text-ink-400">
          {totalCount === 0
            ? 'No postings'
            : `Showing ${start.toLocaleString()}–${end.toLocaleString()} of ${totalCount.toLocaleString()}`}
        </span>
        {/* Page size */}
        <select
          value={pageSize}
          onChange={(e) => onPageSize(Number(e.target.value))}
          className="text-xs py-1 px-2 h-7"
          aria-label="Rows per page"
        >
          {[10, 20, 50, 100].map((n) => (
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

// ── Table skeleton ────────────────────────────────────────────────────────────

function TableSkeleton({ rows = 10 }) {
  return Array.from({ length: rows }, (_, i) => (
    <tr key={i} className="border-b border-border">
      <td className="px-5 py-3"><div className="skeleton h-4 w-48 rounded" /></td>
      <td className="px-4 py-3 hidden md:table-cell"><div className="skeleton h-3 w-28 rounded" /></td>
      <td className="px-4 py-3 hidden lg:table-cell"><div className="skeleton h-3 w-20 rounded" /></td>
      <td className="px-4 py-3 hidden xl:table-cell"><div className="flex gap-1">
        <div className="skeleton h-4 w-12 rounded" />
        <div className="skeleton h-4 w-10 rounded" />
      </div></td>
      <td className="px-4 py-3 hidden lg:table-cell"><div className="skeleton h-5 w-14 rounded" /></td>
      <td className="px-4 py-3 hidden md:table-cell"><div className="skeleton h-3 w-16 rounded" /></td>
      <td className="px-5 py-3"><div className="skeleton h-3 w-16 rounded" /></td>
    </tr>
  ))
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Postings() {
  const { roleFilter } = useApp()
  const tableRef = useRef(null)

  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  // Reset to page 1 when role filter or page size changes
  useEffect(() => { setPage(1) }, [roleFilter, pageSize]) // eslint-disable-line

  // Scroll to top of table on page navigation
  useEffect(() => {
    tableRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [page])

  const fetchPostings = useCallback(
    () => api.postings(roleFilter, page, pageSize),
    [roleFilter, page, pageSize]
  )
  const { data, loading, error, refetch } = useApi(fetchPostings, [roleFilter, page, pageSize])

  const postings = data?.data ?? []
  const totalCount = data?.total_count ?? 0
  const totalPages = data?.total_pages ?? 1

  const handlePageSize = (newSize) => {
    setPageSize(newSize)
    // setPage(1) handled by the useEffect above
  }

  return (
    <div className="p-5 lg:p-7 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="font-display text-3xl tracking-widest text-gradient-amber mb-1">POSTINGS</h1>
        <p className="font-mono text-xs text-ink-400">
          Recent job listings{roleFilter ? ` · ${roleFilter}` : ' · all roles'}
        </p>
      </div>

      {/* Table card */}
      <div ref={tableRef} className="card overflow-hidden scroll-mt-4">
        {/* Card header */}
        <div className="px-5 py-4 border-b border-border flex items-center justify-between">
          <h2 className="font-display text-base tracking-widest text-ink-100">RECENT POSTINGS</h2>
          <span className="label-mono text-[9px] text-ink-400">
            {loading ? 'Loading…' : `${totalCount.toLocaleString()} total`}
          </span>
        </div>

        {/* Error state */}
        {error && !loading && (
          <ErrorState error={error} onRetry={refetch} className="h-64" />
        )}

        {/* Table */}
        {!error && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-void-700">
                  <th className="text-left px-5 py-3 label-mono text-[9px] font-normal text-ink-400">JOB</th>
                  <th className="text-left px-4 py-3 label-mono text-[9px] font-normal text-ink-400 hidden md:table-cell">COMPANY</th>
                  <th className="text-left px-4 py-3 label-mono text-[9px] font-normal text-ink-400 hidden lg:table-cell">ROLE</th>
                  <th className="text-left px-4 py-3 label-mono text-[9px] font-normal text-ink-400 hidden xl:table-cell">SKILLS</th>
                  <th className="text-left px-4 py-3 label-mono text-[9px] font-normal text-ink-400 hidden lg:table-cell">SENTIMENT</th>
                  <th className="text-left px-4 py-3 label-mono text-[9px] font-normal text-ink-400 hidden md:table-cell">SOURCE</th>
                  <th className="text-right px-5 py-3 label-mono text-[9px] font-normal text-ink-400">DATE</th>
                </tr>
              </thead>
              <tbody className={loading ? 'opacity-50 pointer-events-none' : ''}>
                {loading && postings.length === 0 ? (
                  <TableSkeleton rows={pageSize} />
                ) : postings.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-5 py-14 text-center">
                      <div className="font-display text-2xl text-ink-500 tracking-widest mb-2">NO POSTINGS</div>
                      <p className="font-mono text-xs text-ink-400">
                        No postings found for this role yet
                      </p>
                    </td>
                  </tr>
                ) : (
                  postings.map((row) => (
                    <tr
                      key={row.id}
                      className="border-b border-border odd:bg-void-800 even:bg-void-900 hover:bg-void-700 transition-colors group"
                    >
                      {/* Title */}
                      <td className="px-5 py-3 max-w-xs">
                        <a
                          href={row.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-medium text-ink-100 group-hover:text-amber-glow transition-colors line-clamp-1 hover:underline decoration-amber-dim/50"
                          title={row.title}
                        >
                          {row.title || '—'}
                        </a>
                        {/* Mobile-only: company + role inline */}
                        <div className="md:hidden font-mono text-[10px] text-ink-400 mt-0.5 truncate">
                          {row.company}{row.company && row.role_category ? ' · ' : ''}{toTitleCase(row.role_category)}
                        </div>
                      </td>
                      {/* Company */}
                      <td className="px-4 py-3 hidden md:table-cell font-mono text-xs text-ink-300 max-w-[140px] truncate">
                        {row.company || '—'}
                      </td>
                      {/* Role */}
                      <td className="px-4 py-3 hidden lg:table-cell font-mono text-xs text-ink-400">
                        {toTitleCase(row.role_category)}
                      </td>
                      {/* Skills */}
                      <td className="px-4 py-3 hidden xl:table-cell">
                        <SkillPills skills={row.skills} />
                      </td>
                      {/* Sentiment */}
                      <td className="px-4 py-3 hidden lg:table-cell">
                        <SentimentBadge score={row.sentiment_score} />
                      </td>
                      {/* Source */}
                      <td className="px-4 py-3 hidden md:table-cell">
                        <SourceBadge source={row.source} />
                      </td>
                      {/* Date */}
                      <td className="px-5 py-3 text-right font-mono text-[10px] text-ink-400 whitespace-nowrap">
                        {formatDate(row.posted_at ?? row.scraped_at)}
                      </td>
                    </tr>
                  ))
                )}
                {/* Skeleton overlay rows while navigating */}
                {loading && postings.length > 0 && (
                  <TableSkeleton rows={pageSize} />
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination bar */}
        {!error && (
          <PaginationBar
            page={page}
            totalPages={totalPages}
            totalCount={totalCount}
            pageSize={pageSize}
            onPage={setPage}
            onPageSize={handlePageSize}
            loading={loading}
          />
        )}
      </div>
    </div>
  )
}
