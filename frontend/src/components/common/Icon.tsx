import React from 'react'
import * as LucideIcons from 'lucide-react'

/**
 * Icon Component
 * 
 * Renders Lucide React icons by name.
 * Converts kebab-case icon names (e.g., 'trending-up') to PascalCase (e.g., 'TrendingUp')
 * for Lucide React component lookup.
 */
interface IconProps {
  name: string
  size?: number
  color?: string
  strokeWidth?: number
  className?: string
}

export const Icon: React.FC<IconProps> = ({
  name,
  size = 24,
  color,
  strokeWidth = 1.5,
  className = '',
}) => {
  // Convert kebab-case to PascalCase
  // e.g., 'trending-up' -> 'TrendingUp'
  const pascalCaseName = name
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join('')

  const IconComponent = (LucideIcons as any)[pascalCaseName]

  if (!IconComponent) {
    console.warn(`Icon "${name}" (${pascalCaseName}) not found in Lucide React`)
    return null
  }

  return (
    <IconComponent
      size={size}
      color={color}
      strokeWidth={strokeWidth}
      className={className}
    />
  )
}
