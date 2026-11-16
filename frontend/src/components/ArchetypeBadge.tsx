import type { ReactNode } from "react";
import { ZapIcon, ShieldHalf, BicepsFlexed } from "lucide-react";
interface Props {
  archetype: string;
  size?: "sm" | "md";
}

const ARCHETYPE_STYLES: Record<string, string> = {
  striker: "bg-rose-500/20 text-rose-400 border-rose-500/40",
  anchor: "bg-cyan-500/20 text-cyan-400 border-cyan-500/40",
  flex: "bg-violet-500/20 text-violet-400 border-violet-500/40",
  unknown: "bg-slate-500/20 text-slate-400 border-slate-500/40",
};

const ARCHETYPE_ICONS: Record<string, ReactNode> = {
  striker: <ZapIcon className="h-3 w-3" />,
  anchor: <ShieldHalf className="h-3 w-3" />,
  flex: <BicepsFlexed className="h-3 w-3" />,
  unknown: "?",
};

export function ArchetypeBadge({ archetype, size = "sm" }: Props) {
  const styles = ARCHETYPE_STYLES[archetype] ?? ARCHETYPE_STYLES.unknown;
  const icon = ARCHETYPE_ICONS[archetype] ?? "?";
  const sizeClass =
    size === "md"
      ? "px-3 py-1 text-xs gap-1.5"
      : "px-2 py-0.5 text-[11px] gap-1";

  return (
    <span
      className={`inline-flex items-center rounded-full border font-medium capitalize ${styles} ${sizeClass}`}
    >
      <span className="text-[10px]">{icon}</span>
      {archetype}
    </span>
  );
}
