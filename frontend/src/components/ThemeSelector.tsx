import { useState } from 'react'
import { themes, type Theme } from '../styles/tokens'

interface ThemeSelectorProps {
  selectedTheme: Theme | null
  onSelect: (theme: Theme | null) => void
}

interface ThemeOption {
  key: Theme
  label: string
  description: string
}

const THEME_OPTIONS: ThemeOption[] = [
  {
    key: 'corporate',
    label: 'Corporate',
    description: 'Navy blue and white — clean enterprise look',
  },
  {
    key: 'executive',
    label: 'Executive',
    description: 'Navy with gold accent — boardroom ready',
  },
  {
    key: 'professional',
    label: 'Professional',
    description: 'Green and teal — modern professional services',
  },
  {
    key: 'dark-modern',
    label: 'Dark Modern',
    description: 'Dark background — tech-forward and bold',
  },
]

function MiniSlidePreview({ themeKey }: { themeKey: Theme }) {
  const t = themes[themeKey]
  return (
    <div
      className="w-full aspect-[16/10] rounded border overflow-hidden relative"
      style={{ backgroundColor: t.bg, borderColor: t.border }}
    >
      {/* Header accent bar */}
      <div
        className="absolute top-0 left-0 right-0 h-1.5"
        style={{ backgroundColor: t.primary }}
      />

      {/* Title area */}
      <div className="px-3 pt-4 pb-1">
        <div
          className="h-2 rounded-sm w-3/5 mb-1.5"
          style={{ backgroundColor: t.primary }}
        />
        <div
          className="h-1.5 rounded-sm w-2/5"
          style={{ backgroundColor: t.muted, opacity: 0.5 }}
        />
      </div>

      {/* Content area — bullet lines */}
      <div className="px-3 pt-1 space-y-1.5">
        {[0.8, 0.65, 0.7].map((w, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <div
              className="w-1 h-1 rounded-full flex-shrink-0"
              style={{ backgroundColor: t.accent }}
            />
            <div
              className="h-1 rounded-sm"
              style={{
                backgroundColor: t.text,
                opacity: 0.25,
                width: `${w * 100}%`,
              }}
            />
          </div>
        ))}
      </div>

      {/* Chart placeholder */}
      <div className="absolute bottom-2 right-3 flex items-end gap-0.5 h-5">
        {[0.5, 0.8, 0.6, 1, 0.7].map((h, i) => (
          <div
            key={i}
            className="w-1.5 rounded-t-sm"
            style={{
              height: `${h * 100}%`,
              backgroundColor: i === 3 ? t.accent : t.primary,
              opacity: i === 3 ? 1 : 0.6 + i * 0.08,
            }}
          />
        ))}
      </div>
    </div>
  )
}

export default function ThemeSelector({ selectedTheme, onSelect }: ThemeSelectorProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  return (
    <div>
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 transition-colors mb-3"
      >
        <svg
          className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
        <span className="font-medium">
          {selectedTheme
            ? `Theme: ${THEME_OPTIONS.find((t) => t.key === selectedTheme)?.label}`
            : 'Choose a theme (optional)'}
        </span>
        {selectedTheme && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              onSelect(null)
            }}
            className="ml-1 text-gray-400 hover:text-gray-600"
            title="Clear selection — auto-detect theme"
          >
            ✕
          </button>
        )}
      </button>

      {isExpanded && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {THEME_OPTIONS.map((opt) => {
            const isSelected = selectedTheme === opt.key
            return (
              <button
                key={opt.key}
                type="button"
                onClick={() => onSelect(isSelected ? null : opt.key)}
                className={`group rounded-lg border-2 p-2.5 text-left transition-all hover:shadow-md ${
                  isSelected
                    ? 'border-blue-500 bg-blue-50 shadow-sm'
                    : 'border-gray-200 bg-white hover:border-gray-300'
                }`}
              >
                <MiniSlidePreview themeKey={opt.key} />
                <div className="mt-2">
                  <p
                    className={`text-xs font-semibold ${
                      isSelected ? 'text-blue-700' : 'text-gray-800'
                    }`}
                  >
                    {opt.label}
                  </p>
                  <p className="text-[10px] leading-tight text-gray-500 mt-0.5">
                    {opt.description}
                  </p>
                </div>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
