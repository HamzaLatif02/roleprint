export function Skeleton({ className = '', ...props }) {
  return <div className={`skeleton ${className}`} {...props} />
}

export function SkeletonCard({ lines = 3 }) {
  return (
    <div className="card p-5 space-y-3">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-8 w-32" />
      {Array.from({ length: lines - 2 }, (_, i) => (
        <Skeleton key={i} className={`h-3 ${i === 0 ? 'w-full' : 'w-3/4'}`} />
      ))}
    </div>
  )
}

export function SkeletonChart({ height = 240 }) {
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-4">
        <Skeleton className="h-5 w-36" />
        <Skeleton className="h-4 w-20" />
      </div>
      <Skeleton className={`w-full rounded-lg`} style={{ height }} />
    </div>
  )
}

export function SkeletonStat() {
  return (
    <div className="card p-5 space-y-2">
      <Skeleton className="h-3 w-20" />
      <Skeleton className="h-10 w-28" />
      <Skeleton className="h-3 w-32" />
    </div>
  )
}

export function SkeletonRow() {
  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-border">
      <Skeleton className="h-4 w-24 shrink-0" />
      <Skeleton className="h-4 w-16 shrink-0" />
      <Skeleton className="h-4 flex-1" />
      <Skeleton className="h-5 w-12 rounded" />
    </div>
  )
}
