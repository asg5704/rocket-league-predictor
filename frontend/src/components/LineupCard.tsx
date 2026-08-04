import { AlertTriangle, Trophy } from 'lucide-react'
import type { Lineup } from '../api/client'
import { ArchetypeBadge } from './ArchetypeBadge'

interface Props {
  lineup: Lineup
}

function ScoreBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = Math.max(0, Math.min(100, ((value + max) / (2 * max)) * 100))
  return (
    <div className="h-1 bg-border-dim rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full transition-all ${color}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

const RANK_COLORS = ['text-amber-400', 'text-slate-400', 'text-amber-700', 'text-slate-500', 'text-slate-600']
const RANK_BG = [
  'border-amber-500/30 bg-amber-500/5',
  'border-slate-500/30 bg-slate-500/5',
  'border-amber-700/30 bg-amber-700/5',
]

export function LineupCard({ lineup }: Props) {
  const rankColor = RANK_COLORS[lineup.rank - 1] ?? 'text-slate-600'
  const rankBg = RANK_BG[lineup.rank - 1] ?? 'border-border-dim bg-surface'

  return (
    <div className={`rounded-xl border p-4 flex flex-col gap-3 animate-slide-up transition-all hover:border-border-bright ${rankBg}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {lineup.rank === 1 && <Trophy size={14} className="text-amber-400" />}
          <span className={`text-lg font-bold font-mono ${rankColor}`}>
            #{lineup.rank}
          </span>
          <span className="text-xs text-slate-600 font-medium capitalize">
            {lineup.archetype_combo.replace(/\+/g, ' · ')}
          </span>
        </div>
        <div className="text-right">
          <div className="text-lg font-bold font-mono text-cyan-400 text-glow-cyan">
            {lineup.score.toFixed(3)}
          </div>
          <div className="text-[10px] text-slate-600 uppercase tracking-wide">score</div>
        </div>
      </div>

      {/* Players */}
      <div className="flex flex-col gap-1.5">
        {lineup.players.map((p) => (
          <div key={p.player_id} className="flex items-center justify-between">
            <span className="text-sm font-medium text-slate-200">{p.display_name}</span>
            <ArchetypeBadge archetype={p.archetype} />
          </div>
        ))}
      </div>

      {/* Score breakdown */}
      <div className="grid grid-cols-3 gap-2 pt-1 border-t border-border-dim">
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-slate-600 uppercase tracking-wide">Synergy</span>
            <span className={`text-xs font-mono font-semibold ${lineup.synergy >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {lineup.synergy >= 0 ? '+' : ''}{lineup.synergy.toFixed(3)}
            </span>
          </div>
          <ScoreBar value={lineup.synergy} max={0.2} color={lineup.synergy >= 0 ? 'bg-emerald-500' : 'bg-rose-500'} />
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-slate-600 uppercase tracking-wide">Archetype</span>
            <span className="text-xs font-mono font-semibold text-violet-400">
              {lineup.archetype_bonus.toFixed(2)}
            </span>
          </div>
          <ScoreBar value={lineup.archetype_bonus} max={0.5} color="bg-violet-500" />
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-slate-600 uppercase tracking-wide">Avg Elo</span>
            <span className="text-xs font-mono font-semibold text-cyan-400">
              {Math.round(lineup.mean_elo)}
            </span>
          </div>
          <ScoreBar value={lineup.mean_elo - 1500} max={200} color="bg-cyan-500" />
        </div>
      </div>

      {/* Warnings */}
      {lineup.low_sample && (
        <div className="flex items-center gap-1.5 text-[11px] text-amber-500/80 bg-amber-500/5 border border-amber-500/20 rounded-lg px-2.5 py-1.5">
          <AlertTriangle size={11} />
          Low sample ({lineup.n_matches} matches) — treat with caution
        </div>
      )}
    </div>
  )
}
