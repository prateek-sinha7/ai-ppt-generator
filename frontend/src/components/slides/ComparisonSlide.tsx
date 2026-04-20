import React from 'react'
import { ComparisonSlideProps } from '../../types/slideProps'
import { getThemeColors } from '../../utils/themeUtils'
import { Icon } from '../common/Icon'
import '../../styles/transitions.css'

export const ComparisonSlide: React.FC<ComparisonSlideProps> = ({
  title,
  left_column,
  right_column,
  theme,
  icon_name,
  highlight_text,
  transition = 'fade',
  className = '',
}) => {
  const colors = getThemeColors(theme)
  const transitionClass = `slide-transition-${transition}`

  const renderColumn = (
    column: { heading: string; bullets: string[] },
    side: 'left' | 'right'
  ) => {
    const isLeft = side === 'left'
    const bgColor = isLeft ? `${colors.primary}10` : `${colors.secondary}10`
    const accentColor = isLeft ? colors.primary : colors.secondary
    const borderColor = isLeft ? `${colors.primary}30` : `${colors.secondary}30`

    return (
      <div
        className="flex-1 rounded-2xl p-6 flex flex-col"
        style={{ backgroundColor: bgColor, border: `1.5px solid ${borderColor}` }}
      >
        {/* Column header */}
        <div
          className="flex items-center gap-3 pb-4 mb-4"
          style={{ borderBottom: `2px solid ${accentColor}` }}
        >
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center text-white text-sm font-bold flex-shrink-0"
            style={{ backgroundColor: accentColor }}
          >
            {isLeft ? 'A' : 'B'}
          </div>
          <h3 className="font-bold text-base leading-tight" style={{ color: accentColor }}>
            {column.heading}
          </h3>
        </div>

        {/* Bullets */}
        <div className="flex-1 space-y-3">
          {column.bullets.map((bullet, index) => (
            <div key={index} className="flex items-start gap-3">
              <div
                className="flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center mt-0.5"
                style={{ backgroundColor: `${accentColor}20` }}
              >
                <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: accentColor }} />
              </div>
              <span className="text-sm leading-relaxed" style={{ color: colors.text }}>
                {bullet}
              </span>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div
      className={`slide-container ${transitionClass} ${className} relative flex flex-col overflow-hidden`}
      style={{ backgroundColor: colors.bg }}
    >
      {/* Top accent */}
      <div className="h-1.5 w-full flex-shrink-0" style={{ backgroundColor: colors.primary }} />

      {/* Header */}
      <div
        className="flex items-center gap-4 px-10 py-4 flex-shrink-0"
        style={{ borderBottom: `1px solid ${colors.border}` }}
      >
        {icon_name && (
          <div className="flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center" style={{ backgroundColor: `${colors.primary}15` }}>
            <Icon name={icon_name} size={20} color={colors.primary} />
          </div>
        )}
        <h2 className="font-bold flex-1 leading-tight" style={{ color: colors.text, fontSize: '1.5rem' }}>
          {title}
        </h2>
        <div className="flex-shrink-0 text-xs font-medium px-3 py-1 rounded-full" style={{ backgroundColor: `${colors.primary}15`, color: colors.primary }}>
          COMPARISON
        </div>
      </div>

      {/* Columns */}
      <div className="flex-1 flex gap-5 px-10 py-6 overflow-hidden">
        {renderColumn(left_column, 'left')}

        {/* VS divider */}
        <div className="flex-shrink-0 flex flex-col items-center justify-center gap-2">
          <div className="flex-1 w-px" style={{ backgroundColor: colors.border }} />
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
            style={{ backgroundColor: colors.surface, color: colors.muted, border: `1px solid ${colors.border}` }}
          >
            VS
          </div>
          <div className="flex-1 w-px" style={{ backgroundColor: colors.border }} />
        </div>

        {renderColumn(right_column, 'right')}
      </div>

      {/* Bottom highlight */}
      {highlight_text && (
        <div
          className="flex-shrink-0 px-10 py-3 flex items-center gap-3"
          style={{ backgroundColor: `${colors.accent}10`, borderTop: `1px solid ${colors.border}` }}
        >
          <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: colors.accent }} />
          <p className="text-xs font-semibold" style={{ color: colors.text }}>
            {highlight_text}
          </p>
        </div>
      )}
    </div>
  )
}
