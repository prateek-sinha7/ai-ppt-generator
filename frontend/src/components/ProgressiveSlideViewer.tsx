import { useState, useEffect, useCallback, useRef } from 'react'
import {
  ChevronLeft, ChevronRight, BarChart2, Table, Columns,
  FileText, Star, Maximize2, Minimize2, MessageSquare, X,
  TrendingUp, Hash,
} from 'lucide-react'
import { SSEEvent } from '../hooks/useSSEStream'
import { SlideData, Theme, DesignSpec } from '../types'
import { SlideRenderer } from './slides/SlideRenderer'

interface ProgressiveSlideViewerProps {
  events: SSEEvent[]
  theme: Theme
  designSpec?: DesignSpec | null
}

function parseSlide(event: SSEEvent): SlideData {
  const slideData = event.data.slide
  const content = slideData.content || {}

  const typeMapping: Record<string, SlideData['type']> = {
    title: 'title', title_slide: 'title',
    content: 'content', content_slide: 'content',
    chart: 'chart', chart_slide: 'chart',
    table: 'table', table_slide: 'table',
    comparison: 'comparison', comparison_slide: 'comparison',
    metric: 'metric', metric_slide: 'metric',
  }
  const hintToType: Record<string, SlideData['type']> = {
    'centered': 'title', 'split-chart-right': 'chart',
    'split-table-left': 'table', 'two-column': 'comparison',
    'bullet-left': 'content', 'highlight-metric': 'metric',
  }
  const rawType = (slideData.slide_type || slideData.type || '').toLowerCase()
  let resolvedType: SlideData['type'] = typeMapping[rawType] || 'content'
  if (resolvedType === 'content' && slideData.visual_hint) {
    resolvedType = hintToType[slideData.visual_hint] || 'content'
  }

  let table_headers: string[] | undefined
  let table_rows: Record<string, string | number>[] | undefined
  if (content.table_data && typeof content.table_data === 'object') {
    const headers = content.table_data.headers || []
    table_headers = headers
    table_rows = (content.table_data.rows || []).map((row: (string | number)[]) => {
      if (Array.isArray(row)) {
        const obj: Record<string, string | number> = {}
        headers.forEach((h: string, i: number) => { obj[h] = row[i] ?? '' })
        return obj
      }
      return row as Record<string, string | number>
    })
  } else if (content.table_headers) {
    table_headers = content.table_headers
    table_rows = content.table_rows
  }

  let left_column = content.left_column
  let right_column = content.right_column
  if (content.comparison_data && typeof content.comparison_data === 'object') {
    left_column = content.comparison_data.left_column
    right_column = content.comparison_data.right_column
  }

  let chart_data = content.chart_data
  if (chart_data && !Array.isArray(chart_data)) {
    if (chart_data.labels && chart_data.datasets) {
      const labels = chart_data.labels as string[]
      const values = (chart_data.datasets[0]?.data || []) as number[]
      chart_data = labels.map((label: string, i: number) => ({ label, value: values[i] ?? 0 }))
    } else {
      chart_data = undefined
    }
  }

  return {
    id: slideData.slide_id || slideData.id || `slide-${event.data.slide_number}`,
    type: resolvedType,
    visual_hint: slideData.visual_hint,
    title: slideData.title,
    subtitle: slideData.subtitle || content.subtitle,
    bullets: content.bullets,
    chart_type: content.chart_type,
    chart_data,
    table_headers,
    table_rows,
    left_column,
    right_column,
    metric_value: content.metric_value,
    metric_label: content.metric_label,
    metric_trend: content.metric_trend,
    icon_name: content.icon_name,
    highlight_text: content.highlight_text,
    transition: content.transition || 'fade',
    layout_instructions: slideData.layout_instructions,
    speaker_notes: slideData.speaker_notes || content.speaker_notes,
  } as SlideData
}

function SlideTypeIcon({ type }: { type: SlideData['type'] }) {
  const cls = 'w-3 h-3'
  switch (type) {
    case 'chart': return <BarChart2 className={cls} />
    case 'table': return <Table className={cls} />
    case 'comparison': return <Columns className={cls} />
    case 'title': return <Star className={cls} />
    case 'metric': return <TrendingUp className={cls} />
    default: return <FileText className={cls} />
  }
}

const TYPE_COLORS: Record<string, string> = {
  title: '#6366f1', chart: '#0ea5e9', table: '#10b981',
  comparison: '#f59e0b', metric: '#ec4899', content: '#6b7280',
}

