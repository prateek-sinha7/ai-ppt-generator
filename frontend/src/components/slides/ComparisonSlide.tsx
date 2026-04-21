import React from 'react'
import { SlideColors } from '../../utils/themeUtils'
import '../../styles/transitions.css'

interface ComparisonSlideProps {
  title: string
  left_column: { heading: string; bullets: string[] }
  right_column: { heading: string; bullets: string[] }
  colors: SlideColors
  visual_hint: 'two-column'
  icon_name?: string
  highlight_text?: string
  transition?: string
  className?: string
}

export const ComparisonSlide: React.FC<ComparisonSlideProps> = ({
  title,
  left_column,
  right_column,
  colors,
  transition = 'fade',
  className = '',
}) => {
  const transitionClass = `slide-transition-${transition}`

  const renderColumn = (
    column: { heading: string; bullets: string[] },
    side: 'left' | 'right'
  ) => {
    const headerColor = side === 'left' ? colors.primary : colors.secondary
    const arrowColor = side === 'left' ? colors.primary : colors.secondary

    return (
      <div
        className="flex-1 flex flex-col rounded overflow-hidden"
        style={{ border: '1px solid #E2E8F0', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}
      >
        {/* Colored header bar */}
        <div
          className="flex items-center justify-center px-3 py-2 font-bold text-sm"
          style={{ backgroundColor: headerColor, color: '#FFFFFF', minHeight: '2.2rem' }}
        >
          {column.heading}
        </div>

        {/* Items */}
        <div className="flex-1 flex flex-col gap-1 p-2 overflow-hidden" style={{ backgroundColor: '#FFFFFF' }}>
          {column.bullets.map((item, i) => (
            <div
              key={i}
              className="flex items-start gap-2 rounded px-2 py-1.5"
              style={{ backgroundColor: '#F8FAFC', border: '0.5px solid #E2E8F0' }}
            >
              <span className="font-bold flex-shrink-0 text-sm" style={{ color: arrowColor }}>›</span>
              <span className="text-xs leading-snug" style={{ color: colors.text }}>{item}</span>
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
      {/* Dark header bar */}
      <div
        className="flex-shrink-0 flex items-center px-4"
        style={{ backgroundColor: colors.bgDark, height: '13.3%' }}
      >
        <h2 className="font-bold tracking-wide truncate" style={{ color: '#FFFFFF', fontSize: '1.15rem', letterSpacing: '0.03em' }}>
          {title}
        </h2>
      </div>
      <div style={{ height: '1%', backgroundColor: colors.accent, flexShrink: 0 }} />

      {/* Two columns */}
      <div className="flex-1 flex gap-3 px-4 py-3 overflow-hidden">
        {renderColumn(left_column, 'left')}
        {renderColumn(right_column, 'right')}
      </div>
    </div>
  )
}
