import { Component } from 'react'

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, message: '' }
  }

  static getDerivedStateFromError(err) {
    return { hasError: true, message: err.message ?? 'Something went wrong' }
  }

  retry = () => this.setState({ hasError: false, message: '' })

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[300px] gap-4 text-center p-8">
          <div className="w-12 h-12 rounded-full bg-rose-faint border border-rose-signal/30 flex items-center justify-center text-rose-signal text-2xl">
            ⚠
          </div>
          <div>
            <p className="text-ink-100 font-semibold mb-1">Something went wrong</p>
            <p className="font-mono text-xs text-rose-signal/80 max-w-xs">{this.state.message}</p>
          </div>
          <button onClick={this.retry} className="btn-ghost text-xs">
            ↺ Retry
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

/** Inline error display for hook-based fetch errors */
export function FetchError({ message, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
      <div className="w-10 h-10 rounded-full bg-rose-faint border border-rose-signal/30 flex items-center justify-center text-rose-signal">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M8 1L15 14H1L8 1Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
          <path d="M8 6v3M8 11v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
      </div>
      <div>
        <p className="text-sm text-ink-200 mb-0.5">Failed to load data</p>
        <p className="font-mono text-xs text-ink-400">{message}</p>
      </div>
      {onRetry && (
        <button onClick={onRetry} className="btn-ghost text-xs px-3 py-1.5">
          ↺ Retry
        </button>
      )}
    </div>
  )
}
