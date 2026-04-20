import React from 'react'
import { TitleSlideProps } from '../../types/slideProps'
import { getThemeColors } from '../../utils/themeUtils'
import { Icon } from '../common/Icon'
import '../../styles/transitions.css'

export const TitleSlide: React.FC<TitleSlideProps> = ({
  title,
  subtitle,
  theme,
  icon_name,
  transition = 'fade',
  className = '',
}) => {
  const colors = getThemeColors(theme)
  const transitionClass = `slide-transition-${transition}`

  return (
    <div
      className={`slide-container ${transitionClass} ${className} relative overflow-hidden flex flex-col`}
      style={{ backgroundColor: colors.bg }}
    >
      {/* Top accent bar */}
      <div className="h-2 w-full flex-shrink-0" style={{ backgroundColor: colors.primary }} />

      {/* Left accent stripe */}
      <div
        className="absolute left-0 top-2 bottom-0 w-1.5"
        style={{ backgroundColor: colors.accent }}
      />

      {/* Background decorative circle */}
      <div
        className="absolute -right-24 -bottom-24 w-96 h-96 rounded-full opacity-5"
        style={{ backgroundColor: colors.primary }}
      />
      <div
        className="absolute -right-12 -bottom-12 w-64 h-64 rounded-full opacity-5"
        style={{ backgroundColor: colors.secondary }}
      />

      {/* Content */}
      <div className="flex-1 flex items-center justify-center px-20 py-12">
        <div className="max-w-3xl w-full">
          {icon_name && (
            <div className="mb-6">
              <div
                className="inline-flex items-center justify-center w-16 h-16 rounded-2xl"
                style={{ backgroundColor: `${colors.primary}15` }}
              >
                <Icon name={icon_name} size={36} color={colors.primary} />
              </div>
            </div>
          )}

          <h1
            className="font-bold leading-tight mb-6"
            style={{ color: colors.text, fontSize: '2.8rem', lineHeight: '1.15' }}
          >
            {title}
          </h1>

          {subtitle && (
            <>
              <div className="w-16 h-1 rounded-full mb-5" style={{ backgroundColor: colors.primary }} />
              <p
                className="text-xl leading-relaxed"
                style={{ color: colors.muted }}
              >
                {subtitle}
              </p>
            </>
          )}
        </div>
      </div>

      {/* Bottom bar */}
      <div
        className="h-12 flex-shrink-0 flex items-center px-20"
        style={{ backgroundColor: colors.surface }}
      >
        <span className="text-xs font-medium tracking-widest uppercase" style={{ color: colors.muted }}>
          Confidential
        </span>
      </div>
    </div>
  )
}
