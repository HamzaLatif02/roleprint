/**
 * EmptyState — shown after a successful fetch that returned no data.
 *
 * Props:
 *  icon      — emoji or JSX element rendered large above the title
 *  title     — short heading (display font)
 *  message   — one or two sentences of context (mono font)
 *  action    — optional JSX node (button / link) rendered below the message
 *  className — override the wrapper's min-height / padding
 */
export function EmptyState({ icon, title, message, action, className = 'h-64' }) {
  return (
    <div className={`flex flex-col items-center justify-center text-center px-6 py-4 ${className}`}>
      {/* Icon */}
      <div className="text-4xl mb-4 opacity-50 select-none" aria-hidden="true">
        {icon}
      </div>

      {/* Title */}
      <h3 className="font-display text-base tracking-widest text-ink-300 mb-2">
        {title}
      </h3>

      {/* Message */}
      <p className="font-mono text-xs text-ink-400 max-w-xs leading-relaxed">
        {message}
      </p>

      {/* Optional action */}
      {action && (
        <div className="mt-4">
          {action}
        </div>
      )}
    </div>
  )
}

/**
 * EmptyStateRow — for use inside a <tbody> when a table has no rows.
 * Wraps EmptyState in a full-width <tr><td> so table markup stays valid.
 */
export function EmptyStateRow({ colSpan, icon, title, message, action }) {
  return (
    <tr>
      <td colSpan={colSpan} className="py-2">
        <EmptyState
          icon={icon}
          title={title}
          message={message}
          action={action}
          className="h-48"
        />
      </td>
    </tr>
  )
}
