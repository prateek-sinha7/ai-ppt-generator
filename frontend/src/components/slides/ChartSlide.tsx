import React from 'react'
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  LabelList, Area, AreaChart,
} from 'recharts'
import { ChartSlideProps } from '../../types/slideProps'
import { getThemeColors, getChartColors } from '../../utils/themeUtils'
import { Icon } from '../common/Icon'
import '../../styles/transitions.css'

const CustomTooltip = ({ active, payload, label, colors }: any) => {
  if (active && payload && payload.length) {
    return (
      <div
        className="rounded-xl shadow-lg px-4 py-3 text-sm"
        style={{ backgroundColor: colors.surface, border: `1px solid ${colors.border}`, color: colors.text }}
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
  theme,
  icon_name,
  highlight_text,
  transition = 'fade',
  className = '',
}) => {
  const colors = getThemeColors(theme)
  const chartColors = getChartColors(theme)
  const transitionClass = `slide-transition-${transition}`

  // Compute min/max for context
  const values = chart_data.map((d) => d.value)
  const maxVal = Math.max(...values)
  const minVal = Math.min(...values)
  const avgVal = values.reduce((a, b) => a + b, 0) / values.length

  const renderChart = () => {
    switch (chart_type) {
      case 'bar':
        return (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chart_data} margin={{ top: 20, right: 20, left: 0, bottom: 20 }} barCategoryGap="30%">
              <CartesianGrid strokeDasharray="3 3" stroke={`${colors.border}`} vertical={false} />
              <XAxis dataKey="label" stroke={colors.muted} tick={{ fontSize: 11, fill: colors.muted }} axisLine={false} tickLine={false} />
              <YAxis stroke={colors.muted} tick={{ fontSize: 11, fill: colors.muted }} axisLine={false} tickLine={false} width={40} />
              <Tooltip content={<CustomTooltip colors={colors} />} cursor={{ fill: `${colors.primary}10` }} />
              <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                {chart_data.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={entry.value === maxVal ? colors.primary : entry.value === minVal ? colors.accent : chartColors[index % chartColors.length]}
                    fillOpacity={entry.value === maxVal ? 1 : 0.75}
                  />
                ))}
                <LabelList dataKey="value" position="top" style={{ fontSize: 10, fill: colors.muted }} formatter={(v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 1 })} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )

      case 'line':
        return (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chart_data} margin={{ top: 20, right: 20, left: 0, bottom: 20 }}>
              <defs>
                <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={colors.primary} stopOpacity={0.2} />
                  <stop offset="95%" stopColor={colors.primary} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={colors.border} vertical={false} />
              <XAxis dataKey="label" stroke={colors.muted} tick={{ fontSize: 11, fill: colors.muted }} axisLine={false} tickLine={false} />
              <YAxis stroke={colors.muted} tick={{ fontSize: 11, fill: colors.muted }} axisLine={false} tickLine={false} width={40} />
              <Tooltip content={<CustomTooltip colors={colors} />} />
              <Area type="monotone" dataKey="value" stroke={colors.primary} strokeWidth={3} fill="url(#lineGrad)" dot={{ fill: colors.primary, r: 5, strokeWidth: 2, stroke: '#fff' }} activeDot={{ r: 7 }} />
            </AreaChart>
          </ResponsiveContainer>
        )

      case 'pie':
        return (
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chart_data}
                dataKey="value"
                nameKey="label"
                cx="50%"
                cy="50%"
                innerRadius="35%"
                outerRadius="65%"
                paddingAngle={3}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                labelLine={{ stroke: colors.muted, strokeWidth: 1 }}
              >
                {chart_data.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={chartColors[index % chartColors.length]} stroke="none" />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip colors={colors} />} />
              <Legend wrapperStyle={{ fontSize: 11, color: colors.muted }} />
            </PieChart>
          </ResponsiveContainer>
        )

      default:
        return null
    }
  }

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
          {chart_type?.toUpperCase()} CHART
        </div>
      </div>

      {/* Body: left insight + right chart */}
      <div className="flex-1 flex gap-0 overflow-hidden">
        {/* Left: stats + insight */}
        <div
          className="w-48 flex-shrink-0 flex flex-col justify-center gap-4 px-6 py-6"
          style={{ backgroundColor: colors.surface, borderRight: `1px solid ${colors.border}` }}
        >
          {/* Key stats */}
          <div className="space-y-3">
            <div className="rounded-xl p-3" style={{ backgroundColor: colors.bg }}>
              <p className="text-xs font-medium mb-1" style={{ color: colors.muted }}>MAX</p>
              <p className="text-lg font-bold" style={{ color: colors.primary }}>
                {maxVal.toLocaleString(undefined, { maximumFractionDigits: 1 })}
              </p>
            </div>
            <div className="rounded-xl p-3" style={{ backgroundColor: colors.bg }}>
              <p className="text-xs font-medium mb-1" style={{ color: colors.muted }}>AVG</p>
              <p className="text-lg font-bold" style={{ color: colors.secondary }}>
                {avgVal.toLocaleString(undefined, { maximumFractionDigits: 1 })}
              </p>
            </div>
            <div className="rounded-xl p-3" style={{ backgroundColor: colors.bg }}>
              <p className="text-xs font-medium mb-1" style={{ color: colors.muted }}>MIN</p>
              <p className="text-lg font-bold" style={{ color: colors.accent }}>
                {minVal.toLocaleString(undefined, { maximumFractionDigits: 1 })}
              </p>
            </div>
          </div>

          {highlight_text && (
            <div
              className="rounded-xl p-3 mt-2"
              style={{ backgroundColor: `${colors.primary}12`, border: `1px solid ${colors.primary}30` }}
            >
              <div className="w-6 h-0.5 rounded mb-2" style={{ backgroundColor: colors.primary }} />
              <p className="text-xs font-semibold leading-relaxed" style={{ color: colors.primary }}>
                {highlight_text}
              </p>
            </div>
          )}
        </div>

        {/* Right: chart */}
        <div className="flex-1 p-6">
          {renderChart()}
        </div>
      </div>
    </div>
  )
}
