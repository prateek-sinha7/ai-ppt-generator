import React from 'react'
import { SlideData } from '../../types'
import { TitleSlide } from './TitleSlide'
import { ContentSlide } from './ContentSlide'
import { ChartSlide } from './ChartSlide'
import { TableSlide } from './TableSlide'
import { ComparisonSlide } from './ComparisonSlide'
import { MetricSlide } from './MetricSlide'

interface SlideRendererProps {
  slide: SlideData
  theme: 'mckinsey' | 'deloitte' | 'dark-modern'
  className?: string
}

export const SlideRenderer: React.FC<SlideRendererProps> = ({ slide, theme, className = '' }) => {
  switch (slide.type) {
    case 'title':
      return (
        <TitleSlide
          title={slide.title}
          subtitle={slide.subtitle}
          theme={theme}
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
          theme={theme}
          visual_hint="bullet-left"
          icon_name={slide.icon_name}
          highlight_text={slide.highlight_text}
          transition={slide.transition}
          className={className}
        />
      )

    case 'chart':
      if (!slide.chart_data || !slide.chart_type) {
        return (
          <ContentSlide
            title={slide.title}
            bullets={slide.bullets || ['Chart data unavailable']}
            theme={theme}
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
          theme={theme}
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
            theme={theme}
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
          theme={theme}
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
            theme={theme}
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
          theme={theme}
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
          theme={theme}
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
          theme={theme}
          visual_hint="bullet-left"
          icon_name={slide.icon_name}
          highlight_text={slide.highlight_text}
          transition={slide.transition}
          className={className}
        />
      )
  }
}
