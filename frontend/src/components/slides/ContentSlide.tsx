import React from 'react'
import { ContentSlideProps } from '../../types/slideProps'
import { getThemeColors } from '../../utils/themeUtils'
import { Icon } from '../common/Icon'
import '../../styles/transitions.css'

export const ContentSlide: React.FC<ContentSlideProps> = ({
  title,
  bullets,
  theme,
  icon_name,
  highlight_text,
  transition = 'fade',
  className = '',
}) => {
  const colors = getThemeColors(theme)
  const transitionClass = `slide-transition-${transition}`

  return (
    <div
      className={`slide-container ${transitionClass} ${className} relative flex flex-col overflow-hidden`}
      style={{ backgroundColor: colors.bg }}
    >
      {/* Top accent bar */}
      <div className="h-1.5 w-full flex-shrink-0" style={{ backgroundColor: colors.primary }} />

      {/* Header */}
      <div
        className="flex items-center gap-4 px-12 py-5 flex-shrink-0"
        style={{ borderBottom: `1px solid ${colors.border}` }}
      >
        {icon_name && (
          <div
            className="flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center"
            style={{ backgroundColor: `${colors.primary}15` }}
          >
            <Icon name={icon_name} size={22} color={colors.primary} />
          </div>
        )}
        <h2
          className="font-bold flex-1 leading-tight"
          style={{ color: colors.text, fontSize: '1.6rem' }}
        >
          {title}
        </h2>
      </div>

      {/* Body */}
      <div className="flex-1 flex gap-8 px-12 py-8 overflow-hidden">
        {/* Bullets */}
        <div className="flex-1 flex flex-col justify-center space-y-4">
          {bullets.map((bullet, index) => (
            <div
              key={index}
              className="flex items-start gap-4 p-3 rounded-xl transition-colors"
              style={{ backgroundColor: index % 2 === 0 ? `${colors.primary}08` : 'transparent' }}
            >
              <div
                className="flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold mt-0.5"
                style={{ backgroundColor: colors.primary, color: '#fff' }}
              >
                {index + 1}
              </div>
              <span
                className="text-base leading-relaxed font-medium"
                style={{ color: colors.text }}
              >
                {bullet}
              </span>
            </div>
          ))}
        </div>

        {/* Highlight box */}
        {highlight_text && (
          <div
            className="w-56 flex-shrink-0 rounded-2xl p-5 flex flex-col justify-center"
            style={{
              backgroundColor: `${colors.primary}10`,
              border: `2px solid ${colors.primary}30`,
            }}
          >
            <div
              className="w-8 h-1 rounded-full mb-3"
              style={{ backgroundColor: colors.primary }}
            />
            <p
              className="text-sm font-semibold leading-relaxed"
              style={{ color: colors.primary }}
            >
              {highlight_text}
            </p>
          </div>
        )}
      </div>

      {/* Bottom bar */}
      <div
        className="h-8 flex-shrink-0 flex items-center px-12"
        style={{ backgroundColor: colors.surface, borderTop: `1px solid ${colors.border}` }}
      >
        <div className="w-2 h-2 rounded-full mr-2" style={{ backgroundColor: colors.primary }} />
        <span className="text-xs" style={{ color: colors.muted }}>
          {bullets.length} key points
        </span>
      </div>
    </div>
  )
}
