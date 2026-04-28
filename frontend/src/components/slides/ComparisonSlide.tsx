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
  layout_variant?: string
}

export const ComparisonSlide: React.FC<ComparisonSlideProps> = ({
  title,
  left_column,
  right_column,
  colors,
  transition = 'fade',
  className = '',
  layout_variant,
}) => {
  const transitionClass = `slide-transition-${transition}`

  const variant = layout_variant || 'two-column'

  const renderDefaultColumn = (
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
        <div
          className="flex items-center justify-center px-3 py-2 font-bold text-sm"
          style={{ backgroundColor: headerColor, color: '#FFFFFF', minHeight: '2.2rem' }}
        >
          {column.heading}
        </div>
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

  const renderColumns = () => {
    switch (variant) {
      case 'pros-cons':
        return (
          <div className="flex-1 flex gap-3 px-4 py-3 overflow-hidden">
            {/* Left column — pros style with green checkmarks */}
            <div
              className="flex-1 flex flex-col rounded overflow-hidden"
              style={{ border: '1px solid #E2E8F0', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}
            >
              <div
                className="flex items-center justify-center px-3 py-2 font-bold text-sm"
                style={{ backgroundColor: colors.primary, color: '#FFFFFF', minHeight: '2.2rem' }}
              >
                {left_column.heading}
              </div>
              <div className="flex-1 flex flex-col gap-1 p-2 overflow-hidden" style={{ backgroundColor: '#FFFFFF' }}>
                {left_column.bullets.map((item, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 rounded px-2 py-1.5"
                    style={{ backgroundColor: '#F0FFF4', border: '0.5px solid #C6F6D5' }}
                  >
                    <span className="flex-shrink-0 text-sm" style={{ color: '#38A169' }}>✓</span>
                    <span className="text-xs leading-snug" style={{ color: colors.text }}>{item}</span>
                  </div>
                ))}
              </div>
            </div>
            {/* Right column — cons style with red X */}
            <div
              className="flex-1 flex flex-col rounded overflow-hidden"
              style={{ border: '1px solid #E2E8F0', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}
            >
              <div
                className="flex items-center justify-center px-3 py-2 font-bold text-sm"
                style={{ backgroundColor: colors.secondary, color: '#FFFFFF', minHeight: '2.2rem' }}
              >
                {right_column.heading}
              </div>
              <div className="flex-1 flex flex-col gap-1 p-2 overflow-hidden" style={{ backgroundColor: '#FFFFFF' }}>
                {right_column.bullets.map((item, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 rounded px-2 py-1.5"
                    style={{ backgroundColor: '#FFF5F5', border: '0.5px solid #FED7D7' }}
                  >
                    <span className="flex-shrink-0 text-sm" style={{ color: '#E53E3E' }}>✗</span>
                    <span className="text-xs leading-snug" style={{ color: colors.text }}>{item}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )

      case 'before-after':
        return (
          <div className="flex-1 flex gap-3 px-4 py-3 overflow-hidden">
            {/* Left column — muted/grayed "before" */}
            <div
              className="flex-1 flex flex-col rounded overflow-hidden"
              style={{ border: '1px solid #E2E8F0', boxShadow: '0 2px 8px rgba(0,0,0,0.08)', opacity: 0.7 }}
            >
              <div
                className="flex items-center justify-center px-3 py-2 font-bold text-sm"
                style={{ backgroundColor: colors.muted, color: '#FFFFFF', minHeight: '2.2rem' }}
              >
                {left_column.heading}
              </div>
              <div className="flex-1 flex flex-col gap-1 p-2 overflow-hidden" style={{ backgroundColor: '#F7FAFC' }}>
                {left_column.bullets.map((item, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 rounded px-2 py-1.5"
                    style={{ backgroundColor: '#EDF2F7', border: '0.5px solid #E2E8F0' }}
                  >
                    <span className="font-bold flex-shrink-0 text-sm" style={{ color: colors.muted }}>›</span>
                    <span className="text-xs leading-snug" style={{ color: colors.muted }}>{item}</span>
                  </div>
                ))}
              </div>
            </div>
            {/* Arrow separator */}
            <div className="flex items-center justify-center" style={{ width: '1.5rem' }}>
              <span className="font-bold text-lg" style={{ color: colors.accent }}>→</span>
            </div>
            {/* Right column — accent-emphasized "after" */}
            <div
              className="flex-1 flex flex-col rounded overflow-hidden"
              style={{ border: `2px solid ${colors.accent}`, boxShadow: `0 2px 12px ${colors.accent}30` }}
            >
              <div
                className="flex items-center justify-center px-3 py-2 font-bold text-sm"
                style={{ backgroundColor: colors.accent, color: '#FFFFFF', minHeight: '2.2rem' }}
              >
                {right_column.heading}
              </div>
              <div className="flex-1 flex flex-col gap-1 p-2 overflow-hidden" style={{ backgroundColor: '#FFFFFF' }}>
                {right_column.bullets.map((item, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 rounded px-2 py-1.5"
                    style={{ backgroundColor: `${colors.accent}08`, border: `0.5px solid ${colors.accent}30` }}
                  >
                    <span className="font-bold flex-shrink-0 text-sm" style={{ color: colors.accent }}>›</span>
                    <span className="text-xs leading-snug font-medium" style={{ color: colors.text }}>{item}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )

      case 'icon-rows':
        return (
          <div className="flex-1 flex gap-3 px-4 py-3 overflow-hidden">
            {[left_column, right_column].map((col, colIdx) => (
              <div
                key={colIdx}
                className="flex-1 flex flex-col rounded overflow-hidden"
                style={{ border: '1px solid #E2E8F0', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}
              >
                <div
                  className="flex items-center justify-center px-3 py-2 font-bold text-sm"
                  style={{ backgroundColor: colIdx === 0 ? colors.primary : colors.secondary, color: '#FFFFFF', minHeight: '2.2rem' }}
                >
                  {col.heading}
                </div>
                <div className="flex-1 flex flex-col p-2 overflow-hidden" style={{ backgroundColor: '#FFFFFF' }}>
                  {col.bullets.map((item: any, i: number) => {
                    const title = typeof item === 'object' ? item.title : item
                    const desc = typeof item === 'object' ? item.description : undefined
                    return (
                      <div key={i}>
                        <div className="flex items-start gap-2 px-2 py-1.5">
                          <div
                            className="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center mt-0.5"
                            style={{ backgroundColor: `${colors.primary}15`, border: `1px solid ${colors.border}` }}
                          >
                            <span className="text-xs font-bold" style={{ color: colors.primary }}>{i + 1}</span>
                          </div>
                          <div className="flex-1 min-w-0">
                            <span className="text-xs font-semibold leading-snug" style={{ color: colors.text }}>{title}</span>
                            {desc && <p className="text-xs leading-snug mt-0.5" style={{ color: colors.muted }}>{desc}</p>}
                          </div>
                        </div>
                        {i < col.bullets.length - 1 && <div className="mx-2" style={{ height: '1px', backgroundColor: '#E2E8F0' }} />}
                      </div>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        )

      // Default: two-column (existing behavior)
      default:
        return (
          <div className="flex-1 flex gap-3 px-4 py-3 overflow-hidden">
            {renderDefaultColumn(left_column, 'left')}
            {renderDefaultColumn(right_column, 'right')}
          </div>
        )
    }
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

      {renderColumns()}
    </div>
  )
}
