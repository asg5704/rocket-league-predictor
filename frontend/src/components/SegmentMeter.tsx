interface Props {
  /** 0..1 fill fraction */
  fraction: number;
  label: string;
  /** Text equivalent of the value, announced by screen readers */
  valueText: string;
  tone?: "boost" | "ice" | "bad";
  size?: "lg" | "sm";
  segments?: number;
}

const TONES = {
  boost: "bg-boost",
  ice: "bg-ice-deep",
  bad: "bg-bad",
} as const;

/** Skewed boost-segment meter, the signature visual of the app. */
export function SegmentMeter({
  fraction,
  label,
  valueText,
  tone = "ice",
  size = "sm",
  segments = 10,
}: Props) {
  const clamped = Math.max(0, Math.min(1, fraction));
  const filled = Math.round(clamped * segments);
  const height = size === "lg" ? "h-[22px]" : "h-3";

  return (
    <div
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clamped * 100)}
      aria-valuetext={valueText}
      className="flex gap-1 pl-1"
    >
      {Array.from({ length: segments }).map((_, i) => (
        <span
          key={i}
          aria-hidden="true"
          className={`flex-1 -skew-x-[18deg] ${height} ${
            i < filled ? TONES[tone] : "bg-line"
          }`}
        />
      ))}
    </div>
  );
}
