import React, { useEffect, useState } from 'react'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { getThemeColors } from '../../utils/themeUtils'
import { Icon } from '../common/Icon'
import '../../styles/transitions.css'

interface MetricSlideProps {
  title: string
  metric_value?: string
  metric_label?: string
  metric_trend?: string
  bullets?: string[]
  theme: 'mckinsey' | 'deloitte' | 'dark-modern'
  icon_name?: string
  highlight_text?: string
  transition?: string
  className?: string
}

/** Animated counter for numeric values */
function useCountUp(target: string, duration = 1200) {
  const [display, setDisplay] = useState('0')

  useEffect(() => {
    // Extract numeric part
    const match = target.match(/[\d,.]+/)
    if (!match) { setDisplay(target); return }
    const numStr = match[0].replace(/,/g, '')
    const num = parseFloat(numStr)
    if (isNaN(num)) { setDisplay(target); return }

    const prefix = target.slice(0, target.indexOf(match[0]))
    const suffix = target.slice(target.indexOf(match[0]) + match[0].length)
    const steps = 40
    const increment = num / steps
    let current = 0
    let step = 0

    const timer = setInterval(() => {
      step++
      current = Math.min(current + increment, num)
      const formatted = current >= 1000
        ? current.toLocaleString(undefined, { maximumFractionDigits: 1 })
        : current.toFixed(num % 1 !== 0 ? 1 : 0)
      setDisplay(`${prefix}${formatted}${suffix}`)
      if (step >= steps) clearInterval(timer)
    }, duration / steps)

    return () => clearInterval(timer)
  }, [target, duration])

  return display
}

export const MetricSlide: React.FC<MetricSlideProps> = ({
  title,
  metric_value = '',
  metric_label = '',
  metric_trend,
  bullets = [],
  theme,
  icon_name,
  highlight_text,
  transition = 'fade',
  className = '',
}) => {
  const colors = getThemeColors(theme)
  const transitionClass = `slide-transition-${transition}`
  const animatedValue = useCountUp(metric_value)

  const isPositive = metric_trend?.startsWith('+')
  const isNegative = metric_trend?.startsWith('-')

  const TrendIcon = isPositive ? TrendingUp : isNegative ? TrendingDown : Minus
  const trendColor = isPositive ? '#22c55e' : isNegative ? '#ef4444' : colors.muted

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
          KEY METRIC
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 flex gap-0 overflow-hidden">
        {/* Left: big metric */}
        <div
          className="flex-1 flex flex-col items-center justify-center px-10 py-8"
          style={{ background: `linear-gradient(135deg, ${colors.primary}08 0%, ${colors.secondary}08 100%)` }}
        >
          {/* Decorative ring */}
          <div
            className="relative flex items-center justify-center w-52 h-52 rounded-full mb-6"
            style={{
              border: `3px solid ${colors.primary}20`,
              boxShadow: `0 0 0 12px ${colors.primary}08, 0 0 0 24px ${colors.primary}04`,
            }}
          >
            <div className="text-center">
              <div
                className="font-black leading-none mb-1"
                style={{ color: colors.primary, fontSize: '3.2rem' }}
              >
                {animatedValue}
              </div>
              {metric_label && (
                <div className="text-sm font-semibold" style={{ color: colors.muted }}>
                  {metric_label}
                </div>
              )}
            </div>
          </div>

          {/* Trend badge */}
          {metric_trend && (
            <div
              className="flex items-center gap-2 px-5 py-2 rounded-full text-sm font-bold"
              style={{ backgroundColor: `${trendColor}15`, color: trendColor, border: `1px solid ${trendColor}30` }}
            >
              <TrendIcon className="w-4 h-4" />
              {metric_trend}
            </div>
          )}
        </div>

        {/* Right: context bullets */}
        <div
          className="w-64 flex-shrink-0 flex flex-col justify-center px-6 py-6 gap-3"
          style={{ backgroundColor: colors.surface, borderLeft: `1px solid ${colors.border}` }}
        >
          <p className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: colors.muted }}>
            Key Context
          </p>
          {bullets.map((bullet, i) => (
            <div key={i} className="flex items-start gap-3">
              <div
                className="flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold mt-0.5"
                style={{ backgroundColor: colors.primary, color: '#fff' }}
              >
                {i + 1}
              </div>
              <span className="text-sm leading-relaxed" style={{ color: colors.text }}>
                {bullet}
              </span>
            </div>
          ))}

          {highlight_text && (
            <div
              className="mt-3 rounded-xl p-3"
              style={{ backgroundColor: `${colors.primary}10`, border: `1px solid ${colors.primary}25` }}
            >
              <p className="text-xs font-semibold leading-relaxed" style={{ color: colors.primary }}>
                {highlight_text}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
