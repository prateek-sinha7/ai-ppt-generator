import React from 'react'
import { Theme } from '../../types'
import { getThemeColors } from '../../utils/themeUtils'
import '../../styles/transitions.css'

/**
 * HighlightBox Component
 * 
 * Renders a themed callout box for highlighting key information.
 * Used across multiple slide types for emphasis.
 */
interface HighlightBoxProps {
  text: string
  theme: Theme
  className?: string
}

export const HighlightBox: React.FC<HighlightBoxProps> = ({
  text,
  theme,
  className = '',
}) => {
  const colors = getThemeColors(theme)

  return (
    <div
      className={`highlight-box ${className}`}
      style={{
        backgroundColor: colors.highlight,
        borderLeftColor: colors.accent,
        color: colors.text,
      }}
    >
      {text}
    </div>
  )
}
