// TypeScript interfaces for Slide_JSON and API contracts

// Export slide prop interfaces
export * from './slideProps'

export type VisualHint =
  | 'centered'
  | 'bullet-left'
  | 'split-chart-right'
  | 'split-table-left'
  | 'two-column'
  | 'highlight-metric'

export type SlideType = 'title' | 'content' | 'chart' | 'table' | 'comparison' | 'metric'

export type ChartType = 'bar' | 'line' | 'pie'

export type TransitionType = 'fade' | 'slide' | 'none'

export type Theme = 'mckinsey' | 'deloitte' | 'dark-modern'

export interface ChartDataPoint {
  label: string
  value: number
  [key: string]: string | number
}

export interface TableRow {
  [key: string]: string | number
}

export interface SlideData {
  id: string
  type: SlideType
  visual_hint: VisualHint
  title: string
  subtitle?: string
  bullets?: string[]
  chart_type?: ChartType
  chart_data?: ChartDataPoint[]
  table_headers?: string[]
  table_rows?: TableRow[]
  left_column?: { heading: string; bullets: string[] }
  right_column?: { heading: string; bullets: string[] }
  metric_value?: string
  metric_label?: string
  metric_trend?: string
  icon_name?: string
  highlight_text?: string
  transition?: TransitionType
  layout_instructions?: Record<string, string>
  speaker_notes?: string
}

export interface PresentationSlideJSON {
  schema_version: string
  presentation_id: string
  topic: string
  theme: Theme
  detected_industry: string
  detected_audience: string
  slides: SlideData[]
  metadata: {
    generated_at: string
    provider: string
    quality_score: number
    template_id?: string
  }
}

export interface GenerationStatus {
  job_id: string
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled'
  progress: number
  current_agent?: string
  detected_context?: {
    industry: string
    audience: string
    template_id: string
  }
  error?: string
}
