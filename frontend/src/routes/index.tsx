import { createFileRoute } from "@tanstack/react-router";
import { useState, useCallback } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import {
  Zap,
  RotateCcw,
  ChevronRight,
  Loader2,
  SearchX,
} from "lucide-react";
import { api, type Weights } from "../api/client";
import { useQuery, useMutation } from "../hooks/useApi";
import { PlayerPicker } from "../components/PlayerPicker";
import { WeightSliders } from "../components/WeightSliders";
import { LineupCard } from "../components/LineupCard";
import {
  PlayerListSkeleton,
  LineupCardSkeleton,
} from "../components/Skeleton";

export const Route = createFileRoute("/")({
  component: Index,
});

const DEFAULT_WEIGHTS: Weights = { synergy: 1.0, archetype: 0.5, elo: 0.3 };
const TOP_K = 5;

const SIDE_TAB =
  "min-h-12 px-4 font-display text-lg font-bold uppercase tracking-wider text-muted transition-colors hover:bg-surface hover:text-ink data-[state=active]:bg-surface data-[state=active]:text-ink data-[state=active]:shadow-[inset_0_-3px_0_var(--color-boost)]";

function Index() {
  const {
    data: playersData,
    loading: playersLoading,
    error: playersError,
  } = useQuery(() => api.getPlayers());
  const {
    data: results,
    loading: optimizing,
    error: optimizeError,
    execute: runOptimize,
  } = useMutation(api.optimize);

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [weights, setWeights] = useState<Weights>(DEFAULT_WEIGHTS);

  const togglePlayer = useCallback((id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }

      return next;
    });
  }, []);

  const clearAll = useCallback(() => setSelected(new Set()), []);

  const handleOptimize = useCallback(() => {
    if (selected.size < 3) return;
    runOptimize([...selected], TOP_K, weights);
  }, [selected, weights, runOptimize]);

  const canOptimize = selected.size >= 3;

  return (
    <div className="mx-auto grid w-full max-w-7xl grid-cols-1 items-start gap-6 px-4 py-6 lg:grid-cols-[360px_1fr] lg:px-6">
      {/* Left sidebar */}
      <aside className="flex flex-col gap-4 lg:sticky lg:top-24">
        <Tabs.Root defaultValue="players" className="panel overflow-hidden">
          <Tabs.List
            aria-label="Optimizer setup"
            className="grid grid-cols-2 border-b border-line bg-deep"
          >
            <Tabs.Trigger value="players" className={SIDE_TAB}>
              Players
              <span className="num ml-1.5 text-base opacity-80">
                {selected.size}
              </span>
            </Tabs.Trigger>
            <Tabs.Trigger value="weights" className={SIDE_TAB}>
              Weights
            </Tabs.Trigger>
          </Tabs.List>
          {/* forceMount keeps search/filter state when switching tabs */}
          <Tabs.Content
            value="players"
            forceMount
            className="p-4 data-[state=inactive]:hidden"
          >
            {playersLoading ? (
            <div className="flex flex-col gap-3" aria-busy="true">
              <div className="flex items-center justify-between">
                <div className="skeleton-shimmer h-5 w-28 rounded" />
                <div className="skeleton-shimmer h-4 w-16 rounded" />
              </div>
              <div className="skeleton-shimmer h-11 w-full rounded-md" />
              <div className="flex gap-1.5">
                {[0, 1, 2, 3].map((i) => (
                  <div key={i} className="skeleton-shimmer h-9 w-16 rounded" />
                ))}
              </div>
              <div className="overflow-hidden rounded-md border border-line bg-deep">
                <PlayerListSkeleton />
              </div>
            </div>
          ) : playersError ? (
            <div role="alert" className="py-4">
              <p className="mb-1 font-semibold text-bad">
                Failed to connect to API.
              </p>
              <p className="text-sm text-muted">Retry in a few minutes.</p>
            </div>
          ) : (
            <PlayerPicker
              players={playersData!.players}
              selected={selected}
              onToggle={togglePlayer}
              onClear={clearAll}
            />
          )}
          </Tabs.Content>
          <Tabs.Content
            value="weights"
            forceMount
            className="p-4 data-[state=inactive]:hidden"
          >
            <WeightSliders weights={weights} onChange={setWeights} />
            <button
              onClick={() => setWeights(DEFAULT_WEIGHTS)}
              className="mt-4 flex min-h-9 items-center gap-1.5 text-sm text-muted transition-colors hover:text-ink"
            >
              <RotateCcw size={14} aria-hidden="true" />
              Reset to defaults
            </button>
          </Tabs.Content>
        </Tabs.Root>

        <button
          onClick={handleOptimize}
          disabled={!canOptimize || optimizing}
          className={`flex min-h-14 w-full items-center justify-center gap-2 -skew-x-[6deg] font-display text-xl font-extrabold uppercase tracking-wider transition-colors ${
            canOptimize && !optimizing
              ? "bg-boost text-deep hover:bg-boost-hot"
              : "bg-line text-muted"
          }`}
        >
          <span className="inline-flex skew-x-[6deg] items-center gap-2">
            {optimizing ? (
              <>
                <Loader2 size={18} className="animate-spin" aria-hidden="true" />
                Optimizing…
              </>
            ) : (
              <>
                <Zap size={18} aria-hidden="true" />
                {canOptimize
                  ? `Find best lineups (${selected.size})`
                  : "Select at least 3 players"}
                {canOptimize && <ChevronRight size={18} aria-hidden="true" />}
              </>
            )}
          </span>
        </button>
      </aside>

      {/* Right content */}
      <div className="flex min-w-0 flex-col gap-6">
        {optimizeError && (
          <div
            role="alert"
            className="rounded-[10px] border border-bad/50 bg-bad/10 p-4 text-bad"
          >
            {optimizeError}
          </div>
        )}

        {optimizing && (
          <section
            aria-busy="true"
            aria-label="Optimizing lineups"
            className="flex flex-col gap-4"
          >
            <div className="skeleton-shimmer h-6 w-48 rounded" />
            <div className="flex flex-col gap-3">
              {Array.from({ length: TOP_K }).map((_, i) => (
                <LineupCardSkeleton key={i} />
              ))}
            </div>
          </section>
        )}

        {/* Results lead; leaderboard follows */}
        {!optimizing && results && results.lineups.length > 0 && (
          <section className="flex animate-fade-in flex-col gap-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="font-display text-3xl font-extrabold uppercase tracking-wide text-ink">
                Top {results.lineups.length} lineups
                <span className="ml-2 text-lg font-semibold text-muted">
                  from {results.pool_size}-player pool
                </span>
              </h2>
              <span className="num hidden text-base text-muted sm:inline">
                {Math.round(
                  (results.pool_size *
                    (results.pool_size - 1) *
                    (results.pool_size - 2)) /
                    6,
                )}{" "}
                combinations evaluated
              </span>
            </div>
            <div className="flex flex-col gap-4">
              {results.lineups.map((lineup) => (
                <LineupCard key={lineup.rank} lineup={lineup} />
              ))}
            </div>
          </section>
        )}

        {!optimizing && results && results.lineups.length === 0 && (
          <div className="flex animate-fade-in flex-col items-center justify-center py-16 text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl border border-line bg-surface">
              <SearchX size={24} className="text-muted" aria-hidden="true" />
            </div>
            <p className="mb-1 font-display text-2xl font-bold uppercase text-ink">
              No valid lineups found
            </p>
            <p className="max-w-xs text-muted">
              Try adding more players to the pool, or check that their synergy
              data is available.
            </p>
          </div>
        )}

        {!results && !optimizing && (
          <div className="panel flex animate-fade-in flex-col items-center justify-center px-6 py-14 text-center">
            <div className="mb-4 flex h-16 w-16 -skew-x-[12deg] items-center justify-center bg-boost">
              <Zap
                size={30}
                className="skew-x-[12deg] text-deep"
                aria-hidden="true"
              />
            </div>
            <h2 className="mb-2 font-display text-3xl font-extrabold uppercase tracking-wide text-ink">
              Build your trio
            </h2>
            <p className="max-w-sm text-body">
              Pick at least three pros from the pool, tune the score weights,
              then hit{" "}
              <strong className="text-ink">Find best lineups</strong> to rank
              every possible trio.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
