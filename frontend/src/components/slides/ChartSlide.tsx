import React from 'react'
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  LabelList, Area, AreaChart,
} from 'recharts'
import { SlideColors } from '../../utils/themeUtils'
import { ChartDataPoint, ChartType } from '../../types'
import '../../styles/transitions.css'

interface ChartSlideProps {
  title: string
  chart_data: ChartDataPoint[]
  chart_type: ChartType
  colors: SlideColors
  visual_hint: 'split-chart-right'
  icon_name?: string
  highlight_text?: string
  transition?: string
  className?: string
  layout_variant?: string
}

const CustomTooltip = ({ active, payload, label, colors }: any) => {
  if (active && payload && payload.length) {
    return (
      <div
        className="rounded shadow-lg px-3 py-2 text-xs"
        style={{ backgroundColor: '#FFFFFF', border: `1px solid ${colors.border}`, color: colors.text }}
      >
        <p className="font-semibold mb-1">{label}</p>
        {payload.map((p: any, i: number) => (
          <p key={i} style={{ color: p.fill || p.stroke }}>
            {p.value?.toLocaleString(undefined, { maximumFractionDigits: 1 })}
          </p>
        ))}
      </div>
    )
  }
  return null
}

export const ChartSlide: React.FC<ChartSlideProps> = ({
  title,
  chart_data,
  chart_type,
  colors,
  highlight_text,
  transition = 'fade',
  className = '',
  layout_variant,
}) => {
  const transitionClass = `slide-transition-${transition}`
  const chartColors = colors.chartColors

  const variant = layout_variant || 'chart-right'

  const renderChart = () => {
    switch (chart_type) {
      case 'bar':
        return (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chart_data} margin={{ top: 12, right: 12, left: 0, bottom: 16 }} barCategoryGap="30%">
              <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
              <XAxis dataKey="label" stroke={colors.muted} tick={{ fontSize: 9, fill: colors.muted }} axisLine={false} tickLine={false} />
              <YAxis stroke={colors.muted} tick={{ fontSize: 9, fill: colors.muted }} axisLine={false} tickLine={false} width={32} />
              <Tooltip content={<CustomTooltip colors={colors} />} cursor={{ fill: `${colors.primary}10` }} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {chart_data.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={chartColors[index % chartColors.length]} fillOpacity={0.9} />
                ))}
                <LabelList dataKey="value" position="top" style={{ fontSize: 8, fill: colors.muted }} formatter={(v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 1 })} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )
      case 'line':
        return (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chart_data} margin={{ top: 12, right: 12, left: 0, bottom: 16 }}>
              <defs>
                <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={colors.primary} stopOpacity={0.2} />
                  <stop offset="95%" stopColor={colors.primary} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
              <XAxis dataKey="label" stroke={colors.muted} tick={{ fontSize: 9, fill: colors.muted }} axisLine={false} tickLine={false} />
              <YAxis stroke={colors.muted} tick={{ fontSize: 9, fill: colors.muted }} axisLine={false} tickLine={false} width={32} />
              <Tooltip content={<CustomTooltip colors={colors} />} />
              <Area type="monotone" dataKey="value" stroke={colors.primary} strokeWidth={2} fill="url(#chartGrad)" dot={{ fill: colors.primary, r: 3 }} />
            </AreaChart>
          </ResponsiveContainer>
        )
      case 'pie':
        return (
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={chart_data} dataKey="value" nameKey="label" cx="50%" cy="50%" innerRadius="30%" outerRadius="60%" paddingAngle={2}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                labelLine={{ stroke: colors.muted, strokeWidth: 1 }}
              >
                {chart_data.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={chartColors[index % chartColors.length]} stroke="none" />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip colors={colors} />} />
              <Legend wrapperStyle={{ fontSize: 9, color: colors.muted }} />
            </PieChart>
          </ResponsiveContainer>
        )
      default:
        return null
    }
  }

  const renderInsightsPanel = () => (
    <div className="flex flex-col justify-center gap-1.5 py-2 px-3 overflow-hidden" style={{ width: '38%' }}>
      <div className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: colors.muted }}>
        Data Insights
      </div>
      {chart_data.slice(0, 4).map((d, i) => (
        <div
          key={i}
          className="flex items-stretch rounded overflow-hidden"
          style={{ backgroundColor: '#F8FAFC', border: '0.5px solid #E2E8F0', minHeight: '1.8rem' }}
        >
          <div style={{ width: '4px', backgroundColor: colors.accent, flexShrink: 0 }} />
          <span className="flex items-center px-2 text-xs leading-snug" style={{ color: colors.text }}>
            <strong style={{ color: colors.primary, marginRight: '4px' }}>{d.label}:</strong>
            {d.value.toLocaleString(undefined, { maximumFractionDigits: 1 })}
          </span>
        </div>
      ))}
      {highlight_text && (
        <div
          className="mt-1 flex items-center justify-center text-center rounded px-2 py-1.5"
          style={{ backgroundColor: colors.secondary, boxShadow: '0 2px 6px rgba(0,0,0,0.12)' }}
        >
          <span className="font-bold text-xs" style={{ color: '#FFFFFF' }}>{highlight_text}</span>
        </div>
      )}
    </div>
  )

  const renderBody = () => {
    switch (variant) {
      case 'chart-full':
        return (
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="flex-1 p-3">
              {renderChart()}
            </div>
            {highlight_text && (
              <div
                className="flex-shrink-0 flex items-center justify-center text-center px-4 py-1.5"
                style={{ backgroundColor: colors.secondary, boxShadow: '0 -2px 6px rgba(0,0,0,0.1)' }}
              >
                <span className="font-bold text-xs" style={{ color: '#FFFFFF' }}>{highlight_text}</span>
              </div>
            )}
          </div>
        )

      case 'chart-top':
        return (
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Chart on top */}
            <div className="flex-1 p-3" style={{ minHeight: '55%' }}>
              {renderChart()}
            </div>
            {/* Bullets below */}
            <div className="flex-shrink-0 flex gap-2 px-3 pb-2 overflow-hidden">
              {chart_data.slice(0, 4).map((d, i) => (
                <div
                  key={i}
                  className="flex-1 flex items-stretch rounded overflow-hidden"
                  style={{ backgroundColor: '#F8FAFC', border: '0.5px solid #E2E8F0', minHeight: '1.6rem' }}
                >
                  <div style={{ width: '3px', backgroundColor: chartColors[i % chartColors.length], flexShrink: 0 }} />
                  <span className="flex items-center px-2 text-xs leading-snug" style={{ color: colors.text }}>
                    <strong style={{ color: colors.primary, marginRight: '4px' }}>{d.label}:</strong>
                    {d.value.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )

      case 'chart-with-kpi': {
        // Show a large KPI number alongside the chart
        const maxItem = chart_data.reduce((max, d) => d.value > max.value ? d : max, chart_data[0])
        return (
          <div className="flex-1 flex overflow-hidden">
            {/* KPI panel */}
            <div className="flex flex-col items-center justify-center px-4" style={{ width: '30%' }}>
              <span
                className="font-bold"
                style={{ fontSize: '2rem', color: colors.primary, lineHeight: 1.1 }}
              >
                {maxItem?.value.toLocaleString(undefined, { maximumFractionDigits: 1 })}
              </span>
              <span className="text-xs mt-1 text-center" style={{ color: colors.muted }}>
                {maxItem?.label}
              </span>
              {highlight_text && (
                <div
                  className="mt-2 rounded px-2 py-1 text-center"
                  style={{ backgroundColor: colors.accent }}
                >
                  <span className="font-bold text-xs" style={{ color: '#FFFFFF' }}>{highlight_text}</span>
                </div>
              )}
            </div>
            {/* Chart */}
            <div className="flex-1 p-3">
              {renderChart()}
            </div>
          </div>
        )
      }

      // Default: chart-right (existing behavior)
      default:
        return (
          <div className="flex-1 flex overflow-hidden">
            {renderInsightsPanel()}
            <div className="flex-1 p-3">
              {renderChart()}
            </div>
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

      {renderBody()}
    </div>
  )
}
