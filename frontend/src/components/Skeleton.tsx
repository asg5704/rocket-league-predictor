function Block({ className }: { className?: string }) {
  return <div className={`skeleton-shimmer rounded ${className ?? ''}`} />
}

export function PlayerListSkeleton() {
  return (
    <div className="divide-y divide-border-dim">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 px-3 py-2.5">
          <Block className="w-4 h-4 flex-shrink-0" />
          <div className="flex-1 min-w-0 flex flex-col gap-1.5">
            <div className="flex items-center gap-2">
              <Block className="h-3.5 w-28" />
              <Block className="h-4 w-14 rounded-full" />
            </div>
            <Block className="h-3 w-20" />
          </div>
          <Block className="h-3 w-8 ml-auto" />
        </div>
      ))}
    </div>
  )
}

export function LeaderboardSkeleton() {
  return (
    <div className="divide-y divide-border-dim">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="grid grid-cols-[2.5rem_1fr_5rem_5rem] gap-2 items-center px-3 py-2.5">
          <Block className="h-3 w-4" />
          <Block className="h-3.5 w-32" />
          <Block className="h-3 w-10 ml-auto" />
          <Block className="h-1 w-20 ml-auto rounded-full" />
        </div>
      ))}
    </div>
  )
}

export function LineupCardSkeleton() {
  return (
    <div className="rounded-xl border border-border-dim bg-surface p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <Block className="h-5 w-24" />
        <Block className="h-5 w-16" />
      </div>
      <div className="flex flex-col gap-2">
        {[0, 1, 2].map((i) => (
          <div key={i} className="flex items-center justify-between">
            <Block className="h-3.5 w-32" />
            <Block className="h-4 w-16 rounded-full" />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-3 gap-2 pt-1 border-t border-border-dim">
        {[0, 1, 2].map((i) => (
          <div key={i} className="flex flex-col gap-1.5">
            <Block className="h-2.5 w-full" />
            <Block className="h-1 w-full rounded-full" />
          </div>
        ))}
      </div>
    </div>
  )
}
