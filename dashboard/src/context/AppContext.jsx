import { createContext, useContext, useState, useEffect } from 'react'

const AppContext = createContext(null)

export function AppProvider({ children }) {
  const [roleFilter, setRoleFilter] = useState('')
  const [darkMode, setDarkMode] = useState(true)
  const [sidebarOpen, setSidebarOpen] = useState(false)

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
