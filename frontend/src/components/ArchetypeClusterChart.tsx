import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import clusterData from "../data/archetype_clusters.json";
import { ArchetypeBadge } from "./ArchetypeBadge";

const SURFACE = "#102d63";

const ARCHETYPE_COLORS: Record<string, string> = {
  striker: "#ff6b7a",
  anchor: "#5cc8ff",
  flex: "#b79cff",
  unknown: "#9fb6e0",
};

// Secondary (non-color) identity channel, since two of the archetype hues
// sit close enough for some color-vision deficiencies that color alone
// isn't a reliable encoding — shape carries identity too.
const ARCHETYPE_SHAPES: Record<string, "circle" | "diamond" | "triangle" | "cross"> = {
  striker: "circle",
  anchor: "diamond",
  flex: "triangle",
  unknown: "cross",
};

const ARCHETYPE_ORDER = ["striker", "anchor", "flex", "unknown"];

interface ClusterPoint {
  id: string;
  name: string;
  archetype: string;
  x: number;
  y: number;
  n_games: number;
}

const points = clusterData.points as ClusterPoint[];
const [pc1Variance, pc2Variance] = clusterData.explained_variance;

function Marker({
  cx,
  cy,
  payload,
}: {
  cx?: number;
  cy?: number;
  payload?: ClusterPoint;
}) {
  if (cx === undefined || cy === undefined || !payload) return null;
  const archetype = payload.archetype;
  const color = ARCHETYPE_COLORS[archetype] ?? ARCHETYPE_COLORS.unknown;
  const shape = ARCHETYPE_SHAPES[archetype] ?? "cross";
  const r = 5;

  const common = {
    fill: color,
    stroke: SURFACE,
    strokeWidth: 2,
  };

  switch (shape) {
    case "diamond":
      return (
        <path
          d={`M ${cx} ${cy - r} L ${cx + r} ${cy} L ${cx} ${cy + r} L ${cx - r} ${cy} Z`}
          {...common}
        />
      );
    case "triangle":
      return (
        <path
          d={`M ${cx} ${cy - r} L ${cx + r} ${cy + r * 0.8} L ${cx - r} ${cy + r * 0.8} Z`}
          {...common}
        />
      );
    case "cross":
      return (
        <path
          d={`M ${cx - r} ${cy - r} L ${cx + r} ${cy + r} M ${cx + r} ${cy - r} L ${cx - r} ${cy + r}`}
          fill="none"
          stroke={color}
          strokeWidth={2.5}
          strokeLinecap="round"
        />
      );
    default:
      return <circle cx={cx} cy={cy} r={r} {...common} />;
  }
}

function ClusterTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: ClusterPoint }[];
}) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="bg-deep border border-line-bright rounded-md px-3 py-2 shadow-xl flex flex-col gap-1.5">
      <span className="font-display text-lg font-bold uppercase text-ink">{p.name}</span>
      <ArchetypeBadge archetype={p.archetype} />
      <span className="text-sm text-muted">{p.n_games} games</span>
    </div>
  );
}

export function ArchetypeClusterChart() {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-3">
        {ARCHETYPE_ORDER.map((a) => (
          <ArchetypeBadge key={a} archetype={a} />
        ))}
      </div>
      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid stroke="#24488f" strokeWidth={1} />
            <XAxis
              type="number"
              dataKey="x"
              tick={false}
              axisLine={{ stroke: "#24488f" }}
              tickLine={false}
              label={{
                value: `PC1 (${(pc1Variance * 100).toFixed(0)}% variance)`,
                position: "insideBottom",
                offset: -4,
                fill: "#9fb6e0",
                fontSize: 12,
              }}
            />
            <YAxis
              type="number"
              dataKey="y"
              tick={false}
              axisLine={{ stroke: "#24488f" }}
              tickLine={false}
              label={{
                value: `PC2 (${(pc2Variance * 100).toFixed(0)}% variance)`,
                angle: -90,
                position: "insideLeft",
                fill: "#9fb6e0",
                fontSize: 12,
              }}
            />
            <Tooltip
              cursor={{ stroke: "#3866b8", strokeWidth: 1 }}
              content={<ClusterTooltip />}
            />
            <Scatter data={points} shape={<Marker />} isAnimationActive={false} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
