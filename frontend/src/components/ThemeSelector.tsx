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
    key: 'ocean-depths',
    label: 'Ocean Depths',
    description: 'Deep navy and teal — calm, professional',
  },
  {
    key: 'sunset-boulevard',
    label: 'Sunset Boulevard',
    description: 'Warm orange and coral — creative energy',
  },
  {
    key: 'forest-canopy',
    label: 'Forest Canopy',
    description: 'Earth tones and sage — natural, grounded',
  },
  {
    key: 'modern-minimalist',
    label: 'Modern Minimalist',
    description: 'Charcoal and slate — clean versatility',
  },
  {
    key: 'golden-hour',
    label: 'Golden Hour',
    description: 'Mustard and terracotta — warm, inviting',
  },
  {
    key: 'arctic-frost',
    label: 'Arctic Frost',
    description: 'Steel blue and silver — crisp, clinical',
  },
  {
    key: 'desert-rose',
    label: 'Desert Rose',
    description: 'Dusty rose and burgundy — soft elegance',
  },
  {
    key: 'tech-innovation',
    label: 'Tech Innovation',
    description: 'Electric blue on dark — bold, futuristic',
  },
  {
    key: 'botanical-garden',
    label: 'Botanical Garden',
    description: 'Fern green and marigold — fresh, organic',
  },
  {
    key: 'midnight-galaxy',
    label: 'Midnight Galaxy',
    description: 'Deep purple and lavender — dramatic, cosmic',
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
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {THEME_OPTIONS.map((opt) => {
            const isSelected = selectedTheme === opt.key
            const t = themes[opt.key]
            return (
              <button
                key={opt.key}
                type="button"
                onClick={() => onSelect(isSelected ? null : opt.key)}
                className={`group rounded-lg p-2.5 text-left transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg ${
                  isSelected
                    ? 'ring-2 shadow-md'
                    : 'border border-gray-200 bg-white hover:border-transparent hover:shadow-md'
                }`}
                style={isSelected ? {
                  borderColor: t.primary,
                  boxShadow: `0 4px 14px ${t.primary}30`,
                  outline: `2px solid ${t.primary}`,
                  outlineOffset: '-2px',
                  backgroundColor: `${t.bg}`,
                } : undefined}
              >
                <MiniSlidePreview themeKey={opt.key} />
                <div className="mt-2">
                  <p
                    className="text-xs font-semibold"
                    style={{ color: isSelected ? t.primary : undefined }}
                  >
                    {opt.label}
                  </p>
                  <p className="text-[10px] leading-tight text-gray-500 mt-0.5">
                    {opt.description}
                  </p>
                </div>
                {/* Theme color swatch strip */}
                <div className="flex gap-0.5 mt-1.5">
                  {[t.primary, t.secondary, t.accent].map((color, i) => (
                    <div
                      key={i}
                      className="h-1 flex-1 rounded-full"
                      style={{ backgroundColor: color }}
                    />
                  ))}
                </div>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
