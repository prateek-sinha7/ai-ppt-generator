// TypeScript interfaces for slide component props
// These define the Frontend_Data_Contract for all slide components

import { Theme, ChartType, ChartDataPoint, TableRow } from './index'

/**
 * Base props shared by all slide components
 */
export interface BaseSlideProps {
  theme: Theme
  className?: string
}

/**
 * Props for TitleSlide component
 * Visual hint: 'centered'
 */
export interface TitleSlideProps extends BaseSlideProps {
  title: string
  subtitle?: string
  visual_hint: 'centered'
  icon_name?: string
  transition?: 'fade' | 'slide' | 'none'
}

/**
 * Props for ContentSlide component
 * Visual hint: 'bullet-left'
 */
export interface ContentSlideProps extends BaseSlideProps {
  title: string
  bullets: string[] // max 4 items, max 8 words each
  visual_hint: 'bullet-left'
  icon_name?: string
  highlight_text?: string
  transition?: 'fade' | 'slide' | 'none'
}

/**
 * Props for ChartSlide component
 * Visual hint: 'split-chart-right'
 */
export interface ChartSlideProps extends BaseSlideProps {
  title: string
  chart_data: ChartDataPoint[]
  chart_type: ChartType
  visual_hint: 'split-chart-right'
  icon_name?: string
  highlight_text?: string
  transition?: 'fade' | 'slide' | 'none'
}

/**
 * Props for TableSlide component
 * Visual hint: 'split-table-left'
 */
export interface TableSlideProps extends BaseSlideProps {
  title: string
  table_headers: string[]
  table_rows: TableRow[]
  visual_hint: 'split-table-left'
  icon_name?: string
  highlight_text?: string
  transition?: 'fade' | 'slide' | 'none'
}

/**
 * Props for ComparisonSlide component
 * Visual hint: 'two-column'
 */
export interface ComparisonSlideProps extends BaseSlideProps {
  title: string
  left_column: {
    heading: string
    bullets: string[]
  }
  right_column: {
    heading: string
    bullets: string[]
  }
  visual_hint: 'two-column'
  icon_name?: string
  highlight_text?: string
  transition?: 'fade' | 'slide' | 'none'
}
