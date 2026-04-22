import { Fragment, useEffect } from 'react'

// ── Pipeline stepper ──────────────────────────────────────────────────────────

const PIPELINE_STEPS = [
  {
    icon: '🔍',
    title: 'Scraping',
    color: '#f5a623',
    description:
      'Job postings are collected automatically every 6 hours from three sources: Reed, RemoteOK, and Adzuna. The scraper is built in Python using httpx and BeautifulSoup, with retry logic and deduplication to avoid storing duplicate postings.',
  },
  {
    icon: '⚙️',
    title: 'Processing',
    color: '#2dd4bf',
    description:
      'Each posting is passed through an NLP pipeline built with spaCy and NLTK. The pipeline extracts skills using noun chunk matching against a curated vocabulary, runs sentiment analysis using VADER to score the tone of each posting, and identifies topics using BERTopic.',
  },
  {
    icon: '📊',
    title: 'Analysis',
    color: '#818cf8',
    description:
      'Processed postings are aggregated weekly into skill trend tables. Week-over-week changes are calculated to identify rising and emerging skills. Role similarity scores are computed using cosine similarity of skill vectors.',
  },
  {
    icon: '🖥️',
    title: 'Dashboard',
    color: '#4ade80',
    description:
      'Results are served via a FastAPI REST API and displayed in this React dashboard. The dashboard updates automatically as new data is collected — no manual refresh needed.',
  },
]

function PipelineStep({ step, index, isLast }) {
  return (
    <div className="flex-1 flex flex-col rounded-xl border border-border bg-void-800 overflow-hidden min-w-0">
      {/* Accent top bar */}
      <div className="h-0.5 w-full" style={{ background: step.color }} />
      <div className="p-5 flex flex-col flex-1">
        {/* Step number + icon */}
        <div className="flex items-center gap-2 mb-3">
          <span className="label-mono text-[9px] px-1.5 py-0.5 rounded border"
            style={{ color: step.color, borderColor: `${step.color}40`, background: `${step.color}12` }}>
            {String(index + 1).padStart(2, '0')}
          </span>
          <span className="text-xl select-none" aria-hidden="true">{step.icon}</span>
        </div>
        {/* Title */}
        <h3 className="font-display text-base tracking-widest mb-2" style={{ color: step.color }}>
          {step.title.toUpperCase()}
        </h3>
        {/* Description */}
        <p className="font-sans text-xs text-ink-300 leading-relaxed flex-1">
          {step.description}
        </p>
      </div>
    </div>
  )
}

// ── Data sources ──────────────────────────────────────────────────────────────

const SOURCES = [
  {
    name: 'Reed',
    url: 'reed.co.uk',
    dot: '#f5a623',
    badge: 'UK',
    desc: 'UK-focused job board covering a broad range of industries and seniority levels.',
    method: 'Scraped via HTTP with BeautifulSoup',
  },
  {
    name: 'RemoteOK',
    url: 'remoteok.com',
    dot: '#2dd4bf',
    badge: 'Remote',
    desc: 'Remote-first roles worldwide with a strong bias toward software and data roles.',
    method: 'Collected via public JSON API',
  },
  {
    name: 'Adzuna',
    url: 'adzuna.com',
    dot: '#818cf8',
    badge: 'Global',
    desc: 'Aggregates UK and global job listings from hundreds of boards in one API.',
    method: 'Collected via official REST API',
  },
]

// ── Tech stack ────────────────────────────────────────────────────────────────

const STACK = [
  { label: 'Backend', items: 'Python, FastAPI, SQLAlchemy, Alembic' },
  { label: 'NLP', items: 'spaCy, NLTK (VADER), scikit-learn, BERTopic' },
  { label: 'Scraping', items: 'httpx, BeautifulSoup4, APScheduler' },
  { label: 'Database', items: 'PostgreSQL (Supabase)' },
  { label: 'Frontend', items: 'React, Vite, Recharts, Tailwind CSS' },
  { label: 'Hosting', items: 'Railway (API + scheduler), Vercel (dashboard)' },
]

