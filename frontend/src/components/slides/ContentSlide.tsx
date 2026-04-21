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
}) => {
  const transitionClass = `slide-transition-${transition}`
  const textColor = isDark ? '#FFFFFF' : colors.text

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

      {/* Numbered bullet cards — matches builder.js */}
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
            {/* Number badge */}
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
            <span
              className="flex items-center px-3 text-sm leading-snug"
              style={{ color: textColor }}
            >
              {bullet}
            </span>
          </div>
        ))}
      </div>

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
