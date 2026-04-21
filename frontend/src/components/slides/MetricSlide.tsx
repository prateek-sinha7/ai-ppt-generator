import React, { useEffect, useState } from 'react'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { SlideColors } from '../../utils/themeUtils'
import { Icon } from '../common/Icon'
import '../../styles/transitions.css'

interface MetricSlideProps {
  title: string
  metric_value?: string
  metric_label?: string
  metric_trend?: string
  bullets?: string[]
  colors: SlideColors
  icon_name?: string
  highlight_text?: string
  transition?: string
  className?: string
}

function useCountUp(target: string, duration = 1000) {
  const [display, setDisplay] = useState(target)
  useEffect(() => {
    const match = target.match(/[\d,.]+/)
    if (!match) { setDisplay(target); return }
    const numStr = match[0].replace(/,/g, '')
    const num = parseFloat(numStr)
    if (isNaN(num)) { setDisplay(target); return }
    const prefix = target.slice(0, target.indexOf(match[0]))
    const suffix = target.slice(target.indexOf(match[0]) + match[0].length)
    const steps = 30
    let step = 0
    const timer = setInterval(() => {
      step++
      const current = Math.min((num * step) / steps, num)
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
  colors,
  icon_name,
  transition = 'fade',
  className = '',
}) => {
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

      {/* Body */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: big metric card — matches builder.js */}
        <div
          className="flex flex-col items-center justify-center"
          style={{ width: '44%', backgroundColor: colors.primary, boxShadow: '4px 0 12px rgba(0,0,0,0.2)' }}
        >
          {icon_name && (
            <div className="mb-2">
              <Icon name={icon_name} size={28} color={colors.accent} />
            </div>
          )}
          {/* Big number */}
          <div
            className="font-black leading-none"
            style={{ color: '#FFFFFF', fontSize: '3rem' }}
          >
            {animatedValue}
          </div>
          {metric_label && (
            <div className="mt-1 text-xs font-semibold" style={{ color: colors.accent }}>
              {metric_label}
            </div>
          )}
          {/* Trend badge */}
          {metric_trend && (
            <div
              className="mt-2 flex items-center gap-1 px-3 py-1 rounded text-xs font-bold"
              style={{ backgroundColor: `${trendColor}25`, color: trendColor, border: `1px solid ${trendColor}50` }}
            >
              <TrendIcon className="w-3 h-3" />
              {metric_trend}
            </div>
          )}
        </div>

        {/* Right: numbered bullet cards — matches builder.js */}
        <div className="flex-1 flex flex-col justify-center gap-1.5 px-3 py-2 overflow-hidden">
          {bullets.slice(0, 4).map((b, i) => (
            <div
              key={i}
              className="flex items-stretch rounded overflow-hidden"
              style={{ backgroundColor: '#F8FAFC', border: '0.5px solid #E2E8F0', boxShadow: '0 1px 4px rgba(0,0,0,0.06)', minHeight: '2rem' }}
            >
              <div
                className="flex items-center justify-center font-bold flex-shrink-0"
                style={{ width: '1.8rem', backgroundColor: colors.primary, color: colors.accent, fontSize: '0.75rem' }}
              >
                {i + 1}
              </div>
              <span className="flex items-center px-2 text-xs leading-snug" style={{ color: colors.text }}>
                {b}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
