import { useState, useMemo } from 'react'
import { Search, X, Users } from 'lucide-react'
import type { Player } from '../api/client'
import { ArchetypeBadge } from './ArchetypeBadge'

interface Props {
  players: Player[]
  selected: Set<string>
  onToggle: (id: string) => void
  onClear: () => void
}

const ARCHETYPE_FILTERS = ['all', 'striker', 'anchor', 'flex'] as const
type ArchetypeFilter = (typeof ARCHETYPE_FILTERS)[number]

export function PlayerPicker({ players, selected, onToggle, onClear }: Props) {
  const [search, setSearch] = useState('')
  const [archetypeFilter, setArchetypeFilter] = useState<ArchetypeFilter>('all')

  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    return players.filter((p) => {
      const matchSearch =
        !q ||
        p.display_name.toLowerCase().includes(q) ||
        (p.team_name?.toLowerCase().includes(q) ?? false)
      const matchArchetype =
        archetypeFilter === 'all' || p.archetype === archetypeFilter
      return matchSearch && matchArchetype
    })
  }, [players, search, archetypeFilter])

  const selectedCount = selected.size

  return (
    <div className="flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Users size={16} className="text-cyan-400" />
          <span className="text-sm font-semibold text-slate-200">Player Pool</span>
          <span className="text-xs text-slate-500">({selectedCount} selected)</span>
        </div>
        {selectedCount > 0 && (
          <button
            onClick={onClear}
            className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
          >
            <X size={12} />
            Clear all
          </button>
        )}
      </div>

      {/* Search */}
      <div className="relative">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search players or teams..."
          className="w-full bg-surface border border-border-dim rounded-lg pl-9 pr-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/20 transition-all"
        />
      </div>

      {/* Archetype filter pills */}
      <div className="flex gap-1.5">
        {ARCHETYPE_FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setArchetypeFilter(f)}
            className={`px-3 py-1 rounded-full text-xs font-medium border transition-all ${
              archetypeFilter === f
                ? 'bg-cyan-500/20 text-cyan-400 border-cyan-500/50'
                : 'bg-transparent text-slate-500 border-border-dim hover:border-border-bright hover:text-slate-400'
            }`}
          >
            {f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Player list */}
      <div className="overflow-y-auto scrollbar-thin rounded-lg border border-border-dim bg-surface max-h-56 sm:max-h-72 lg:max-h-96">
        {filtered.length === 0 ? (
          <div className="py-8 text-center text-sm text-slate-600">No players found</div>
        ) : (
          <div className="divide-y divide-border-dim">
            {filtered.map((player) => {
              const isSelected = selected.has(player.player_id)
              return (
                <button
                  key={player.player_id}
                  onClick={() => onToggle(player.player_id)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 text-left transition-all hover:bg-white/[0.03] ${
                    isSelected ? 'bg-cyan-500/[0.06]' : ''
                  }`}
                >
                  {/* Checkbox */}
                  <div
                    className={`w-4 h-4 rounded border flex-shrink-0 flex items-center justify-center transition-all ${
                      isSelected
                        ? 'bg-cyan-500 border-cyan-500'
                        : 'border-border-bright bg-transparent'
                    }`}
                  >
                    {isSelected && (
                      <svg viewBox="0 0 10 8" className="w-2.5 h-2 text-bg fill-current">
                        <path d="M1 4l3 3 5-6" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    )}
                  </div>

                  {/* Player info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-medium truncate ${isSelected ? 'text-cyan-300' : 'text-slate-200'}`}>
                        {player.display_name}
                      </span>
                      <ArchetypeBadge archetype={player.archetype} />
                    </div>
                    <div className="text-xs text-slate-600 truncate mt-0.5">
                      {player.team_name ?? 'Unknown team'}
                    </div>
                  </div>

                  {/* Elo */}
                  <div className="text-right flex-shrink-0">
                    <div className="text-xs font-mono text-slate-400">{Math.round(player.elo)}</div>
                    <div className="text-[10px] text-slate-700">Elo</div>
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
