import * as RadixSlider from '@radix-ui/react-slider'
import type { Weights } from '../api/client'

interface Props {
  weights: Weights
  onChange: (weights: Weights) => void
}

interface SliderConfig {
  key: keyof Weights
  label: string
  description: string
  color: string
  trackColor: string
  thumbGlow: string
}

const SLIDERS: SliderConfig[] = [
  {
    key: 'synergy',
    label: 'Synergy',
    description: 'Trio win-rate vs. expected',
    color: 'text-emerald-400',
    trackColor: 'bg-emerald-500',
    thumbGlow: 'shadow-[0_0_8px_rgba(52,211,153,0.6)]',
  },
  {
    key: 'archetype',
    label: 'Archetype',
    description: 'Role composition balance',
    color: 'text-violet-400',
    trackColor: 'bg-violet-500',
    thumbGlow: 'shadow-[0_0_8px_rgba(167,139,250,0.6)]',
  },
  {
    key: 'elo',
    label: 'Elo Strength',
    description: 'Team Elo rating average',
    color: 'text-cyan-400',
    trackColor: 'bg-cyan-500',
    thumbGlow: 'shadow-[0_0_8px_rgba(0,212,255,0.6)]',
  },
]

export function WeightSliders({ weights, onChange }: Props) {
  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-slate-200">Score Weights</span>
        <span className="text-xs text-slate-600">Drag to rebalance</span>
      </div>

      {SLIDERS.map(({ key, label, description, color, trackColor, thumbGlow }) => (
        <div key={key} className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <div>
              <span className={`text-xs font-semibold ${color}`}>{label}</span>
              <span className="ml-1.5 text-xs text-slate-600">{description}</span>
            </div>
            <span className={`text-xs font-mono font-semibold ${color}`}>
              {weights[key].toFixed(1)}
            </span>
          </div>

          <RadixSlider.Root
            value={[weights[key]]}
            onValueChange={([v]) => onChange({ ...weights, [key]: v })}
            min={0}
            max={2}
            step={0.1}
            className="relative flex items-center select-none touch-none w-full h-5"
          >
            <RadixSlider.Track className="bg-border-dim relative grow rounded-full h-1.5">
              <RadixSlider.Range className={`absolute rounded-full h-full ${trackColor} opacity-80`} />
            </RadixSlider.Track>
            <RadixSlider.Thumb
              className={`block w-4 h-4 bg-white rounded-full border-2 border-white/20 focus:outline-none cursor-grab active:cursor-grabbing transition-shadow ${thumbGlow} hover:scale-110`}
            />
          </RadixSlider.Root>
        </div>
      ))}
    </div>
  )
}
