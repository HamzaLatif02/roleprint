import { useCallback } from 'react'
import {
  AreaChart, Area, LineChart, Line, ComposedChart,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { useApi } from '../hooks/useApi'
import { api } from '../api/client'
import { useApp } from '../context/AppContext'
import { SkeletonChart } from '../components/Skeleton'
import { FetchError } from '../components/ErrorBoundary'

const AMBER = '#f5a623'
const TEAL = '#2dd4bf'
const ROSE = '#f05151'
const INDIGO = '#818cf8'

function SentimentTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const sentiment = payload.find((p) => p.dataKey === 'avg_sentiment')
  const urgency = payload.find((p) => p.dataKey === 'urgency_score')
  const count = payload.find((p) => p.dataKey === 'posting_count')
  return (
    <div className="custom-tooltip min-w-[180px]">
      <div className="label-mono text-[9px] mb-2 text-ink-400">{label}</div>
      {sentiment && (
        <div className="flex items-center justify-between gap-4 mb-1">
          <span className="text-xs text-ink-200">Avg sentiment</span>
          <span
            className="font-mono text-xs font-bold"
            style={{ color: sentiment.value >= 0 ? TEAL : ROSE }}
          >
            {sentiment.value > 0 ? '+' : ''}{sentiment.value?.toFixed(3)}
          </span>
        </div>
      )}
      {urgency && (
        <div className="flex items-center justify-between gap-4 mb-1">
          <span className="text-xs text-ink-200">Urgency hits</span>
          <span className="font-mono text-xs font-bold" style={{ color: AMBER }}>{urgency.value}</span>
        </div>
      )}
      {count && (
        <div className="flex items-center justify-between gap-4">
          <span className="text-xs text-ink-400">Postings</span>
          <span className="font-mono text-xs text-ink-300">{count.value}</span>
        </div>
      )}
    </div>
  )
}

function SentimentBadge({ value }) {
  if (value === null || value === undefined) return <span className="badge-neutral">—</span>
  if (value > 0.1) return <span className="badge-rising">+{value.toFixed(3)}</span>
  if (value < -0.1) return <span className="badge-falling">{value.toFixed(3)}</span>
  return <span className="badge-neutral">{value > 0 ? '+' : ''}{value.toFixed(3)}</span>
}

