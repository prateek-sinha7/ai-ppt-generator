import { useState } from 'react'

export type GenerationMode = 'artisan' | 'studio' | 'craft' | 'express'

interface GenerationModeSelectorProps {
  selectedMode: GenerationMode
  onSelect: (mode: GenerationMode) => void
}

interface ModeOption {
  key: GenerationMode
  label: string
  description: string
  icon: string
  hint: string
}

const MODE_OPTIONS: ModeOption[] = [
  {
    key: 'artisan',
    label: 'Artisan',
    description: 'Bespoke AI-designed presentation',
    icon: '🎨',
    hint: 'AI writes the entire presentation as one script with full creative freedom — custom colors, cross-slide consistency, and unique layouts. Best visual quality but slower.',
  },
  {
    key: 'studio',
    label: 'Studio',
    description: 'Professional-grade slides',
    icon: '✦',
    hint: 'AI writes code for each slide individually with theme colors applied. Great visual quality with per-slide error recovery.',
  },
  {
    key: 'craft',
    label: 'Craft',
    description: 'Balanced quality & speed',
    icon: '⚡',
    hint: 'Simple slides use fast templates, complex slides get AI-generated code. Good balance of speed and quality.',
  },
  {
    key: 'express',
    label: 'Express',
    description: 'Fastest generation',
    icon: '⏱',
    hint: 'Uses pre-built templates for all slides. Fastest and most reliable, but limited layout variety.',
  },
]

function InfoTooltip({ hint }: { hint: string }) {
  const [visible, setVisible] = useState(false)

  return (
    <span className="relative inline-flex items-center ml-1">
      <button
        type="button"
        aria-label="More info"
        className="text-xs leading-none focus:outline-none"
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
        onFocus={() => setVisible(true)}
        onBlur={() => setVisible(false)}
        onClick={(e) => { e.stopPropagation(); setVisible((v) => !v) }}
      >
        ⓘ
      </button>
      {visible && (
        <span
          role="tooltip"
          className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-52 rounded-lg bg-slate-800 text-white text-xs px-3 py-2 shadow-lg z-10 pointer-events-none"
        >
          {hint}
          <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-800" />
        </span>
      )}
    </span>
  )
}

export default function GenerationModeSelector({
  selectedMode,
  onSelect,
}: GenerationModeSelectorProps) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-2">
        Generation Mode
      </label>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {MODE_OPTIONS.map((opt) => {
          const isSelected = selectedMode === opt.key
          return (
            <button
              key={opt.key}
              type="button"
              onClick={() => onSelect(opt.key)}
              className={`relative rounded-lg px-3 py-3 text-center transition-all duration-200 ${
                isSelected
                  ? 'bg-slate-800 text-white shadow-md ring-2 ring-slate-800'
                  : 'bg-white border border-gray-200 text-gray-700 hover:border-slate-400 hover:shadow-sm'
              }`}
            >
              <span className="block text-lg mb-1" aria-hidden="true">
                {opt.icon}
              </span>
              <span className="flex items-center justify-center text-sm font-semibold">
                {opt.label}
                <InfoTooltip hint={opt.hint} />
              </span>
              <span
                className={`block text-xs mt-0.5 ${
                  isSelected ? 'text-slate-300' : 'text-gray-500'
                }`}
              >
                {opt.description}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
