import React from 'react'
import { SlideColors } from '../../utils/themeUtils'
import { Icon } from '../common/Icon'
import '../../styles/transitions.css'

interface ContentSlideProps {
  title: string
  bullets: string[]
  colors: SlideColors
  visual_hint: 'bullet-left'
  icon_name?: string
  highlight_text?: string
  transition?: string
  className?: string
  isDark?: boolean
  layout_variant?: string
}

export const ContentSlide: React.FC<ContentSlideProps> = ({
  title,
  bullets,
  colors,
  icon_name,
  highlight_text,
  transition = 'fade',
  className = '',
  isDark = false,
  layout_variant,
}) => {
  const transitionClass = `slide-transition-${transition}`
  const textColor = isDark ? '#FFFFFF' : colors.text

  // Resolve variant — fall back to numbered-cards (default)
  const variant = layout_variant || 'numbered-cards'

  const renderBullets = () => {
    switch (variant) {
      case 'icon-grid':
        return (
          <div className="flex-1 grid grid-cols-2 gap-2 px-4 py-3 overflow-hidden">
            {bullets.map((bullet, i) => (
              <div
                key={i}
                className="flex flex-col items-center justify-center text-center rounded p-2"
                style={{
                  backgroundColor: isDark ? '#112240' : '#F8FAFC',
                  border: `0.5px solid ${isDark ? colors.accent : '#E2E8F0'}`,
                  boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                }}
              >
                <div
                  className="flex items-center justify-center rounded-full mb-1.5"
                  style={{
                    width: '1.8rem',
                    height: '1.8rem',
                    backgroundColor: colors.primary,
                  }}
                >
                  <span className="text-xs font-bold" style={{ color: colors.accent }}>{i + 1}</span>
                </div>
                <span className="text-xs leading-snug" style={{ color: textColor }}>{bullet}</span>
              </div>
            ))}
          </div>
        )

      case 'two-column-text':
        const mid = Math.ceil(bullets.length / 2)
        const leftBullets = bullets.slice(0, mid)
        const rightBullets = bullets.slice(mid)
        return (
          <div className="flex-1 flex gap-3 px-4 py-3 overflow-hidden">
            {[leftBullets, rightBullets].map((col, colIdx) => (
              <div key={colIdx} className="flex-1 flex flex-col gap-1.5">
                {col.map((bullet, i) => (
                  <div
                    key={i}
                    className="flex items-stretch rounded overflow-hidden"
                    style={{
                      backgroundColor: isDark ? '#112240' : '#F8FAFC',
                      border: `0.5px solid ${isDark ? colors.accent : '#E2E8F0'}`,
                      boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                      minHeight: '2.2rem',
                    }}
                  >
                    <div
                      className="flex items-center justify-center font-bold flex-shrink-0"
                      style={{ width: '2rem', backgroundColor: colors.primary, color: colors.accent, fontSize: '0.8rem' }}
                    >
                      {colIdx * mid + i + 1}
                    </div>
                    <span className="flex items-center px-3 text-sm leading-snug" style={{ color: textColor }}>
                      {bullet}
                    </span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )

      case 'stat-callouts':
        return (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 px-4 py-3 overflow-hidden">
            {bullets.map((bullet, i) => (
              <div
                key={i}
                className="w-full text-center rounded py-3 px-4"
                style={{
                  backgroundColor: isDark ? '#112240' : '#F8FAFC',
                  border: `0.5px solid ${isDark ? colors.accent : '#E2E8F0'}`,
                  boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                }}
              >
                <span
                  className="font-bold leading-tight"
                  style={{ color: i === 0 ? colors.primary : textColor, fontSize: i === 0 ? '1.3rem' : '1rem' }}
                >
                  {bullet}
                </span>
              </div>
            ))}
          </div>
        )

      case 'timeline':
        return (
          <div className="flex-1 flex items-center px-4 py-3 overflow-hidden">
            <div className="flex items-start w-full gap-1">
              {bullets.map((bullet, i) => (
                <div key={i} className="flex-1 flex flex-col items-center text-center">
                  {/* Step number circle */}
                  <div
                    className="flex items-center justify-center rounded-full font-bold mb-1"
                    style={{
                      width: '1.6rem',
                      height: '1.6rem',
                      backgroundColor: colors.primary,
                      color: colors.accent,
                      fontSize: '0.7rem',
                    }}
                  >
                    {i + 1}
                  </div>
                  {/* Connector line */}
                  {i < bullets.length - 1 && (
                    <div
                      className="absolute"
                      style={{
                        width: '100%',
                        height: '2px',
                        backgroundColor: colors.primary,
                        opacity: 0.3,
                      }}
                    />
                  )}
                  <span className="text-xs leading-snug mt-1" style={{ color: textColor }}>{bullet}</span>
                </div>
              ))}
            </div>
          </div>
        )

      case 'quote-highlight': {
        const [quote, ...attribution] = bullets
        return (
          <div className="flex-1 flex flex-col justify-center px-6 py-4 overflow-hidden">
            {/* Large italic quote */}
            <div
              className="rounded px-4 py-3 mb-3"
              style={{
                backgroundColor: isDark ? '#112240' : '#F8FAFC',
                borderLeft: `4px solid ${colors.accent}`,
              }}
            >
              <span
                className="italic leading-relaxed"
                style={{ color: textColor, fontSize: '1.05rem' }}
              >
                &ldquo;{quote}&rdquo;
              </span>
            </div>
            {/* Attribution lines */}
            {attribution.map((line, i) => (
              <span
                key={i}
                className="text-xs leading-snug px-4"
                style={{ color: colors.muted }}
              >
                {line}
              </span>
            ))}
          </div>
        )
      }

      // Default: numbered-cards (existing behavior)
      default:
        return (
          <div className="flex-1 flex flex-col justify-center px-4 py-2 gap-1.5 overflow-hidden">
            {bullets.map((bullet, i) => (
              <div
                key={i}
                className="flex items-stretch rounded overflow-hidden"
                style={{
                  backgroundColor: isDark ? '#112240' : '#F8FAFC',
                  border: `0.5px solid ${isDark ? colors.accent : '#E2E8F0'}`,
                  boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                  minHeight: '2.2rem',
                }}
              >
                <div
                  className="flex items-center justify-center font-bold flex-shrink-0"
                  style={{
                    width: '2rem',
                    backgroundColor: `#${colors.primary.replace('#', '')}`,
                    color: colors.accent,
                    fontSize: '0.8rem',
                  }}
                >
                  {i + 1}
                </div>
                <span className="flex items-center px-3 text-sm leading-snug" style={{ color: textColor }}>
                  {bullet}
                </span>
              </div>
            ))}
          </div>
        )
    }
  }

  return (
    <div
      className={`slide-container ${transitionClass} ${className} relative flex flex-col overflow-hidden`}
      style={{ backgroundColor: isDark ? colors.bgDark : colors.bg }}
    >
      {/* Dark header bar — matches builder.js addHeader() */}
      <div
        className="flex-shrink-0 flex items-center px-4"
        style={{ backgroundColor: colors.bgDark, height: '13.3%', position: 'relative' }}
      >
        <h2
          className="font-bold tracking-wide truncate"
          style={{ color: '#FFFFFF', fontSize: '1.15rem', letterSpacing: '0.03em' }}
        >
          {title}
        </h2>
        {/* Icon circle top-right */}
        {icon_name && (
          <div
            className="absolute flex items-center justify-center rounded-full"
            style={{
              right: '3%', top: '50%', transform: 'translateY(-50%)',
              width: '2.2rem', height: '2.2rem',
              backgroundColor: `${colors.primary}CC`,
              border: `1px solid ${colors.accent}`,
            }}
          >
            <Icon name={icon_name} size={16} color={colors.accent} />
          </div>
        )}
      </div>
      {/* Accent line under header */}
      <div style={{ height: '1%', backgroundColor: colors.accent, flexShrink: 0 }} />

      {/* Variant-dispatched bullet rendering */}
      {renderBullets()}

      {/* Highlight callout — matches builder.js */}
      {highlight_text && (
        <div
          className="flex-shrink-0 flex items-center justify-center text-center px-4"
          style={{
            backgroundColor: colors.accent,
            height: '13%',
            boxShadow: '0 -2px 8px rgba(0,0,0,0.15)',
          }}
        >
          <span
            className="font-bold text-xs"
            style={{ color: isDark ? colors.bgDark : '#FFFFFF' }}
          >
            {highlight_text}
          </span>
        </div>
      )}
    </div>
  )
}
