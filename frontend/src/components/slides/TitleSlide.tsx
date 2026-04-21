import React from 'react'
import { SlideColors } from '../../utils/themeUtils'
import { Icon } from '../common/Icon'
import '../../styles/transitions.css'

interface TitleSlideProps {
  title: string
  subtitle?: string
  bullets?: string[]
  colors: SlideColors
  visual_hint: 'centered'
  icon_name?: string
  transition?: string
  className?: string
}

export const TitleSlide: React.FC<TitleSlideProps> = ({
  title,
  subtitle,
  bullets = [],
  colors,
  icon_name,
  transition = 'fade',
  className = '',
}) => {
  const transitionClass = `slide-transition-${transition}`
  const kpis = bullets.slice(0, 4)

  return (
    <div
      className={`slide-container ${transitionClass} ${className} relative overflow-hidden flex flex-col`}
      style={{ backgroundColor: colors.bgDark }}
    >
      {/* Left accent stripe — matches builder.js */}
      <div
        className="absolute left-0 top-0 bottom-0"
        style={{ width: '1%', backgroundColor: colors.accent }}
      />

      {/* Decorative circles top-right — matches builder.js */}
      <div
        className="absolute rounded-full"
        style={{
          right: '-15%', top: '-20%',
          width: '45%', height: '80%',
          backgroundColor: colors.accent,
          opacity: 0.08,
          border: `1px solid ${colors.accent}`,
        }}
      />
      <div
        className="absolute rounded-full"
        style={{
          right: '-8%', top: '0%',
          width: '32%', height: '55%',
          backgroundColor: colors.accent,
          opacity: 0.05,
          border: `1px solid ${colors.accent}`,
        }}
      />

      {/* Icon top-right */}
      {icon_name && (
        <div className="absolute" style={{ right: '8%', top: '8%' }}>
          <Icon name={icon_name} size={56} color={colors.accent} />
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col justify-center pl-[6%] pr-[30%] pt-4">
        {/* Title */}
        <h1
          className="font-bold leading-tight tracking-wide"
          style={{ color: '#FFFFFF', fontSize: '2.2rem', letterSpacing: '0.05em' }}
        >
          {title}
        </h1>

        {/* Subtitle */}
        {subtitle && (
          <p
            className="mt-3 italic"
            style={{ color: colors.accent, fontSize: '1.1rem' }}
          >
            {subtitle}
          </p>
        )}

        {/* Divider */}
        <div
          className="mt-4"
          style={{ width: '35%', height: '3px', backgroundColor: colors.accent }}
        />
      </div>

      {/* KPI badge row — matches builder.js */}
      {kpis.length > 0 && (
        <div className="flex gap-2 px-[4%] pb-[4%]">
          {kpis.map((kpi, i) => (
            <div
              key={i}
              className="flex-1 flex items-center justify-center text-center rounded"
              style={{
                backgroundColor: '#112240',
                border: `1px solid ${colors.accent}`,
                padding: '8px 6px',
                minHeight: '60px',
                boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
              }}
            >
              <span style={{ color: '#FFFFFF', fontSize: '0.7rem', lineHeight: 1.3 }}>{kpi}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
