import { createFileRoute } from "@tanstack/react-router";
import { TrendingUp } from "lucide-react";
import { api } from "../api/client";
import { useQuery } from "../hooks/useApi";
import { EloLeaderboard } from "../components/EloLeaderboard";
import { LeaderboardSkeleton } from "../components/Skeleton";

export const Route = createFileRoute("/leaderboard")({
  component: Leaderboard,
});

function Leaderboard() {
  const { data, loading, error } = useQuery(() => api.getEloRatings());

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6 lg:px-6">
      <header className="mb-5">
        <h1 className="flex items-center gap-3 font-display text-4xl font-extrabold uppercase tracking-wide text-ink">
          <TrendingUp size={28} className="text-boost" aria-hidden="true" />
          Elo leaderboard
          {data && (
            <span className="num text-xl text-muted">· {data.total} teams</span>
          )}
        </h1>
        <p className="mt-2 max-w-2xl text-body">
          Team strength from every RLCS match in the dataset. Every player has their
          own rating (start 1500, K = 16, updated chronologically). A team's
          rating is the mean of its current roster, so a roster change moves the
          ranking immediately.
        </p>
      </header>

      <section className="panel p-4">
        {loading ? (
          <div
            aria-busy="true"
            className="overflow-hidden rounded-md border border-line bg-deep"
          >
            <LeaderboardSkeleton />
          </div>
        ) : error ? (
          <p role="alert" className="py-4 font-semibold text-bad">
            Failed to load ratings. Retry in a few minutes.
          </p>
        ) : data ? (
          <EloLeaderboard ratings={data.ratings} />
        ) : null}
      </section>
    </div>
  );
}
