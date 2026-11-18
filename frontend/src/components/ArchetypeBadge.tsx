import type { ReactNode } from "react";
import { ZapIcon, ShieldHalf, BicepsFlexed, CircleHelp } from "lucide-react";

interface Props {
  archetype: string;
  size?: "sm" | "md";
}

const ARCHETYPE_STYLES: Record<string, string> = {
  striker: "bg-striker/15 text-striker border-striker/50",
  anchor: "bg-anchor/15 text-anchor border-anchor/50",
  flex: "bg-flex/15 text-flex border-flex/50",
  unknown: "bg-muted/10 text-muted border-muted/40",
};

const ARCHETYPE_ICONS: Record<string, ReactNode> = {
  striker: <ZapIcon className="h-3 w-3" aria-hidden="true" />,
  anchor: <ShieldHalf className="h-3 w-3" aria-hidden="true" />,
  flex: <BicepsFlexed className="h-3 w-3" aria-hidden="true" />,
  unknown: <CircleHelp className="h-3 w-3" aria-hidden="true" />,
};

export function ArchetypeBadge({ archetype, size = "sm" }: Props) {
  const styles = ARCHETYPE_STYLES[archetype] ?? ARCHETYPE_STYLES.unknown;
  const icon = ARCHETYPE_ICONS[archetype] ?? ARCHETYPE_ICONS.unknown;
  const sizeClass =
    size === "md" ? "px-3 py-1 text-sm gap-1.5" : "px-2 py-0.5 text-xs gap-1";

  return (
    <span
      className={`inline-flex items-center rounded-[4px] border font-display font-bold uppercase tracking-wider ${styles} ${sizeClass}`}
    >
      {icon}
      {archetype}
    </span>
  );
}
