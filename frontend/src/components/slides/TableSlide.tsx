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
  layout_variant?: string
  bullets?: string[]
}

export const TableSlide: React.FC<TableSlideProps> = ({
  title,
  table_headers,
  table_rows,
  colors,
  highlight_text,
  transition = 'fade',
  className = '',
  layout_variant,
  bullets,
}) => {
  const transitionClass = `slide-transition-${transition}`

  const variant = layout_variant || 'table-full'

  const renderTable = (highlightFirstRow?: boolean) => (
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
        {table_rows.map((row, rowIndex) => {
          const isHighlighted = highlightFirstRow && rowIndex === 0
          return (
            <tr
              key={rowIndex}
              style={{
                backgroundColor: isHighlighted
                  ? `${colors.accent}20`
                  : rowIndex % 2 === 0 ? '#F8F9FA' : '#FFFFFF',
                borderBottom: '0.5px solid #E2E8F0',
                borderLeft: isHighlighted ? `3px solid ${colors.accent}` : 'none',
              }}
            >
              {table_headers.map((header, colIndex) => (
                <td
                  key={colIndex}
                  className="px-3 py-1.5"
                  style={{
                    color: isHighlighted ? colors.primary : colIndex === 0 ? colors.text : colors.muted,
                    fontWeight: isHighlighted ? 700 : colIndex === 0 ? 600 : 400,
                  }}
                >
                  {row[header]}
                </td>
              ))}
            </tr>
          )
        })}
      </tbody>
    </table>
  )

  const renderBody = () => {
    switch (variant) {
      case 'table-with-insights':
        return (
          <div className="flex-1 flex overflow-hidden">
            {/* Table */}
            <div className="flex-1 overflow-auto px-3 py-2">
              {renderTable()}
            </div>
            {/* Side bullets */}
            {bullets && bullets.length > 0 && (
              <div className="flex flex-col justify-center gap-1.5 py-2 px-3 overflow-hidden" style={{ width: '35%' }}>
                <div className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: colors.muted }}>
                  Key Insights
                </div>
                {bullets.map((bullet, i) => (
                  <div
                    key={i}
                    className="flex items-stretch rounded overflow-hidden"
                    style={{ backgroundColor: '#F8FAFC', border: '0.5px solid #E2E8F0', minHeight: '1.6rem' }}
                  >
                    <div style={{ width: '4px', backgroundColor: colors.accent, flexShrink: 0 }} />
                    <span className="flex items-center px-2 text-xs leading-snug" style={{ color: colors.text }}>
                      {bullet}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )

      case 'table-highlight':
        return (
          <div className="flex-1 overflow-auto px-4 py-2">
            {renderTable(true)}
          </div>
        )

      // Default: table-full
      default:
        return (
          <div className="flex-1 overflow-auto px-4 py-2">
            {renderTable()}
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
