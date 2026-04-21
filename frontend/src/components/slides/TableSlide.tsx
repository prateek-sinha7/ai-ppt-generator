import React from 'react'
import { SlideColors } from '../../utils/themeUtils'
import { TableRow } from '../../types'
import '../../styles/transitions.css'

interface TableSlideProps {
  title: string
  table_headers: string[]
  table_rows: TableRow[]
  colors: SlideColors
  visual_hint: 'split-table-left'
  icon_name?: string
  highlight_text?: string
  transition?: string
  className?: string
}

export const TableSlide: React.FC<TableSlideProps> = ({
  title,
  table_headers,
  table_rows,
  colors,
  highlight_text,
  transition = 'fade',
  className = '',
}) => {
  const transitionClass = `slide-transition-${transition}`

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

      {/* Table */}
      <div className="flex-1 overflow-auto px-4 py-2">
        <table className="w-full border-collapse text-xs">
          <thead>
            <tr style={{ backgroundColor: colors.primary }}>
              {table_headers.map((header, index) => (
                <th
                  key={index}
                  className="text-left px-3 py-2 font-semibold"
                  style={{ color: '#fff' }}
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
                style={{
                  backgroundColor: rowIndex % 2 === 0 ? '#F8F9FA' : '#FFFFFF',
                  borderBottom: '0.5px solid #E2E8F0',
                }}
              >
                {table_headers.map((header, colIndex) => (
                  <td
                    key={colIndex}
                    className="px-3 py-1.5"
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

      {/* Highlight callout */}
      {highlight_text && (
        <div
          className="flex-shrink-0 flex items-center justify-center text-center px-4"
          style={{ backgroundColor: colors.accent, height: '12%', boxShadow: '0 -2px 8px rgba(0,0,0,0.1)' }}
        >
          <span className="font-bold text-xs" style={{ color: '#FFFFFF' }}>{highlight_text}</span>
        </div>
      )}
    </div>
  )
}
