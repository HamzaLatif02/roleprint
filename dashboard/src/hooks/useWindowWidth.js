import { useState, useEffect } from 'react'

/**
 * Returns the current window inner width, updating on resize.
 * Safe to call in SSR-capable environments (returns 1024 as fallback).
 */
export function useWindowWidth() {
  const [width, setWidth] = useState(
    () => (typeof window !== 'undefined' ? window.innerWidth : 1024)
  )

  useEffect(() => {
    const handler = () => setWidth(window.innerWidth)
    window.addEventListener('resize', handler, { passive: true })
    return () => window.removeEventListener('resize', handler)
  }, [])

  return width
}
