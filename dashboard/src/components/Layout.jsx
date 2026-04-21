import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { useApp } from '../context/AppContext'
import { ErrorBoundary } from './ErrorBoundary'
import { getRelativeTime, stalenessColor } from '../utils'

const PAGE_TITLES = {
  '/': 'Overview',
  '/trends': 'Trends',
  '/compare': 'Compare',
  '/sentiment': 'Sentiment',
  '/skill-gap': 'Skill Gap',
}

export function Layout({ children }) {
  const { sidebarOpen, setSidebarOpen, closeSidebar, lastScraped } = useApp()
  const location = useLocation()
  const title = PAGE_TITLES[location.pathname] ?? 'Roleprint'

  // Close sidebar on route change
  useEffect(() => {
    closeSidebar()
  }, [location.pathname]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex h-screen overflow-hidden bg-void-900">
      {/* Sidebar — desktop always visible, mobile overlay */}
      <div
        className={`
          fixed inset-y-0 left-0 z-40 w-56 transition-transform duration-250 ease-in-out
          lg:relative lg:translate-x-0 lg:z-auto lg:shrink-0
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        <Sidebar />
      </div>

      {/* Backdrop (mobile) */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-void-950/80 backdrop-blur-sm lg:hidden"
          onClick={closeSidebar}
        />
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top bar */}
        <header className="shrink-0 flex items-center justify-between px-5 py-3 border-b border-border bg-void-800/60 backdrop-blur-sm">
          <div className="flex items-center gap-3">
            {/* Hamburger — mobile only */}
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="lg:hidden p-1.5 rounded-lg text-ink-300 hover:text-ink-100 hover:bg-void-700 transition-colors"
              aria-label="Toggle sidebar"
            >
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                {sidebarOpen ? (
                  <path d="M3 3l12 12M15 3L3 15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                ) : (
                  <>
                    <line x1="2" y1="5" x2="16" y2="5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                    <line x1="2" y1="9" x2="16" y2="9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                    <line x1="2" y1="13" x2="16" y2="13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                  </>
                )}
              </svg>
            </button>

            {/* Breadcrumb */}
            <div className="flex items-center gap-2">
              <span className="label-mono text-[9px] text-ink-400 hidden sm:block">roleprint /</span>
              <h1 className="font-display text-lg tracking-widest text-ink-100">{title.toUpperCase()}</h1>
            </div>
          </div>

          {/* Staleness indicator */}
          <div className="flex items-center gap-1.5 min-w-0">
            {lastScraped ? (
              <>
                <span className="w-1.5 h-1.5 rounded-full bg-teal-signal animate-pulse shrink-0 hidden sm:block" />
                <span className={`label-mono text-[9px] truncate hidden sm:block ${stalenessColor(lastScraped)}`}>
                  {getRelativeTime(lastScraped)}
                </span>
              </>
            ) : (
              <>
                <span className="w-1.5 h-1.5 rounded-full bg-teal-signal animate-pulse shrink-0" />
                <span className="label-mono text-[9px] text-ink-400 hidden sm:block">LIVE</span>
              </>
            )}
          </div>
        </header>

        {/* Page scroll area */}
        <main className="flex-1 overflow-y-auto grid-bg">
          <ErrorBoundary>
            <div className="page-enter">
              {children}
            </div>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  )
}
