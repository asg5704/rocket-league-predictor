function Block({ className }: { className?: string }) {
  return <div className={`skeleton-shimmer rounded ${className ?? ""}`} />;
}

export function PlayerListSkeleton() {
  return (
    <div className="divide-y divide-line" aria-hidden="true">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="flex min-h-14 items-center gap-3 px-3 py-2">
          <Block className="h-5 w-5 shrink-0" />
          <div className="flex min-w-0 flex-1 flex-col gap-1.5">
            <div className="flex items-center gap-2">
              <Block className="h-4 w-28" />
              <Block className="h-4 w-14" />
            </div>
            <Block className="h-3 w-20" />
          </div>
          <Block className="ml-auto h-4 w-9" />
        </div>
      ))}
    </div>
  );
}

export function LeaderboardSkeleton() {
  return (
    <div className="divide-y divide-line" aria-hidden="true">
      {Array.from({ length: 8 }).map((_, i) => (
        <div
          key={i}
          className="grid grid-cols-[1.5rem_1.25rem_minmax(0,1fr)_5.5rem_2.75rem] items-center gap-3 px-3 py-2.5 sm:grid-cols-[3rem_4rem_minmax(0,1fr)_minmax(0,1.4fr)_4rem_7rem]"
        >
          <Block className="h-4 w-4" />
          <Block className="h-4 w-5" />
          <Block className="h-4 w-24" />
          <Block className="h-4 w-full" />
          <Block className="ml-auto h-4 w-10" />
          <Block className="hidden h-2 w-full sm:block" />
        </div>
      ))}
    </div>
  );
}

export function LineupCardSkeleton() {
  return (
    <div
      aria-hidden="true"
      className="grid gap-6 rounded-[10px] border border-line bg-surface p-5 md:grid-cols-[1fr_minmax(0,22rem)]"
    >
      <div className="flex flex-col gap-3">
        <Block className="h-5 w-32" />
        {[0, 1, 2].map((i) => (
          <Block key={i} className="h-6 w-48" />
        ))}
        <Block className="mt-2 h-14 w-40" />
      </div>
      <div className="flex flex-col justify-center gap-4">
        {[0, 1, 2].map((i) => (
          <div key={i} className="flex flex-col gap-1.5">
            <Block className="h-3 w-full" />
            <Block className="h-4 w-full" />
          </div>
        ))}
      </div>
    </div>
  );
}
