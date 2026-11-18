import "flag-icons/css/flag-icons.min.css";
import type { EloRating } from "../api/client";

interface Props {
  ratings: EloRating[];
}

const COLS =
  "grid-cols-[1.5rem_1.25rem_minmax(0,1fr)_5.5rem_2.75rem] sm:grid-cols-[3rem_4rem_minmax(0,1fr)_minmax(0,1.4fr)_4rem_7rem]";

function EloBar({ elo }: { elo: number }) {
  const min = 1350;
  const max = 1700;
  const pct = Math.max(0, Math.min(100, ((elo - min) / (max - min)) * 100));
  return (
    <div aria-hidden="true" className="h-2 w-full -skew-x-[18deg] bg-line">
      <div className="h-full bg-ice-deep" style={{ width: `${pct}%` }} />
    </div>
  );
}

function Flag({ code }: { code: string | null }) {
  if (!code) {
    return (
      <span
        aria-hidden="true"
        className="inline-block h-[15px] w-5 shrink-0 rounded-[2px] border border-dashed border-line-bright"
      />
    );
  }
  return (
    <span
      role="img"
      aria-label={`Flag: ${code.toUpperCase()}`}
      className={`fi fi-${code} !h-[15px] !w-5 shrink-0 rounded-[2px] !bg-cover`}
    />
  );
}

export function EloLeaderboard({ ratings }: Props) {
  return (
    <div className="overflow-hidden rounded-md border border-line bg-deep">
      <div className={`grid ${COLS} gap-3 border-b border-line px-3 py-2`}>
        <span className="eyebrow">#</span>
        <span className="eyebrow">
          <span className="sr-only sm:not-sr-only">Country</span>
        </span>
        <span className="eyebrow">Team</span>
        <span className="eyebrow">Roster</span>
        <span className="eyebrow text-right">Elo</span>
        <span className="eyebrow hidden sm:block" aria-hidden="true" />
      </div>

      <ol className="divide-y divide-line">
        {ratings.map((r) => (
          <li
            key={r.team_name}
            className={`grid ${COLS} items-center gap-3 px-3 py-2.5 transition-colors hover:bg-raised`}
          >
            <span
              className={`num text-lg ${r.rank <= 3 ? "text-boost" : "text-muted"}`}
            >
              {r.rank}
            </span>
            <Flag code={r.country} />
            <span className="truncate font-display text-lg font-bold uppercase tracking-wide text-ink">
              {r.team_name}
            </span>
            <ul
              aria-label="Roster"
              className="flex min-w-0 flex-col text-sm leading-tight text-muted sm:flex-row sm:flex-wrap sm:gap-x-1.5"
            >
              {r.roster.map((name, i) => (
                <li
                  key={name}
                  className="truncate sm:after:ml-1.5 sm:after:content-['·'] sm:last:after:content-none"
                >
                  {name}
                  <span className="sr-only">{i < r.roster.length - 1 ? "," : ""}</span>
                </li>
              ))}
            </ul>
            <span className="num text-right text-lg text-ink">
              {Math.round(r.elo)}
            </span>
            <div className="hidden pr-2 sm:block">
              <EloBar elo={r.elo} />
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