// ── Section divider ───────────────────────────────────────────────────────────

function Divider() {
  return <div className="border-t border-border my-10" />
}

// ── Page ──────────────────────────────────────────────────────────────────────

const SECTION_CARD = 'bg-white dark:bg-void-800 rounded-xl shadow-sm border border-gray-100/50 dark:border-border p-6 mb-6'

export default function About() {
  useEffect(() => { document.title = 'About — Roleprint' }, [])
  return (
    <div className="p-5 lg:p-10 max-w-4xl mx-auto">
      {/* ── Page header ── */}
      <div className="mb-8">
        <h1 className="font-display text-3xl tracking-widest text-gradient-amber mb-1">ABOUT</h1>
        <p className="font-mono text-xs text-ink-400">How Roleprint works</p>
      </div>

      {/* ── 1. What is Roleprint ── */}
      <section aria-labelledby="what-heading" className={SECTION_CARD}>
        <h2 id="what-heading" className="font-display text-xl tracking-widest text-ink-100 mb-4">
          WHAT IS ROLEPRINT?
        </h2>
        <p className="font-sans text-sm text-ink-200 leading-relaxed mb-3 max-w-2xl">
          Roleprint analyses thousands of real job postings to identify which skills are in demand
          across different tech roles. It tracks how skill demand changes week over week, giving you
          an accurate, data-driven view of the job market — not guesswork.
        </p>
        <p className="font-sans text-sm text-ink-200 leading-relaxed max-w-2xl">
          Whether you are preparing for a job search, deciding what to learn next, or benchmarking
          yourself against a target role, Roleprint shows you exactly where the gaps are based on
          what employers are actually asking for right now.
        </p>
      </section>

      {/* ── 2. How it works — pipeline ── */}
      <section aria-labelledby="pipeline-heading" className={SECTION_CARD}>
        <h2 id="pipeline-heading" className="font-display text-xl tracking-widest text-ink-100 mb-2">
          HOW IT WORKS
        </h2>
        <p className="font-mono text-xs text-ink-400 mb-8">
          End-to-end data pipeline — from raw job listings to interactive insights
        </p>

        {/* Stepper — horizontal on desktop, vertical on mobile */}
        <div className="flex flex-col lg:flex-row items-stretch gap-4 lg:gap-0">
          {PIPELINE_STEPS.map((step, i) => (
            <Fragment key={step.title}>
              <PipelineStep step={step} index={i} isLast={i === PIPELINE_STEPS.length - 1} />

              {i < PIPELINE_STEPS.length - 1 && (
                <>
                  {/* Desktop: horizontal arrow */}
                  <div className="hidden lg:flex items-center justify-center shrink-0 w-8 text-ink-500 text-lg select-none">
                    →
                  </div>
                  {/* Mobile: vertical arrow */}
                  <div className="flex lg:hidden justify-center items-center h-6 text-ink-500 text-lg select-none">
                    ↓
                  </div>
                </>
              )}
            </Fragment>
          ))}
        </div>
      </section>

      {/* ── 3. Data sources ── */}
      <section aria-labelledby="sources-heading" className={SECTION_CARD}>
        <h2 id="sources-heading" className="font-display text-xl tracking-widest text-ink-100 mb-2">
          DATA SOURCES
        </h2>
        <p className="font-mono text-xs text-ink-400 mb-6">
          Three independent sources for broad market coverage
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {SOURCES.map((src) => (
            <div key={src.name} className="card p-5 flex flex-col gap-3">
              {/* Header */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ background: src.dot }} />
                  <span className="font-display text-base tracking-widest text-ink-100">{src.name}</span>
                </div>
                <span
                  className="label-mono text-[9px] px-1.5 py-0.5 rounded border"
                  style={{ color: src.dot, borderColor: `${src.dot}40`, background: `${src.dot}12` }}
                >
                  {src.badge}
                </span>
              </div>

              {/* URL */}
              <p className="font-mono text-[10px] text-ink-400">{src.url}</p>

              {/* Description */}
              <p className="font-sans text-xs text-ink-300 leading-relaxed flex-1">{src.desc}</p>

              {/* Method */}
              <div className="pt-3 border-t border-border">
                <p className="font-mono text-[10px] text-ink-500">{src.method}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── 4. Update frequency ── */}
      <section aria-labelledby="frequency-heading" className={SECTION_CARD}>
        <h2 id="frequency-heading" className="font-display text-xl tracking-widest text-ink-100 mb-6">
          UPDATE FREQUENCY
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-2xl">
          {[
            { label: 'Scraper runs', value: 'Every 6 hours', color: '#f5a623' },
            { label: 'NLP processing', value: 'Every 6 hours', sub: '1 hour after scraping', color: '#2dd4bf' },
            { label: 'Dashboard data', value: 'Automatic', sub: 'After each processing run', color: '#818cf8' },
            { label: 'Skill trends', value: 'Every 6 hours', sub: 'Updated with each NLP run', color: '#4ade80' },
          ].map((item) => (
            <div key={item.label} className="card p-4 flex items-start gap-4">
              <div className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0" style={{ background: item.color }} />
              <div>
                <div className="label-mono text-[9px] text-ink-400 mb-1">{item.label.toUpperCase()}</div>
                <div className="font-display text-lg leading-tight" style={{ color: item.color }}>{item.value}</div>
                {item.sub && <div className="font-mono text-[10px] text-ink-500 mt-0.5">{item.sub}</div>}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── 5. Tech stack ── */}
      <section aria-labelledby="stack-heading" className={SECTION_CARD}>
        <h2 id="stack-heading" className="font-display text-xl tracking-widest text-ink-100 mb-6">
          TECH STACK
        </h2>

        <div className="card overflow-hidden max-w-2xl">
          {STACK.map((row, i) => (
            <div
              key={row.label}
              className={`flex items-start gap-6 px-5 py-3.5 ${
                i < STACK.length - 1 ? 'border-b border-border' : ''
              } ${i % 2 === 0 ? 'bg-void-800' : 'bg-void-700'}`}
            >
              <div className="label-mono text-[9px] text-ink-400 w-20 shrink-0 pt-0.5">{row.label.toUpperCase()}</div>
              <div className="font-mono text-xs text-ink-200 leading-relaxed">{row.items}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── 6. Built by ── */}
      <section aria-labelledby="built-by-heading" className={SECTION_CARD + ' pb-6'}>
        <h2 id="built-by-heading" className="font-display text-xl tracking-widest text-ink-100 mb-6">
          BUILT BY
        </h2>

        <div className="flex items-start gap-4">
          {/* Avatar placeholder */}
          <div className="w-12 h-12 rounded-xl bg-amber-100 dark:bg-amber-muted border border-amber-200/60 dark:border-amber-dim/30 flex items-center justify-center shrink-0">
            <span className="font-display text-amber-600 dark:text-amber-glow text-lg">HL</span>
          </div>

          <div className="flex-1 min-w-0">
            <div className="font-display text-lg tracking-widest text-amber-glow mb-0.5">HAMZA LATIF</div>
            <p className="font-sans text-xs text-ink-300 leading-relaxed mb-4">
              Built as a portfolio project to demonstrate full-stack data engineering and NLP skills.
              The entire pipeline — from scraping to dashboard — was designed and built from scratch.
            </p>

            <div className="flex flex-wrap gap-2">
              <a
                href="https://github.com/HamzaLatif02/roleprint"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono
                           border border-border text-ink-300 hover:text-ink-100 hover:border-border-bright
                           transition-colors"
              >
                {/* GitHub icon */}
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>
                </svg>
                GitHub
              </a>

              <a
                href="https://www.linkedin.com/in/latif-hamza/"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono
                           border border-border text-ink-300 hover:text-ink-100 hover:border-border-bright
                           transition-colors"
              >
                {/* LinkedIn icon */}
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                </svg>
                LinkedIn
              </a>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
