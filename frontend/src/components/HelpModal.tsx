import * as Dialog from "@radix-ui/react-dialog";
import {
  HelpCircle,
  X,
  MousePointerClick,
  SlidersHorizontal,
  Zap,
  TrendingUp,
  AlertTriangle,
} from "lucide-react";

function Section({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <div className="text-cyan-400">{icon}</div>
        <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
      </div>
      <div className="pl-6 flex flex-col gap-1.5 text-xs text-slate-400 leading-relaxed">
        {children}
      </div>
    </div>
  );
}

function Pill({ label, color }: { label: string; color: string }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full border text-[11px] font-medium ${color}`}
    >
      {label}
    </span>
  );
}

function Metric({
  label,
  color,
  children,
}: {
  label: string;
  color: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-2">
      <span className={`font-semibold flex-shrink-0 ${color}`}>{label}</span>
      <span>{children}</span>
    </div>
  );
}

export function HelpModal() {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <button
          className="flex items-center gap-1.5 text-xs text-slate-600 hover:text-slate-400 transition-colors"
          aria-label="How to use"
        >
          <HelpCircle size={15} />
          <span className="hidden sm:inline">How to use</span>
        </button>
      </Dialog.Trigger>

      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 animate-fade-in" />
        <Dialog.Content className="fixed z-50 inset-0 flex items-center justify-center p-4">
          <div className="relative w-full max-w-5xl bg-surface border border-border-dim rounded-2xl shadow-2xl flex flex-col max-h-[90vh] animate-slide-up">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-border-dim flex-shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center">
                  <Zap size={14} className="text-cyan-400" />
                </div>
                <Dialog.Title className="text-sm font-bold text-white">
                  How to use the Lineup Optimizer
                </Dialog.Title>
              </div>
              <Dialog.Close asChild>
                <button
                  className="text-slate-600 hover:text-slate-400 transition-colors"
                  aria-label="Close"
                >
                  <X size={16} />
                </button>
              </Dialog.Close>
            </div>

            {/* Scrollable body */}
            <div className="overflow-y-auto scrollbar-thin px-6 py-5 flex flex-col gap-6">
              <Section
                icon={<MousePointerClick size={15} />}
                title="Step 1 — Build your player pool"
              >
                <p>
                  Search by player name or team, then filter by archetype using
                  the pills.
                </p>
                <p>
                  Check any player to add them to your pool. You need at least 3
                  to run an optimization — more players means more combinations
                  explored.
                </p>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  <Pill
                    label="⚡ Striker"
                    color="bg-rose-500/20 text-rose-400 border-rose-500/40"
                  />
                  <Pill
                    label="🛡 Anchor"
                    color="bg-cyan-500/20 text-cyan-400 border-cyan-500/40"
                  />
                  <Pill
                    label="🔄 Flex"
                    color="bg-violet-500/20 text-violet-400 border-violet-500/40"
                  />
                </div>
                <p className="mt-1">
                  Archetypes are derived from K-Means clustering on 22
                  career-average stats across {117} RLCS pros.
                </p>
              </Section>

              <Section
                icon={<SlidersHorizontal size={15} />}
                title="Step 2 — Tune the score weights"
              >
                <p>
                  Each slider scales how much that factor contributes to a
                  lineup's composite score.
                </p>
                <Metric label="Synergy" color="text-emerald-400">
                  How much the trio's actual win rate exceeded their
                  model-predicted win rate. Positive = overperforms; negative =
                  underperforms.
                </Metric>
                <Metric label="Archetype" color="text-violet-400">
                  A bonus based on role composition. Data shows
                  flex+striker+striker outperforms balanced lineups; triple-flex
                  scores lowest.
                </Metric>
                <Metric label="Elo Strength" color="text-cyan-400">
                  Average team Elo of the three players. Higher Elo = stronger
                  recent form across RLCS matches.
                </Metric>
              </Section>

              <Section
                icon={<Zap size={15} />}
                title="Step 3 — Find Best Lineups"
              >
                <p>
                  Click the button to evaluate every possible trio from your
                  pool — all C(n, 3) combinations — ranked by composite score.
                </p>
                <p>
                  Results show the top 5 lineups with a breakdown of what's
                  driving each score.
                </p>
              </Section>

              <Section
                icon={<TrendingUp size={15} />}
                title="Reading the results"
              >
                <Metric label="Score" color="text-cyan-400">
                  Weighted composite: synergy + archetype bonus + normalised
                  Elo.
                </Metric>
                <Metric label="Synergy" color="text-emerald-400">
                  Raw synergy value. Computed as actual trio win rate minus the
                  mean win probability predicted by the model.
                </Metric>
                <Metric label="Avg Elo" color="text-cyan-400">
                  Mean team Elo across the three players (initial = 1500, K =
                  32, chronological).
                </Metric>
                <div className="flex items-start gap-2 bg-amber-500/5 border border-amber-500/20 rounded-lg px-2.5 py-2 mt-1">
                  <AlertTriangle
                    size={12}
                    className="text-amber-500 flex-shrink-0 mt-0.5"
                  />
                  <span className="text-amber-500/80">
                    A low-sample warning appears when fewer than 10 matches were
                    used to compute a trio's synergy score — treat those lineups
                    as exploratory.
                  </span>
                </div>
              </Section>

              <Section icon={<TrendingUp size={15} />} title="Elo Leaderboard">
                <p>
                  Shows team strength computed from all 303 RLCS match outcomes
                  (2025–2026 seasons). Elo updates chronologically — each match
                  shifts ratings by up to 32 points.
                </p>
                <p>
                  Player Elo is inherited from their most recent team, so a
                  player who transferred carries their new team's rating.
                </p>
              </Section>

              {/* Data note */}
              <div className="border-t border-border-dim pt-4 text-[11px] text-slate-600 leading-relaxed">
                Data sourced from Ballchasing.com · 303 RLCS replays · 117
                players · 42 teams. Synergy scores are in-sample — the optimizer
                favours historically strong trios, not forward predictions.
              </div>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
