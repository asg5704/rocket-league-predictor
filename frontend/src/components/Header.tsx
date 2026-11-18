import { Rocket } from "lucide-react";
import { Link } from "@tanstack/react-router";

const NAV_LINK =
  "relative px-1 py-2 font-display text-base font-bold uppercase tracking-wider text-muted transition-colors hover:text-ink [&.active]:text-ink after:absolute after:inset-x-0 after:-bottom-[1px] after:h-[3px] after:bg-boost after:origin-left after:scale-x-0 after:transition-transform [&.active]:after:scale-x-100";

export default function Header() {
  return (
    <header className="sticky top-0 z-20 border-b-4 border-boost bg-deep">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-2 focus:rounded focus:bg-boost focus:px-3 focus:py-1 focus:font-semibold focus:text-deep"
      >
        Skip to content
      </a>
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 lg:px-6">
        <Link to="/" className="flex min-w-0 items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 -skew-x-[12deg] items-center justify-center bg-boost">
            <Rocket
              size={18}
              className="skew-x-[12deg] text-deep"
              aria-hidden="true"
            />
          </span>
          <span className="min-w-0">
            <span className="block truncate font-display text-xl font-extrabold uppercase leading-none tracking-wide text-ink sm:text-2xl">
              RLCS Roster Optimizer
            </span>
            <span className="mt-0.5 hidden text-xs text-muted sm:block">
              Synergy · Archetypes · Elo
            </span>
          </span>
        </Link>
        <nav aria-label="Primary" className="flex shrink-0 items-center gap-4 sm:gap-6">
          <Link to="/" className={NAV_LINK}>
            Optimizer
          </Link>
          <Link to="/leaderboard" className={NAV_LINK}>
            Leaderboard
          </Link>
          <Link to="/about" className={NAV_LINK}>
            About
          </Link>
        </nav>
      </div>
    </header>
  );
}