export default function ProgressiveSlideViewer({ events, theme, designSpec }: ProgressiveSlideViewerProps) {
  const [slides, setSlides] = useState<SlideData[]>([])
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0)
  const [declaredTotal, setDeclaredTotal] = useState<number | null>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [showNotes, setShowNotes] = useState(false)
  const [isTransitioning, setIsTransitioning] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const slideReadyEvents = events.filter((e) => e.type === 'slide_ready')
    if (slideReadyEvents.length === 0) return

    const bySlideNumber = new Map<number, SSEEvent>()
    slideReadyEvents.forEach((e) => {
      const num: number = e.data.slide?.slide_number ?? e.data.slide_number ?? 0
      bySlideNumber.set(num, e)
    })

    const sorted = Array.from(bySlideNumber.entries())
      .sort(([a], [b]) => a - b)
      .map(([, ev]) => parseSlide(ev))

    setSlides(sorted)

    const latestEvent = slideReadyEvents[slideReadyEvents.length - 1]
    const declared = latestEvent.data?.total_slides
    setDeclaredTotal(declared && declared > 0 ? declared : sorted.length)
  }, [events])

  const goTo = useCallback((index: number) => {
    if (index < 0 || index >= slides.length || isTransitioning) return
    setIsTransitioning(true)
    setTimeout(() => {
      setCurrentSlideIndex(index)
      setIsTransitioning(false)
    }, 150)
  }, [slides.length, isTransitioning])

  const handlePrevious = useCallback(() => goTo(currentSlideIndex - 1), [goTo, currentSlideIndex])
  const handleNext = useCallback(() => goTo(currentSlideIndex + 1), [goTo, currentSlideIndex])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') handlePrevious()
      else if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === ' ') handleNext()
      else if (e.key === 'f' || e.key === 'F') setIsFullscreen((v) => !v)
      else if (e.key === 'Escape') setIsFullscreen(false)
      else if (e.key === 'n' || e.key === 'N') setShowNotes((v) => !v)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handlePrevious, handleNext])

  // Fullscreen API
  useEffect(() => {
    if (isFullscreen && containerRef.current) {
      containerRef.current.requestFullscreen?.().catch(() => {})
    } else if (!isFullscreen && document.fullscreenElement) {
      document.exitFullscreen?.().catch(() => {})
    }
  }, [isFullscreen])

  useEffect(() => {
    const onFsChange = () => {
      if (!document.fullscreenElement) setIsFullscreen(false)
    }
    document.addEventListener('fullscreenchange', onFsChange)
    return () => document.removeEventListener('fullscreenchange', onFsChange)
  }, [])

  if (slides.length === 0) return null

  const currentSlide = slides[currentSlideIndex]
  const totalCount = declaredTotal ?? slides.length
  const isLoading = slides.length < totalCount
  const typeColor = TYPE_COLORS[currentSlide.type] || '#6b7280'

  return (
    <div
      ref={containerRef}
      className={`w-full ${isFullscreen ? 'fixed inset-0 z-50 bg-black flex flex-col' : 'max-w-6xl mx-auto px-8'}`}
    >
      <div className={`bg-white rounded-xl shadow-xl overflow-hidden border border-gray-200 flex flex-col ${isFullscreen ? 'flex-1 rounded-none border-0' : ''}`}>

        {/* ── Top toolbar ── */}
        <div className="bg-gray-50 px-5 py-2.5 border-b border-gray-200 flex items-center gap-3 flex-shrink-0">
          {/* Slide counter */}
          <div className="flex items-center gap-2">
            <Hash className="w-3.5 h-3.5 text-gray-400" />
            <span className="text-sm font-semibold text-gray-700">
              {currentSlideIndex + 1} <span className="text-gray-400 font-normal">/ {totalCount}</span>
            </span>
          </div>

          {/* Type badge */}
          <div
            className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full"
            style={{ backgroundColor: `${typeColor}15`, color: typeColor }}
          >
            <SlideTypeIcon type={currentSlide.type} />
            {currentSlide.type.toUpperCase()}
          </div>

          {isLoading && (
            <span className="text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full animate-pulse">
              {slides.length} loaded…
            </span>
          )}

          {/* Dot navigation */}
          <div className="flex-1 flex items-center justify-center gap-1.5 overflow-hidden">
            {slides.map((slide, index) => (
              <button
                key={slide.id}
                onClick={() => goTo(index)}
                title={slide.title}
                className="flex-shrink-0 transition-all duration-200"
                style={{
                  width: index === currentSlideIndex ? 20 : 8,
                  height: 8,
                  borderRadius: 4,
                  backgroundColor: index === currentSlideIndex
                    ? typeColor
                    : TYPE_COLORS[slide.type] + '60',
                }}
              />
            ))}
          </div>

          {/* Controls */}
          <div className="flex items-center gap-1">
            {currentSlide.speaker_notes && (
              <button
                onClick={() => setShowNotes((v) => !v)}
                title="Speaker notes (N)"
                className={`p-1.5 rounded-lg transition-colors ${showNotes ? 'bg-blue-100 text-blue-600' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'}`}
              >
                <MessageSquare className="w-4 h-4" />
              </button>
            )}
            <button
              onClick={() => setIsFullscreen((v) => !v)}
              title="Fullscreen (F)"
              className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            >
              {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            </button>
            <button
              onClick={handlePrevious}
              disabled={currentSlideIndex === 0}
              className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={handleNext}
              disabled={currentSlideIndex >= slides.length - 1}
              className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* ── Main area: slide + optional notes ── */}
        <div className={`flex flex-col ${isFullscreen ? 'flex-1' : ''}`}>
          {/* Slide canvas */}
          <div
            className={`relative bg-gray-100 ${isFullscreen ? 'flex-1' : 'aspect-video'}`}
            style={{ opacity: isTransitioning ? 0 : 1, transition: 'opacity 0.15s ease' }}
          >
            <div className="w-full h-full">
              <SlideRenderer
                slide={currentSlide}
                theme={theme}
                designSpec={designSpec}
                isDark={currentSlideIndex === 0 || currentSlideIndex === slides.length - 1}
                className="w-full h-full"
              />
            </div>
          </div>

          {/* Speaker notes panel */}
          {showNotes && currentSlide.speaker_notes && (
            <div className="border-t border-gray-200 bg-yellow-50 px-6 py-4 flex-shrink-0">
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 flex items-center gap-2">
                  <MessageSquare className="w-4 h-4 text-yellow-600" />
                  <span className="text-xs font-semibold text-yellow-700 uppercase tracking-wide">Speaker Notes</span>
                </div>
                <p className="text-sm text-gray-700 leading-relaxed flex-1">{currentSlide.speaker_notes}</p>
                <button onClick={() => setShowNotes(false)} className="flex-shrink-0 text-gray-400 hover:text-gray-600">
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* ── Thumbnail strip ── */}
        {!isFullscreen && (
          <div className="bg-gray-50 px-5 py-3 border-t border-gray-200 flex-shrink-0">
            <div className="flex gap-2 overflow-x-auto pb-1">
              {slides.map((slide, index) => {
                const tc = TYPE_COLORS[slide.type] || '#6b7280'
                return (
                  <button
                    key={slide.id}
                    onClick={() => goTo(index)}
                    title={slide.title}
                    className={`flex-shrink-0 w-20 h-14 rounded-lg border-2 transition-all flex flex-col items-center justify-center gap-1 relative overflow-hidden ${
                      index === currentSlideIndex ? 'shadow-md' : 'opacity-70 hover:opacity-100'
                    }`}
                    style={{
                      borderColor: index === currentSlideIndex ? tc : '#e5e7eb',
                      backgroundColor: index === currentSlideIndex ? `${tc}10` : '#fff',
                    }}
                  >
                    {/* Type color strip */}
                    <div className="absolute top-0 left-0 right-0 h-1" style={{ backgroundColor: tc }} />
                    <SlideTypeIcon type={slide.type} />
                    <span className="text-xs font-semibold" style={{ color: index === currentSlideIndex ? tc : '#9ca3af' }}>
                      {index + 1}
                    </span>
                  </button>
                )
              })}
              {isLoading && Array.from({ length: totalCount - slides.length }).map((_, i) => (
                <div key={`ph-${i}`} className="flex-shrink-0 w-20 h-14 rounded-lg border-2 border-dashed border-gray-200 flex items-center justify-center">
                  <span className="text-xs text-gray-300">…</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Slide title bar ── */}
        {!isFullscreen && (
          <div className="px-5 py-2 border-t border-gray-100 bg-white flex-shrink-0">
            <p className="text-sm font-semibold text-gray-700 truncate">{currentSlide.title}</p>
            {currentSlide.subtitle && (
              <p className="text-xs text-gray-400 truncate mt-0.5">{currentSlide.subtitle}</p>
            )}
          </div>
        )}

        {/* Fullscreen keyboard hint */}
        {isFullscreen && (
          <div className="bg-black bg-opacity-80 px-6 py-2 flex items-center justify-between flex-shrink-0">
            <p className="text-xs text-gray-400">
              ← → Navigate &nbsp;·&nbsp; F Fullscreen &nbsp;·&nbsp; N Notes &nbsp;·&nbsp; ESC Exit
            </p>
            <p className="text-xs text-gray-400">{currentSlide.title}</p>
          </div>
        )}
      </div>
    </div>
  )
}
