import React from 'react'
import { TableSlideProps } from '../../types/slideProps'
import { getThemeColors } from '../../utils/themeUtils'
import { Icon } from '../common/Icon'
import '../../styles/transitions.css'

export const TableSlide: React.FC<TableSlideProps> = ({
  title,
  table_headers,
  table_rows,
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
          DATA TABLE
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 flex gap-0 overflow-hidden">
        {/* Table */}
        <div className="flex-1 overflow-auto px-10 py-6">
          <table className="w-full border-collapse">
            <thead>
              <tr style={{ backgroundColor: colors.primary }}>
                {table_headers.map((header, index) => (
                  <th
                    key={index}
                    className="text-left px-4 py-3 text-sm font-semibold"
                    style={{ color: '#fff', borderBottom: `2px solid ${colors.primary}` }}
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table_rows.map((row, rowIndex) => (
                <tr
                  key={rowIndex}
                  className="transition-colors"
                  style={{
                    backgroundColor: rowIndex % 2 === 0 ? colors.bg : colors.surface,
                    borderBottom: `1px solid ${colors.border}`,
                  }}
                >
                  {table_headers.map((header, colIndex) => (
                    <td
                      key={colIndex}
                      className="px-4 py-3 text-sm"
                      style={{
                        color: colIndex === 0 ? colors.text : colors.muted,
                        fontWeight: colIndex === 0 ? 600 : 400,
                      }}
                    >
                      {row[header]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Right insight panel */}
        {highlight_text && (
          <div
            className="w-44 flex-shrink-0 flex flex-col justify-center px-5 py-6"
            style={{ backgroundColor: colors.surface, borderLeft: `1px solid ${colors.border}` }}
          >
            <div className="w-8 h-1 rounded-full mb-4" style={{ backgroundColor: colors.primary }} />
            <p className="text-xs font-semibold leading-relaxed" style={{ color: colors.primary }}>
              {highlight_text}
            </p>
            <div className="mt-4 pt-4" style={{ borderTop: `1px solid ${colors.border}` }}>
              <p className="text-xs" style={{ color: colors.muted }}>
                {table_rows.length} records
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
