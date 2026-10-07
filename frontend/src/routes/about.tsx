import { createFileRoute } from "@tanstack/react-router";
import * as Tabs from "@radix-ui/react-tabs";
import {
  Rocket,
  MousePointerClick,
  SlidersHorizontal,
  Zap,
  TrendingUp,
  AlertTriangle,
  ScatterChart,
  History,
} from "lucide-react";
import { ArchetypeBadge } from "../components/ArchetypeBadge";
import { ArchetypeClusterChart } from "../components/ArchetypeClusterChart";
import changelog from "../data/model_changelog.json";

export const Route = createFileRoute("/about")({
  component: About,
});

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
        <h3 className="text-lg font-semibold text-slate-200">{title}</h3>
      </div>
      <div className="pl-6 flex flex-col gap-1.5 text-base text-slate-400 leading-relaxed">
        {children}
      </div>
    </div>
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
    <>
      <span className={`font-semibold ${color}`}>{label}</span>
      <p>{children}</p>
    </>
  );
}

function About() {
  return (
    <Tabs.Root
      className="flex-1 max-w-7xl mx-auto w-full px-4 lg:px-6 py-6 grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-6 items-start"
      defaultValue="how-to-use"
      orientation="vertical"
    >
      <Tabs.List
        aria-label="How to use"
        className="flex flex-col items-start space-y-2"
      >
        <Tabs.Trigger
          className="data-[state='active']:font-bold"
          value="how-to-use"
        >
          How to use
        </Tabs.Trigger>
        <Tabs.Trigger className="data-[state='active']:font-bold" value="about">
          About this project
        </Tabs.Trigger>
        <Tabs.Trigger
          className="data-[state='active']:font-bold"
          value="warning"
        >
          Warning
        </Tabs.Trigger>
      </Tabs.List>
      <Tabs.Content
        className="relative w-full max-w-5xl bg-surface border border-border-dim rounded-2xl shadow-2xl flex flex-col animate-slide-up"
        value="how-to-use"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border-dim flex-shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center">
              <Rocket size={14} className="text-orange-400" />
            </div>
            <h2 className="text-xl font-bold text-white">
              How to use the Lineup Optimizer
            </h2>
          </div>
        </div>

        {/* Scrollable body */}
        <div className="overflow-y-auto scrollbar-thin px-6 py-5 flex flex-col gap-6">
          <Section
            icon={<MousePointerClick size={20} />}
            title="Step 1 — Build your player pool"
          >
            <p>
              Search by player name or team, then filter by archetype using the
              pills.
            </p>
            <p>
              Check any player to add them to your pool. You need at least 3 to
              run an optimization. The more players added means the more
              combinations that can be explored.
            </p>
            <div className="flex flex-wrap gap-1.5 mt-1">
              {["striker", "anchor", "flex"].map((a) => (
                <ArchetypeBadge archetype={a} />
              ))}
            </div>
            <p className="mt-1">
              Archetypes are derived from K-Means clustering on 22
              career-average stats across {121} RLCS pros.
            </p>
          </Section>

          <Section
            icon={<SlidersHorizontal size={20} />}
            title="Step 2 — Tune the score weights"
          >
            <p>
              Each slider scales how much that factor contributes to a lineup's
              composite score.
            </p>
            <div className="grid grid-cols-1 lg:grid-cols-[130px_1fr] space-y-2">
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
                Average team Elo of the three RLCS players. <em>Higher Elo</em>{" "}
                = stronger recent form across RLCS matches.
              </Metric>
            </div>
          </Section>

          <Section icon={<Zap size={20} />} title="Step 3 — Find Best Lineups">
            <p>
              Click the button to evaluate every possible trio from your pool of
              players all C(n, 3) combinations ranked by composite score.
            </p>
            <p>
              Results show the top 5 lineups with a breakdown of what's driving
              each score.
            </p>
          </Section>

          <Section icon={<TrendingUp size={20} />} title="Reading the results">
            <div className="grid grid-cols-1 lg:grid-cols-[130px_1fr] space-y-2">
              <Metric label="Score" color="text-blue-400">
                Weighted composite: synergy + archetype bonus + normalised Elo.
              </Metric>
              <Metric label="Synergy" color="text-emerald-400">
                Raw synergy value. Computed as actual trio win rate minus the
                mean win probability predicted by the model.
              </Metric>
              <Metric label="Avg Elo" color="text-cyan-400">
                Mean team Elo across the three players (initial = 1500, K = 32,
                chronological).
              </Metric>
            </div>
            <div className="flex items-start gap-2 bg-amber-500/5 border border-amber-500/20 rounded-lg px-2.5 py-2 mt-1">
              <AlertTriangle
                size={12}
                className="text-amber-500 flex-shrink-0 mt-0.5"
              />
              <span className="text-amber-500/80">
                A low-sample warning appears when fewer than 10 matches were
                used to compute a trio's synergy score — treat those lineups as
                exploratory.
              </span>
            </div>
          </Section>

          <Section icon={<TrendingUp size={20} />} title="Elo Leaderboard">
            <p>
              Shows team strength computed from all 328 RLCS match outcomes
              (2025–2026 seasons). Elo updates chronologically each match shifts
              ratings by up to 32 points.
            </p>
            <p>
              Player Elo is inherited from their most recent team, so a player
              who transferred carries their new team's rating.
            </p>
          </Section>

          <Section icon={<History size={20} />} title="Model changelog">
            <p>
              Each retrain with new Ballchasing data is logged here, newest
              first.
            </p>
            <ul className="flex flex-col gap-3">
              {changelog.map((e) => (
                <li
                  key={e.date}
                  className="border border-border-dim rounded-lg px-3 py-2 text-xs leading-relaxed"
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-slate-200 font-medium">{e.title}</span>
                    <span className="text-slate-500">{e.date}</span>
                  </div>
                  <div className="text-slate-400">
                    {e.matches} matches · {e.players} players · {e.teams} teams
                  </div>
                  <div className="text-slate-400">
                    XGBoost accuracy {(e.xgboostAccuracy * 100).toFixed(1)}% ·
                    ROC-AUC {e.xgboostRocAuc.toFixed(2)} · silhouette{" "}
                    {e.silhouette.toFixed(2)}
                  </div>
                  <div className="text-slate-400">
                    Top 3: {e.top3.join(", ")}
                  </div>
                </li>
              ))}
            </ul>
          </Section>

          {/* Data note */}
          <div className="border-t border-border-dim pt-4 text-xs text-slate-600 leading-relaxed">
            Data sourced from Ballchasing.com · 328 RLCS replays · 121 players ·
            45 teams. Synergy scores are in-sample — the optimizer favours
            historically strong trios, not forward predictions.
          </div>
        </div>
      </Tabs.Content>
      <Tabs.Content
        className="relative w-full max-w-5xl bg-surface border border-border-dim rounded-2xl shadow-2xl flex flex-col animate-slide-up"
        value="about"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border-dim flex-shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center">
              <Rocket size={16} className="text-orange-400" />
            </div>
            <h2 className="text-xl font-bold text-white">About</h2>
          </div>
        </div>

        {/* Scrollable body */}
        <div className="overflow-y-auto scrollbar-thin px-6 py-5 flex flex-col gap-6">
          <Section icon={<MousePointerClick size={20} />} title="Background">
            <p>
              My goal was to showcase my newly acquired skills and knowledge and
              apply it to something that I'm interested in:{" "}
              <strong>Rocket League</strong> and <strong>AI</strong>. With that
              in mind, I decided to create this Machine Learning project, to
              learn the processes from instantiation to full deployment.
            </p>
            <p>
              I chose Rocket League mostly because I enjoy watching RLCS pros
              hit crazy shots and the{" "}
              <a
                href="https://ballchasing.com"
                className="underline text-slate-500"
              >
                BallChasing
              </a>{" "}
              site has an API with a generous free tier that has enabled a lot
              of the Machine Learning + Data Science work.
            </p>
          </Section>
          <Section icon={<MousePointerClick size={20} />} title="Skills">
            <p>
              The skills used to create this project include a mix of the
              following using both Python and TypeScript:
            </p>
            <div className="grid grid-cols-1 lg:grid-cols-2">
              <ul className="list-disc list-inside">
                <li>Statistical Rating Systems</li>
                <li>Unsupervised Learning + Clustering</li>
                <li>Combinatorial Optimization</li>
                <li>Feature Engineering (Time-Series aware)</li>
                <li>Model Development + Selection</li>
                <li>Data Engineering + ETL Pipelines</li>
                <li>Exploratory Data Analysis</li>
              </ul>
              <ul className="list-disc list-inside">
                <li>REST API Design (via FastAPI)</li>
                <li>API Security Hardening</li>
                <li>UI/Frontend Development</li>
                <li>Testing + QA</li>
                <li>Containerization</li>
                <li>Deployment + DevOps</li>
              </ul>
            </div>
          </Section>
          <Section
            icon={<ScatterChart size={20} />}
            title="Methodology: K-Means player archetypes"
          >
            <p>
              Each RLCS pro's 22 career-average stats (goals, saves, boost
              usage, positioning, movement, etc.) are standardized and
              clustered into 3 archetypes with K-Means. Players below 5
              career games aren't clustered and show as "unknown". The plot
              below projects that 22-dimensional feature space down to 2D
              with PCA, purely for visualization — the model itself clusters
              on the full feature set, not these two components.
            </p>
            <ArchetypeClusterChart />
            <p className="text-xs text-slate-600 mt-1">
              Silhouette score ≈ 0.12 — clusters are directional rather than
              tightly separated, which tracks with how fluid pro RL roles
              actually are.
            </p>
          </Section>
          <Section icon={<MousePointerClick size={20} />} title="About me">
            <p>
              My name is Alexander Garcia and I'm a Frontend + AI Engineer who
              loves to learn new things and build cool stuff. If you're
              interested in this I have an entire{" "}
              <a
                href="https://alexandergarcia.dev/blog/rocket-league-ml-series"
                className="underline text-indigo-500"
              >
                blog series
              </a>{" "}
              going through everything from soup to nuts.
            </p>
          </Section>
        </div>
      </Tabs.Content>
      <Tabs.Content
        className="relative w-full max-w-5xl bg-surface border border-border-dim rounded-2xl shadow-2xl flex flex-col animate-slide-up"
        value="warning"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border-dim flex-shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-red-500/20 border border-red-500/30 flex items-center justify-center">
              <AlertTriangle size={16} className="text-red-400" />
            </div>
            <h2 className="text-xl font-bold text-white">Warning</h2>
          </div>
        </div>

        {/* Scrollable body */}
        <div className="overflow-y-auto scrollbar-thin px-6 py-5 flex flex-col gap-6">
          <Section
            icon={<AlertTriangle size={16} className="text-red-400" />}
            title="Notice"
          >
            <p>
              This Rocket League lineup optmizer tool is built purely for{" "}
              <strong>educational and data analysis purposes.</strong> The
              algorithm and model evaluates pro player statistics hypothetically
              and should not be used as a tool for official team recruitment,
              scouting, or roster decisions.
            </p>
          </Section>
        </div>
      </Tabs.Content>
    </Tabs.Root>
  );
}
