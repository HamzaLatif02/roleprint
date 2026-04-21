import { useState } from 'react'

const DownloadIcon = () => (
  <svg width="11" height="11" viewBox="0 0 12 12" fill="none" aria-hidden="true">
    <path d="M6 1v7M3 6l3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M1 10h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
)

/**
 * Renders an anchor styled as a small outlined secondary button.
 * When `href` is null/undefined the button is shown disabled.
 *
 * @param {string|null} href  - Full export URL (same-origin /api/export/…)
 * @param {string}      label - Button label text (default "Export CSV")
 */
export function ExportButton({ href, label = 'Export CSV' }) {
  const [state, setState] = useState('idle')

  const baseClass =
    'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md ' +
    'label-mono text-[9px] border transition-all duration-150 shrink-0'

  const activeClass =
    baseClass +
    ' border-border text-ink-400 hover:border-amber-dim hover:text-amber-glow ' +
    'bg-transparent cursor-pointer'

  const disabledClass =
    baseClass + ' border-border text-ink-500 bg-transparent opacity-40 cursor-not-allowed'

  if (!href) {
    return (
      <span className={disabledClass}>
        <DownloadIcon />
        {label}
      </span>
    )
  }

  const handleClick = () => {
    setState('downloading')
    setTimeout(() => setState('idle'), 2000)
  }

  return (
    <a
      href={href}
      download
      onClick={handleClick}
      className={activeClass}
    >
      <DownloadIcon />
      {state === 'downloading' ? 'Downloading…' : label}
    </a>
  )
}
