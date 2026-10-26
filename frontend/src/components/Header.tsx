import { Rocket } from "lucide-react";
import { Link } from "@tanstack/react-router";

export default function Header() {
  return (
    <header className="border-b border-border-dim bg-surface backdrop-blur-sm sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-4 lg:px-6 py-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center flex-shrink-0">
            <Rocket size={16} className="text-orange-400" />
          </div>
          <div className="min-w-0">
            <h1 className="text-base font-bold text-white leading-none truncate">
              RLCS Roster Optimizer
            </h1>
            <p className="text-xs text-slate-500 mt-0.5 hidden sm:block">
              Synergy scores · Archetypes · Elo
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4 flex-shrink-0">
          <Link to="/" className="[&.active]:font-bold">
            Home
          </Link>
          <Link to="/about" className="[&.active]:font-bold">
            About
          </Link>
        </div>
      </div>
    </header>
  );
}
