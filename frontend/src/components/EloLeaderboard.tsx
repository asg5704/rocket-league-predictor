import type { EloRating } from '../api/client'

interface Props {
  ratings: EloRating[]
}

function EloBar({ elo }: { elo: number }) {
  const min = 1350
  const max = 1700
  const pct = Math.max(0, Math.min(100, ((elo - min) / (max - min)) * 100))
  return (
    <div className="h-1 bg-border-dim rounded-full overflow-hidden w-20">
      <div
        className="h-full rounded-full bg-gradient-to-r from-cyan-600 to-cyan-400"
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

function rankColor(rank: number): string {
  if (rank === 1) return 'text-amber-400'
  if (rank === 2) return 'text-slate-400'
  if (rank === 3) return 'text-amber-700'
  return 'text-slate-600'
}

export function EloLeaderboard({ ratings }: Props) {
  return (
    <div className="rounded-lg border border-border-dim overflow-hidden">
      {/* Table header */}
      <div className="grid grid-cols-[2.5rem_1fr_5rem_5rem] gap-2 px-3 py-2 bg-white/[0.02] border-b border-border-dim">
        <span className="text-[10px] font-semibold text-slate-600 uppercase tracking-wider">#</span>
        <span className="text-[10px] font-semibold text-slate-600 uppercase tracking-wider">Team</span>
        <span className="text-[10px] font-semibold text-slate-600 uppercase tracking-wider text-right">Elo</span>
        <span className="text-[10px] font-semibold text-slate-600 uppercase tracking-wider"></span>
      </div>

      {/* Table body */}
      <div className="divide-y divide-border-dim max-h-64 overflow-y-auto scrollbar-thin">
        {ratings.map((r) => (
          <div
            key={r.team_name}
            className="grid grid-cols-[2.5rem_1fr_5rem_5rem] gap-2 items-center px-3 py-2.5 hover:bg-white/[0.02] transition-colors"
          >
            <span className={`text-xs font-bold font-mono ${rankColor(r.rank)}`}>
              {r.rank}
            </span>
            <span className="text-sm text-slate-300 font-medium truncate">{r.team_name}</span>
            <span className="text-sm font-mono text-cyan-400 text-right font-semibold">
              {Math.round(r.elo)}
            </span>
            <div className="flex justify-end">
              <EloBar elo={r.elo} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