export default function Sentiment() {
  const { roleFilter } = useApp()

  const fetchSentiment = useCallback(
    () => api.sentiment(roleFilter, 12),
    [roleFilter]
  )
  const { data, loading, error, refetch } = useApi(fetchSentiment, [roleFilter])

  const weeks = data ?? []

  // Summary stats
  const lastWeek = weeks[weeks.length - 1]
  const avgSentiment = weeks.length
    ? weeks.reduce((s, w) => s + w.avg_sentiment, 0) / weeks.length
    : null
  const totalUrgency = weeks.reduce((s, w) => s + w.urgency_score, 0)
  const trend = weeks.length >= 2
    ? weeks[weeks.length - 1].avg_sentiment - weeks[0].avg_sentiment
    : null

  return (
    <div className="p-5 lg:p-7 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="font-display text-3xl tracking-widest text-gradient-amber mb-1">SENTIMENT</h1>
        <p className="font-mono text-xs text-ink-400">
          Tone and urgency signals{roleFilter ? ` · ${roleFilter}` : ' · all roles'}
        </p>
      </div>

      {/* Summary stat row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        {[
          {
            label: 'Avg Sentiment',
            value: avgSentiment !== null ? (avgSentiment > 0 ? '+' : '') + avgSentiment.toFixed(3) : '—',
            color: avgSentiment === null ? INDIGO : avgSentiment > 0 ? TEAL : ROSE,
            sub: 'VADER compound score',
          },
          {
            label: 'Latest Week',
            value: lastWeek ? (lastWeek.avg_sentiment > 0 ? '+' : '') + lastWeek.avg_sentiment.toFixed(3) : '—',
            color: lastWeek ? lastWeek.avg_sentiment >= 0 ? TEAL : ROSE : INDIGO,
            sub: lastWeek?.week ?? '—',
          },
          {
            label: 'Total Urgency',
            value: totalUrgency.toLocaleString(),
            color: AMBER,
            sub: 'phrase matches summed',
          },
          {
            label: 'Sentiment Trend',
            value: trend !== null ? (trend > 0 ? '▲ UP' : trend < 0 ? '▼ DOWN' : '→ FLAT') : '—',
            color: trend === null ? INDIGO : trend > 0 ? TEAL : trend < 0 ? ROSE : INDIGO,
            sub: 'first → last week',
          },
        ].map((s) => (
          <div
            key={s.label}
            className="card p-4"
            style={{ borderColor: `${s.color}20` }}
          >
            <div className="label-mono text-[9px] mb-1.5" style={{ color: `${s.color}80` }}>
              {s.label.toUpperCase()}
            </div>
            <div
              className="font-display text-2xl leading-none mb-1"
              style={{ color: s.color, textShadow: `0 0 16px ${s.color}30` }}
            >
              {loading ? <span className="skeleton inline-block w-16 h-7 rounded" /> : s.value}
            </div>
            <div className="font-mono text-[10px] text-ink-400">{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Main chart */}
      <div className="card p-5 mb-5">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="font-display text-base tracking-widest text-ink-100">SENTIMENT TIMELINE</h2>
            <p className="font-mono text-[10px] text-ink-400 mt-0.5">avg weekly tone · dashed = urgency signal</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 label-mono text-[9px] text-teal-signal">
              <span className="w-3 h-0.5 bg-teal-signal rounded" />
              sentiment
            </div>
            <div className="flex items-center gap-1.5 label-mono text-[9px] text-amber-glow">
              <span className="w-3 h-0.5 bg-amber-glow rounded border-dashed border-t" />
              urgency
            </div>
          </div>
        </div>

        {loading ? (
          <div className="skeleton w-full rounded-lg" style={{ height: 280 }} />
        ) : error ? (
          <FetchError message={error} onRetry={refetch} />
        ) : weeks.length === 0 ? (
          <div className="h-60 flex items-center justify-center text-ink-400 font-mono text-xs">
            No sentiment data yet
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={weeks} margin={{ top: 4, right: 24, bottom: 0, left: -10 }}>
              <defs>
                <linearGradient id="sentGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={TEAL} stopOpacity={0.25} />
                  <stop offset="95%" stopColor={TEAL} stopOpacity={0} />
                </linearGradient>
                <linearGradient id="sentGradientNeg" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={ROSE} stopOpacity={0.15} />
                  <stop offset="95%" stopColor={ROSE} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid />
              <XAxis
                dataKey="week"
                tickFormatter={(v) => v.slice(5)}
              />
              <YAxis yAxisId="left" domain={[-1, 1]} />
              <YAxis yAxisId="right" orientation="right" />
              <Tooltip content={<SentimentTooltip />} />
              <ReferenceLine yAxisId="left" y={0} stroke="rgba(255,255,255,0.1)" strokeDasharray="4 4" />
              <Area
                yAxisId="left"
                type="monotone"
                dataKey="avg_sentiment"
                stroke={TEAL}
                strokeWidth={2}
                fill="url(#sentGradient)"
                dot={false}
                activeDot={{ r: 5, fill: TEAL, strokeWidth: 0 }}
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="urgency_score"
                stroke={AMBER}
                strokeWidth={1.5}
                strokeDasharray="5 3"
                dot={false}
                activeDot={{ r: 4, fill: AMBER, strokeWidth: 0 }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Weekly breakdown table */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <h2 className="font-display text-base tracking-widest text-ink-100">WEEKLY BREAKDOWN</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left px-5 py-3 label-mono text-[9px] font-normal text-ink-400">WEEK</th>
                <th className="text-right px-4 py-3 label-mono text-[9px] font-normal text-ink-400">SENTIMENT</th>
                <th className="text-right px-4 py-3 label-mono text-[9px] font-normal text-ink-400">URGENCY</th>
                <th className="text-right px-5 py-3 label-mono text-[9px] font-normal text-ink-400">POSTINGS</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 6 }, (_, i) => (
                  <tr key={i} className="border-b border-border">
                    {Array.from({ length: 4 }, (_, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="skeleton h-3 rounded w-20" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : [...weeks].reverse().map((row, i) => (
                <tr
                  key={row.week}
                  className="border-b border-border hover:bg-void-700 transition-colors"
                >
                  <td className="px-5 py-3 font-mono text-xs text-ink-300">{row.week}</td>
                  <td className="px-4 py-3 text-right">
                    <SentimentBadge value={row.avg_sentiment} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span
                      className="font-mono text-xs font-bold"
                      style={{ color: row.urgency_score > 0 ? AMBER : 'inherit' }}
                    >
                      {row.urgency_score}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-right font-mono text-xs text-ink-300">{row.posting_count}</td>
                </tr>
              ))}
              {!loading && weeks.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-5 py-10 text-center text-ink-400 font-mono text-xs">
                    No sentiment data available
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Explainer */}
      <div className="card p-5 mt-5">
        <h3 className="font-display text-sm tracking-widest text-ink-300 mb-3">HOW SENTIMENT IS CALCULATED</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <div className="label-mono text-[9px] text-teal-signal mb-1.5">SENTIMENT SCORE</div>
            <p className="font-sans text-xs text-ink-300 leading-relaxed">
              Each job description is scored using VADER (Valence Aware Dictionary for sEntiment Reasoning),
              a lexicon-based model tuned for short social/professional text. Scores range from −1.0 (very negative)
              to +1.0 (very positive). Weekly values are averaged across all processed postings.
            </p>
          </div>
          <div>
            <div className="label-mono text-[9px] text-amber-glow mb-1.5">URGENCY SCORE</div>
            <p className="font-sans text-xs text-ink-300 leading-relaxed">
              Urgency is counted by matching phrase patterns like <span className="font-mono text-amber-dim">immediately</span>,{' '}
              <span className="font-mono text-amber-dim">ASAP</span>,{' '}
              <span className="font-mono text-amber-dim">urgent hire</span>, and similar signals in raw job text.
              Higher scores indicate more time-pressured postings in a given week.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
