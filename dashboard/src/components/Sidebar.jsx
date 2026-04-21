import { NavLink, useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext'
import { useApi } from '../hooks/useApi'
import { api } from '../api/client'
import { useCallback } from 'react'
import { toTitleCase } from '../utils'

const NAV = [
  {
    path: '/',
    label: 'Overview',
    color: '#f5a623',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="1" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
        <rect x="9" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
        <rect x="1" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
        <rect x="9" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      </svg>
    ),
  },
  {
    path: '/trends',
    label: 'Trends',
    color: '#2dd4bf',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <polyline points="1,12 5,7 8,9 12,4 15,6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
        <polyline points="12,4 15,4 15,7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  {
    path: '/compare',
    label: 'Compare',
    color: '#818cf8',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle cx="5" cy="8" r="4" stroke="currentColor" strokeWidth="1.4"/>
        <circle cx="11" cy="8" r="4" stroke="currentColor" strokeWidth="1.4"/>
      </svg>
    ),
  },
  {
    path: '/sentiment',
    label: 'Sentiment',
    color: '#fb7185',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M1 12 Q4 4 8 8 Q12 12 15 4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
        <path d="M1 12 Q4 4 8 8 Q12 12 15 4 L15 14 L1 14 Z" fill="currentColor" fillOpacity="0.12"/>
      </svg>
    ),
  },
  {
    path: '/postings',
    label: 'Postings',
    color: '#a78bfa',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <rect x="2" y="1.5" width="12" height="13" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
        <line x1="5" y1="5.5" x2="11" y2="5.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
        <line x1="5" y1="8" x2="11" y2="8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
        <line x1="5" y1="10.5" x2="8.5" y2="10.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    path: '/skill-gap',
    label: 'Skill Gap',
    color: '#4ade80',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.4"/>
        <path d="M8 4.5v3.5l2.5 1.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M11.5 1.5L14 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
        <path d="M4.5 1.5L2 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
      </svg>
    ),
  },
]

export function Sidebar() {
  const { roleFilter, setRoleFilter, darkMode, setDarkMode, closeSidebar } = useApp()

  const fetchRoles = useCallback(() => api.roles(), [])
  const { data: roles } = useApi(fetchRoles)

  return (
    <aside className="flex flex-col h-full bg-void-800 border-r border-border">
      {/* Logo */}
      <div className="px-5 pt-6 pb-5 border-b border-border">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-gray-900 flex items-center justify-center overflow-hidden shrink-0">
            <img src="/logo.png" alt="Roleprint logo" className="w-full h-full object-contain" />
          </div>
          <div>
            <div className="font-display text-lg text-amber-glow glow-amber leading-none tracking-widest">ROLEPRINT</div>
            <div className="label-mono text-[9px] text-ink-400 leading-none mt-0.5">job market intelligence</div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        <div className="label-mono text-[9px] px-2 mb-3 text-ink-500">navigation</div>
        {NAV.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/'}
            onClick={closeSidebar}
            className={({ isActive }) =>
              `group relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                isActive
                  ? 'nav-active bg-void-700'
                  : 'text-ink-300 hover:text-ink-100 hover:bg-void-700'
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <span
                    className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-full transition-all"
                    style={{ background: item.color, boxShadow: `0 0 8px ${item.color}60` }}
                  />
                )}
                <span
                  className="transition-colors duration-150"
                  style={{ color: isActive ? item.color : undefined }}
                >
                  {item.icon}
                </span>
                <span>{item.label}</span>
                {isActive && (
                  <span
                    className="ml-auto w-1.5 h-1.5 rounded-full"
                    style={{ background: item.color, boxShadow: `0 0 6px ${item.color}` }}
                  />
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Role filter */}
      <div className="px-4 py-4 border-t border-border">
        <div className="label-mono text-[9px] mb-2 text-ink-500">filter by role</div>
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          className="w-full text-xs"
          aria-label="Filter by role category"
        >
          <option value="">All Roles</option>
          {roles?.map((r) => (
            <option key={r.role_category} value={r.role_category}>
              {toTitleCase(r.role_category)}
            </option>
          ))}
        </select>
        {roleFilter && (
          <button
            onClick={() => setRoleFilter('')}
            className="mt-1.5 text-xs text-ink-400 hover:text-amber-glow transition-colors flex items-center gap-1"
          >
            <span>✕</span> Clear filter
          </button>
        )}
      </div>

      {/* Dark mode toggle */}
      <div className="px-4 py-3 border-t border-border">
        <button
          onClick={() => setDarkMode(!darkMode)}
          className="w-full flex items-center justify-between group"
          aria-label="Toggle dark mode"
        >
          <span className="label-mono text-[9px] text-ink-500 group-hover:text-ink-400 transition-colors">
            {darkMode ? 'dark mode' : 'light mode'}
          </span>
          <div
            className={`relative w-9 h-5 rounded-full border transition-all duration-200 ${
              darkMode ? 'bg-amber-muted border-amber-dim' : 'bg-slate-200 border-slate-300'
            }`}
          >
            <span
              className={`absolute top-0.5 w-4 h-4 rounded-full transition-all duration-200 flex items-center justify-center text-[9px] ${
                darkMode
                  ? 'right-0.5 bg-amber-glow shadow-amber-glow-sm'
                  : 'left-0.5 bg-white shadow-sm'
              }`}
            >
              {darkMode ? '◑' : '○'}
            </span>
          </div>
        </button>
      </div>
    </aside>
  )
}
