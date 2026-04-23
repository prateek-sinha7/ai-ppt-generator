import React from 'react'
import { SlideData, DesignSpec } from '../../types'
import { resolveColors, SlideColors } from '../../utils/themeUtils'
import { TitleSlide } from './TitleSlide'
import { ContentSlide } from './ContentSlide'
import { ChartSlide } from './ChartSlide'
import { TableSlide } from './TableSlide'
import { ComparisonSlide } from './ComparisonSlide'
import { MetricSlide } from './MetricSlide'

interface SlideRendererProps {
  slide: SlideData
  theme: 'executive' | 'professional' | 'dark-modern' | 'corporate'
  designSpec?: DesignSpec | null
  /** Whether this is the first or last slide (dark background sandwich) */
  isDark?: boolean
  className?: string
}

export const SlideRenderer: React.FC<SlideRendererProps> = ({
  slide,
  theme,
  designSpec,
  isDark = false,
  className = '',
}) => {
  const colors: SlideColors = resolveColors(theme, designSpec)

  // Dark sandwich: title slides and slides marked isDark use backgroundDark
  const darkColors: SlideColors = isDark
    ? { ...colors, bg: colors.bgDark, text: '#FFFFFF', muted: 'rgba(255,255,255,0.65)', surface: 'rgba(255,255,255,0.08)', border: 'rgba(255,255,255,0.15)' }
    : colors

  switch (slide.type) {
    case 'title':
      return (
        <TitleSlide
          title={slide.title}
          subtitle={slide.subtitle}
          bullets={slide.bullets}
          colors={darkColors}
          visual_hint="centered"
          icon_name={slide.icon_name}
          transition={slide.transition}
          className={className}
        />
      )

    case 'content':
      return (
        <ContentSlide
          title={slide.title}
          bullets={slide.bullets || []}
          colors={darkColors}
          visual_hint="bullet-left"
          icon_name={slide.icon_name}
          highlight_text={slide.highlight_text}
          transition={slide.transition}
          isDark={isDark}
          className={className}
        />
      )

    case 'chart':
      if (!slide.chart_data || !slide.chart_type) {
        return (
          <ContentSlide
            title={slide.title}
            bullets={slide.bullets || ['Chart data unavailable']}
            colors={darkColors}
            visual_hint="bullet-left"
            icon_name={slide.icon_name}
            highlight_text={slide.highlight_text}
            transition={slide.transition}
            className={className}
          />
        )
      }
      return (
        <ChartSlide
          title={slide.title}
          chart_data={slide.chart_data}
          chart_type={slide.chart_type}
          colors={darkColors}
          visual_hint="split-chart-right"
          icon_name={slide.icon_name}
          highlight_text={slide.highlight_text}
          transition={slide.transition}
          className={className}
        />
      )

    case 'table':
      if (!slide.table_headers || !slide.table_rows) {
        return (
          <ContentSlide
            title={slide.title}
            bullets={slide.bullets || ['Table data unavailable']}
            colors={darkColors}
            visual_hint="bullet-left"
            icon_name={slide.icon_name}
            highlight_text={slide.highlight_text}
            transition={slide.transition}
            className={className}
          />
        )
      }
      return (
        <TableSlide
          title={slide.title}
          table_headers={slide.table_headers}
          table_rows={slide.table_rows}
          colors={darkColors}
          visual_hint="split-table-left"
          icon_name={slide.icon_name}
          highlight_text={slide.highlight_text}
          transition={slide.transition}
          className={className}
        />
      )

    case 'comparison':
      if (!slide.left_column || !slide.right_column) {
        return (
          <ContentSlide
            title={slide.title}
            bullets={slide.bullets || ['Comparison data unavailable']}
            colors={darkColors}
            visual_hint="bullet-left"
            icon_name={slide.icon_name}
            highlight_text={slide.highlight_text}
            transition={slide.transition}
            className={className}
          />
        )
      }
      return (
        <ComparisonSlide
          title={slide.title}
          left_column={slide.left_column}
          right_column={slide.right_column}
          colors={darkColors}
          visual_hint="two-column"
          icon_name={slide.icon_name}
          highlight_text={slide.highlight_text}
          transition={slide.transition}
          className={className}
        />
      )

    case 'metric':
      return (
        <MetricSlide
          title={slide.title}
          metric_value={slide.metric_value}
          metric_label={slide.metric_label}
          metric_trend={slide.metric_trend}
          bullets={slide.bullets || []}
          colors={darkColors}
          icon_name={slide.icon_name}
          highlight_text={slide.highlight_text}
          transition={slide.transition}
          className={className}
        />
      )

    default:
      return (
        <ContentSlide
          title={slide.title}
          bullets={slide.bullets || []}
          colors={darkColors}
          visual_hint="bullet-left"
          icon_name={slide.icon_name}
          highlight_text={slide.highlight_text}
          transition={slide.transition}
          isDark={isDark}
          className={className}
        />
      )
  }
}
