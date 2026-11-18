import * as RadixSlider from "@radix-ui/react-slider";
import type { Weights } from "../api/client";

interface Props {
  weights: Weights;
  onChange: (weights: Weights) => void;
}

interface SliderConfig {
  key: keyof Weights;
  label: string;
  description: string;
  rangeColor: string;
}

const SLIDERS: SliderConfig[] = [
  {
    key: "synergy",
    label: "Synergy",
    description: "Trio win rate vs. expected",
    rangeColor: "bg-boost",
  },
  {
    key: "archetype",
    label: "Archetype",
    description: "Role composition balance",
    rangeColor: "bg-ice-deep",
  },
  {
    key: "elo",
    label: "Elo strength",
    description: "Average team Elo",
    rangeColor: "bg-ice-deep",
  },
];

export function WeightSliders({ weights, onChange }: Props) {
  return (
    <div className="flex flex-col gap-5">
      <h2 className="sr-only">Score weights</h2>

      {SLIDERS.map(({ key, label, description, rangeColor }) => (
        <div key={key} className="flex flex-col gap-1">
          <div className="flex items-baseline justify-between">
            <span id={`w-${key}`} className="eyebrow text-body">
              {label}
            </span>
            <span className="num text-lg text-ink">
              {weights[key].toFixed(1)}
            </span>
          </div>
          <p className="text-sm text-muted">{description}</p>

          <RadixSlider.Root
            value={[weights[key]]}
            onValueChange={([v]) => onChange({ ...weights, [key]: v })}
            min={0}
            max={2}
            step={0.1}
            className="relative flex h-8 w-full touch-none select-none items-center"
          >
            <RadixSlider.Track className="relative h-2 grow rounded-full bg-line">
              <RadixSlider.Range
                className={`absolute h-full rounded-full ${rangeColor}`}
              />
            </RadixSlider.Track>
            <RadixSlider.Thumb
              aria-labelledby={`w-${key}`}
              className="block h-6 w-3 -skew-x-[18deg] cursor-grab bg-ink shadow-md transition-transform hover:scale-110 active:cursor-grabbing"
            />
          </RadixSlider.Root>
        </div>
      ))}
    </div>
  );
}
