export type GenerationMode = 'code' | 'hybrid' | 'json'

interface GenerationModeSelectorProps {
  selectedMode: GenerationMode
  onSelect: (mode: GenerationMode) => void
}

interface ModeOption {
  key: GenerationMode
  label: string
  description: string
  icon: string
}

const MODE_OPTIONS: ModeOption[] = [
  {
    key: 'code',
    label: 'Code',
    description: 'Highest Visual Quality',
    icon: '✦',
  },
  {
    key: 'hybrid',
    label: 'Hybrid',
    description: 'Balanced',
    icon: '⚡',
  },
  {
    key: 'json',
    label: 'JSON',
    description: 'Classic / Fastest',
    icon: '⏱',
  },
]

export default function GenerationModeSelector({
  selectedMode,
  onSelect,
}: GenerationModeSelectorProps) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-2">
        Generation Mode
      </label>
      <div className="grid grid-cols-3 gap-3">
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
              <span className="block text-sm font-semibold">{opt.label}</span>
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
