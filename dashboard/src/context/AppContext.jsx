import { createContext, useCallback, useContext, useState, useEffect } from 'react'

const AppContext = createContext(null)

export function AppProvider({ children }) {
  const [roleFilter, setRoleFilter] = useState('')
  const [darkMode, setDarkMode] = useState(true)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Global stats — used by the navbar staleness indicator
  const [lastScraped, setLastScraped] = useState(null)
  const [statsRefreshing, setStatsRefreshing] = useState(false)

  // Persist dark mode preference
  useEffect(() => {
    const stored = localStorage.getItem('rp-dark')
    if (stored !== null) setDarkMode(stored === 'true')
  }, [])

  useEffect(() => {
    localStorage.setItem('rp-dark', String(darkMode))
    if (darkMode) {
      document.documentElement.classList.remove('light')
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
      document.documentElement.classList.add('light')
    }
  }, [darkMode])

  // Fetch stats summary for the active role filter (used by navbar indicator)
  const refetchStats = useCallback(async () => {
    setStatsRefreshing(true)
    try {
      const params = new URLSearchParams()
      if (roleFilter) params.set('role_category', roleFilter)
      const qs = params.toString()
      const res = await fetch(`/api/stats/summary${qs ? `?${qs}` : ''}`)
      if (res.ok) {
        const data = await res.json()
        setLastScraped(data.last_scraped ?? data.last_updated ?? null)
      }
    } catch {
      // silently ignore — indicator stays at last known value
    } finally {
      setStatsRefreshing(false)
    }
  }, [roleFilter])

  // Re-fetch whenever the role filter changes or on mount
  useEffect(() => { refetchStats() }, [refetchStats])

  // Close sidebar on route change (mobile)
  const closeSidebar = () => setSidebarOpen(false)

  return (
    <AppContext.Provider
      value={{
        roleFilter,
        setRoleFilter,
        darkMode,
        setDarkMode,
        sidebarOpen,
        setSidebarOpen,
        closeSidebar,
        lastScraped,
        statsRefreshing,
        refetchStats,
      }}
    >
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be inside AppProvider')
  return ctx
}
