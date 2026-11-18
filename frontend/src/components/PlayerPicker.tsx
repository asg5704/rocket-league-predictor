import { useState, useMemo } from "react";
import { Search, X, Check } from "lucide-react";
import type { Player } from "../api/client";
import { ArchetypeBadge } from "./ArchetypeBadge";

interface Props {
  players: Player[];
  selected: Set<string>;
  onToggle: (id: string) => void;
  onClear: () => void;
}

const ARCHETYPE_FILTERS = ["all", "striker", "anchor", "flex"] as const;

export function PlayerPicker({ players, selected, onToggle, onClear }: Props) {
  const [search, setSearch] = useState("");
  const [archetypeFilter, setArchetypeFilter] = useState<string>("all");

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return players.filter((p) => {
      const matchSearch =
        !q ||
        p.display_name.toLowerCase().includes(q) ||
        (p.team_name?.toLowerCase().includes(q) ?? false);
      const matchArchetype =
        archetypeFilter === "all" || p.archetype === archetypeFilter;
      return matchSearch && matchArchetype;
    });
  }, [players, search, archetypeFilter]);

  const selectedCount = selected.size;

  return (
    <div className="flex flex-col gap-3">
      <h2 className="sr-only">Player pool</h2>
      {selectedCount > 0 && (
        <button
          onClick={onClear}
          className="flex min-h-9 items-center gap-1 self-end px-2 text-sm text-muted transition-colors hover:text-ink"
        >
          <X size={14} aria-hidden="true" />
          Clear all
        </button>
      )}

      <div className="relative">
        <label htmlFor="player-search" className="sr-only">
          Search players or teams
        </label>
        <Search
          size={16}
          aria-hidden="true"
          className="absolute left-3 top-1/2 -translate-y-1/2 text-muted"
        />
        <input
          id="player-search"
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search players or teams…"
          className="min-h-11 w-full rounded-md border border-line bg-deep py-2 pl-9 pr-3 text-base text-ink placeholder:text-muted transition-colors hover:border-line-bright focus:border-boost"
        />
      </div>

      <div role="group" aria-label="Filter by archetype" className="flex flex-wrap gap-1.5">
        {ARCHETYPE_FILTERS.map((type) => {
          const active = archetypeFilter === type;
          return (
            <button
              key={type}
              aria-pressed={active}
              onClick={() => setArchetypeFilter(type)}
              className={`min-h-9 -skew-x-[12deg] border px-3 font-display text-sm font-bold uppercase tracking-wider transition-colors ${
                active
                  ? "border-boost bg-boost text-deep"
                  : "border-line text-body hover:border-line-bright hover:bg-raised"
              }`}
            >
              <span className="inline-block skew-x-[12deg]">{type}</span>
            </button>
          );
        })}
      </div>

      <div className="scrollbar-thin max-h-72 overflow-y-auto rounded-md border border-line bg-deep lg:max-h-[28rem]">
        {filtered.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted">
            No players found
          </div>
        ) : (
          <ul className="divide-y divide-line">
            {filtered.map((player) => {
              const isSelected = selected.has(player.player_id);
              return (
                <li key={player.player_id}>
                  <button
                    role="checkbox"
                    aria-checked={isSelected}
                    onClick={() => onToggle(player.player_id)}
                    className={`flex min-h-14 w-full items-center gap-3 px-3 py-2 text-left transition-colors hover:bg-raised ${
                      isSelected
                        ? "bg-raised ring-1 ring-inset ring-boost/70"
                        : ""
                    }`}
                  >
                    <span
                      aria-hidden="true"
                      className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-[3px] border transition-colors ${
                        isSelected
                          ? "border-boost bg-boost text-deep"
                          : "border-line-bright"
                      }`}
                    >
                      {isSelected && <Check size={14} strokeWidth={3} />}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-2">
                        <span className="truncate font-display text-lg font-bold uppercase tracking-wide text-ink">
                          {player.display_name}
                        </span>
                        <ArchetypeBadge archetype={player.archetype} />
                      </span>
                      <span className="block truncate text-sm text-muted">
                        {player.team_name ?? "Free agent"}
                      </span>
                    </span>
                    <span className="shrink-0 text-right">
                      <span className="num block text-lg text-ink">
                        {Math.round(player.elo)}
                      </span>
                      <span className="eyebrow block text-[0.6875rem]">Elo</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
