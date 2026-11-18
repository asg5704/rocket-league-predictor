import { AlertTriangle, Info, Trophy } from "lucide-react";
import type { Lineup } from "../api/client";
import { ArchetypeBadge } from "./ArchetypeBadge";
import { SegmentMeter } from "./SegmentMeter";

interface Props {
  lineup: Lineup;
}

const toFraction = (value: number, max: number) =>
  (value + max) / (2 * max);

function MeterRow({
  label,
  value,
  children,
}: {
  label: string;
  value: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <span className="eyebrow">{label}</span>
        <span className="num text-base text-ink">{value}</span>
      </div>
      {children}
    </div>
  );
}

export function LineupCard({ lineup }: Props) {
  const isTop = lineup.rank === 1;
  // n_matches === 0 means the trio never played together; the backend
  // returns synergy 0.0 as a placeholder, which would read as a real score.
  const hasHistory = lineup.n_matches > 0;
  const synergyText = `${lineup.synergy >= 0 ? "+" : ""}${lineup.synergy.toFixed(3)}`;
  const eloText = String(Math.round(lineup.mean_elo));

  return (
    <article
      aria-label={`Rank ${lineup.rank} lineup`}
      className={`animate-slide-up rounded-[10px] border bg-surface p-5 transition-colors hover:border-line-bright ${
        isTop ? "border-boost border-l-[10px]" : "border-line"
      }`}
    >
      <div className="grid gap-6 md:grid-cols-[1fr_minmax(0,22rem)]">
        {/* Identity + composite score */}
        <div className="flex flex-col justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              {isTop && (
                <Trophy size={18} className="text-boost" aria-hidden="true" />
              )}
              <span
                className={`num text-xl ${isTop ? "text-boost" : "text-muted"}`}
              >
                #{lineup.rank}
              </span>
              <span className="eyebrow">
                {lineup.archetype_combo.replace(/\+/g, " · ")}
              </span>
            </div>
            <ul className="mt-2 flex flex-col gap-1.5">
              {lineup.players.map((p) => (
                <li key={p.player_id} className="flex items-center gap-3">
                  <span className="font-display text-2xl font-extrabold uppercase leading-tight tracking-wide text-ink">
                    {p.display_name}
                  </span>
                  <ArchetypeBadge archetype={p.archetype} />
                </li>
              ))}
            </ul>
          </div>
          <div>
            <div className="num text-6xl leading-none text-boost">
              {lineup.score.toFixed(3)}
            </div>
            <div className="eyebrow mt-1">Composite score</div>
          </div>
        </div>

        {/* Explainable breakdown */}
        <div className="flex flex-col justify-center gap-3">
          {hasHistory && (
          <MeterRow label="Synergy" value={synergyText}>
            <SegmentMeter
              label="Synergy"
              valueText={synergyText}
              fraction={toFraction(lineup.synergy, 0.2)}
              tone={lineup.synergy >= 0 ? "boost" : "bad"}
              size="lg"
            />
          </MeterRow>
          )}
          <MeterRow label="Archetype bonus" value={lineup.archetype_bonus.toFixed(2)}>
            <SegmentMeter
              label="Archetype bonus"
              valueText={lineup.archetype_bonus.toFixed(2)}
              fraction={toFraction(lineup.archetype_bonus, 0.5)}
            />
          </MeterRow>
          <MeterRow label="Avg Elo" value={eloText}>
            <SegmentMeter
              label="Average Elo"
              valueText={eloText}
              fraction={toFraction(lineup.mean_elo - 1500, 200)}
            />
          </MeterRow>
        </div>
      </div>

      {!hasHistory ? (
        <div
          role="note"
          className="mt-4 flex items-center gap-2 rounded-md border border-line-bright bg-deep px-3 py-2 text-sm text-body"
        >
          <Info size={14} aria-hidden="true" />
          No shared match history: ranked on archetype and Elo only.
        </div>
      ) : (
        lineup.low_sample && (
          <div
            role="note"
            className="mt-4 flex items-center gap-2 rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-sm text-warn"
          >
            <AlertTriangle size={14} aria-hidden="true" />
            Low sample ({lineup.n_matches} matches): treat with caution
          </div>
        )
      )}
    </article>
  );
}
