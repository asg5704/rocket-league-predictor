import { useState, useCallback } from 'react'
import { Zap, RotateCcw, ChevronRight, Loader2, SearchX, TrendingUp } from 'lucide-react'
import { api, type Weights } from './api/client'
import { useQuery, useMutation } from './hooks/useApi'
import { PlayerPicker } from './components/PlayerPicker'
import { WeightSliders } from './components/WeightSliders'
import { LineupCard } from './components/LineupCard'
import { EloLeaderboard } from './components/EloLeaderboard'
import { PlayerListSkeleton, LeaderboardSkeleton, LineupCardSkeleton } from './components/Skeleton'
import { HelpModal } from './components/HelpModal'

const DEFAULT_WEIGHTS: Weights = { synergy: 1.0, archetype: 0.5, elo: 0.3 }
const TOP_K = 5

export default function App() {
  const { data: playersData, loading: playersLoading, error: playersError } = useQuery(() => api.getPlayers())
  const { data: eloData, loading: eloLoading } = useQuery(() => api.getEloRatings())
  const { data: results, loading: optimizing, error: optimizeError, execute: runOptimize } = useMutation(api.optimize)

  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [weights, setWeights] = useState<Weights>(DEFAULT_WEIGHTS)

  const togglePlayer = useCallback((id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const clearAll = useCallback(() => setSelected(new Set()), [])

  const handleOptimize = useCallback(() => {
    if (selected.size < 3) return
    runOptimize([...selected], TOP_K, weights)
  }, [selected, weights, runOptimize])

  const canOptimize = selected.size >= 3

  return (
    <div className="min-h-screen bg-bg text-slate-200 flex flex-col">
      {/* Header */}
      <header className="border-b border-border-dim bg-surface/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 lg:px-6 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center flex-shrink-0">
              <Zap size={16} className="text-cyan-400" />
            </div>
            <div className="min-w-0">
              <h1 className="text-base font-bold text-white leading-none truncate">RLCS Lineup Optimizer</h1>
              <p className="text-xs text-slate-600 mt-0.5 hidden sm:block">Synergy scores · Archetypes · Elo</p>
            </div>
          </div>
          <div className="flex items-center gap-4 flex-shrink-0">
            <HelpModal />
            <div className="flex items-center gap-2 text-xs text-slate-600">
              <div className={`w-1.5 h-1.5 rounded-full ${playersData ? 'bg-emerald-500' : 'bg-slate-700'}`} />
              <span className="hidden sm:inline">
                {playersLoading ? 'Connecting...' : playersData ? `${playersData.total} players loaded` : 'API offline'}
              </span>
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-7xl mx-auto w-full px-4 lg:px-6 py-6 grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-6 items-start">
        {/* Left sidebar */}
        <aside className="flex flex-col gap-4 lg:sticky lg:top-20">
          {/* Player picker */}
          <div className="rounded-xl border border-border-dim bg-surface p-4">
            {playersLoading ? (
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <div className="skeleton-shimmer h-4 w-24 rounded" />
                  <div className="skeleton-shimmer h-3 w-16 rounded" />
                </div>
                <div className="skeleton-shimmer h-9 w-full rounded-lg" />
                <div className="flex gap-1.5">
                  {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton-shimmer h-6 w-14 rounded-full" />)}
                </div>
                <div className="rounded-lg border border-border-dim bg-surface overflow-hidden">
                  <PlayerListSkeleton />
                </div>
              </div>
            ) : playersError ? (
              <div className="py-4">
                <p className="text-sm text-rose-400 mb-2">Failed to connect to API.</p>
                <p className="text-xs text-slate-600">Start the backend:</p>
                <code className="text-xs text-slate-500 block mt-1">PYTHONPATH=. uvicorn src.api.main:app --reload</code>
              </div>
            ) : (
              <PlayerPicker
                players={playersData!.players}
                selected={selected}
                onToggle={togglePlayer}
                onClear={clearAll}
              />
            )}
          </div>

          {/* Weight sliders */}
          <div className="rounded-xl border border-border-dim bg-surface p-4">
            <WeightSliders weights={weights} onChange={setWeights} />
            <button
              onClick={() => setWeights(DEFAULT_WEIGHTS)}
              className="mt-4 flex items-center gap-1.5 text-xs text-slate-700 hover:text-slate-500 transition-colors"
            >
              <RotateCcw size={11} />
              Reset to defaults
            </button>
          </div>

          {/* Optimize button */}
          <button
            onClick={handleOptimize}
            disabled={!canOptimize || optimizing}
            className={`flex items-center justify-center gap-2 w-full py-3 rounded-xl font-semibold text-sm transition-all ${
              canOptimize && !optimizing
                ? 'bg-cyan-500 hover:bg-cyan-400 text-bg cursor-pointer'
                : 'bg-border-dim text-slate-600 cursor-not-allowed'
            }`}
          >
            {optimizing ? (
              <>
                <Loader2 size={15} className="animate-spin" />
                Optimizing...
              </>
            ) : (
              <>
                <Zap size={15} />
                {canOptimize
                  ? `Find Best Lineups (${selected.size} players)`
                  : 'Select at least 3 players'}
                {canOptimize && <ChevronRight size={14} />}
              </>
            )}
          </button>
        </aside>

        {/* Right content */}
        <div className="flex flex-col gap-6">
          {/* Error */}
          {optimizeError && (
            <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-4 text-sm text-rose-400">
              {optimizeError}
            </div>
          )}

          {/* Optimizing — skeleton cards */}
          {optimizing && (
            <section className="flex flex-col gap-4">
              <div className="skeleton-shimmer h-4 w-40 rounded" />
              <div className="flex flex-col gap-3">
                {Array.from({ length: TOP_K }).map((_, i) => <LineupCardSkeleton key={i} />)}
              </div>
            </section>
          )}

          {/* Results */}
          {!optimizing && results && results.lineups.length > 0 && (
            <section className="flex flex-col gap-4 animate-fade-in">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-slate-300">
                  Top {results.lineups.length} Lineups
                  <span className="ml-1.5 text-slate-600 font-normal">
                    from {results.pool_size}-player pool
                  </span>
                </h2>
                <span className="text-xs text-slate-700 font-mono hidden sm:inline">
                  {Math.round(results.pool_size * (results.pool_size - 1) * (results.pool_size - 2) / 6)} combinations evaluated
                </span>
              </div>
              <div className="flex flex-col gap-3">
                {results.lineups.map((lineup) => (
                  <LineupCard key={lineup.rank} lineup={lineup} />
                ))}
              </div>
            </section>
          )}

          {/* Zero-results empty state */}
          {!optimizing && results && results.lineups.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-center animate-fade-in">
              <div className="w-14 h-14 rounded-2xl bg-surface border border-border-dim flex items-center justify-center mb-4">
                <SearchX size={24} className="text-slate-600" />
              </div>
              <p className="text-slate-500 text-sm font-medium mb-1">No valid lineups found</p>
              <p className="text-slate-600 text-xs max-w-xs leading-relaxed">
                Try adding more players to the pool, or check that their synergy data is available.
              </p>
            </div>
          )}

          {/* Initial empty state */}
          {!results && !optimizing && (
            <div className="flex flex-col items-center justify-center py-16 sm:py-24 text-center animate-fade-in">
              <div className="w-16 h-16 rounded-2xl bg-surface border border-border-dim flex items-center justify-center mb-4">
                <Zap size={28} className="text-border-bright" />
              </div>
              <p className="text-slate-600 text-sm max-w-xs leading-relaxed">
                Select players from the pool on the left, adjust score weights, then hit{' '}
                <span className="text-slate-500 font-medium">Find Best Lineups</span>.
              </p>
            </div>
          )}

          {/* Elo leaderboard — always visible */}
          <div className="rounded-xl border border-border-dim bg-surface p-4">
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp size={16} className="text-cyan-400" />
              <span className="text-sm font-semibold text-slate-200">Elo Leaderboard</span>
              {!eloLoading && eloData && (
                <span className="text-xs text-slate-500">({eloData.total} teams)</span>
              )}
            </div>
            {eloLoading ? (
              <div className="rounded-lg border border-border-dim overflow-hidden">
                <LeaderboardSkeleton />
              </div>
            ) : eloData ? (
              <EloLeaderboard ratings={eloData.ratings} />
            ) : null}
          </div>
        </div>
      </main>
    </div>
  )
}
