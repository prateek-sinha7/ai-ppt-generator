import { useState, useCallback } from 'react'
import {
  Edit2,
  Download,
  Clock,
  MessageSquare,
  GripVertical,
  Lock,
} from 'lucide-react'
import { SlideData, Theme } from '../types'
import { SlideRenderer } from './slides/SlideRenderer'
import DraggableSlideList from './DraggableSlideList'
import SlideEditPanel from './SlideEditPanel'
import ExportPreviewPanel from './ExportPreviewPanel'
import VersionHistoryPanel from './VersionHistoryPanel'
import CollaborationPanel from './CollaborationPanel'
import SlideLockIndicator from './SlideLockIndicator'

type ActivePanel = 'edit' | 'export' | 'history' | 'collaboration' | null

interface PresentationEditorProps {
  presentationId: string
  initialSlides: SlideData[]
  theme: Theme
  currentVersion?: number
}

export default function PresentationEditor({
  presentationId,
  initialSlides,
  theme,
  currentVersion = 1,
}: PresentationEditorProps) {
  const [slides, setSlides] = useState<SlideData[]>(initialSlides)
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0)
  const [activePanel, setActivePanel] = useState<ActivePanel>(null)
  const [lockedSlideIds, setLockedSlideIds] = useState<Set<string>>(new Set())
  const [lockedByMap, setLockedByMap] = useState<Record<string, string>>({})
  const [showReorderPanel, setShowReorderPanel] = useState(false)

  const currentSlide = slides[currentSlideIndex]

  const togglePanel = (panel: ActivePanel) => {
    setActivePanel((prev) => (prev === panel ? null : panel))
  }

  const handleReorder = useCallback((reordered: SlideData[]) => {
    setSlides(reordered)
  }, [])

  const handleSlideSaved = useCallback((updated: SlideData) => {
    setSlides((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
    setActivePanel(null)
  }, [])

  const handleLockChange = useCallback((slideId: string, locked: boolean) => {
    setLockedSlideIds((prev) => {
      const next = new Set(prev)
      if (locked) next.add(slideId)
      else next.delete(slideId)
      return next
    })
    if (!locked) {
      setLockedByMap((prev) => {
        const next = { ...prev }
        delete next[slideId]
        return next
      })
    }
  }, [])

  const handleRollback = useCallback((version: number) => {
    console.info(`Rolled back to version ${version}`)
    // Parent should reload slides after rollback
  }, [])

  const isCurrentSlideLocked = currentSlide ? lockedSlideIds.has(currentSlide.id) : false

  return (
    <div className="flex h-screen bg-gray-100 overflow-hidden">
      {/* ── Left sidebar: slide list ── */}
      <div className="w-64 bg-white border-r border-gray-200 flex flex-col flex-shrink-0">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <h3 className="text-sm font-semibold text-gray-700">Slides</h3>
          <button
            onClick={() => setShowReorderPanel((v) => !v)}
            title="Reorder slides"
            className={`p-1.5 rounded transition-colors ${
              showReorderPanel ? 'bg-blue-100 text-blue-600' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
            }`}
          >
            <GripVertical className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-3">
          {showReorderPanel ? (
            <DraggableSlideList
              presentationId={presentationId}
              slides={slides}
              lockedSlideIds={lockedSlideIds}
              theme={theme}
              onReorder={handleReorder}
            />
          ) : (
            <div className="space-y-1.5">
              {slides.map((slide, index) => (
                <button
                  key={slide.id}
                  onClick={() => setCurrentSlideIndex(index)}
                  className={`w-full text-left flex items-center gap-2 p-2 rounded-lg transition-colors ${
                    index === currentSlideIndex
                      ? 'bg-blue-50 border border-blue-200'
                      : 'hover:bg-gray-50 border border-transparent'
                  }`}
                >
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-gray-100 flex items-center justify-center text-xs font-semibold text-gray-500">
                    {index + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-gray-800 truncate">{slide.title}</p>
                    <p className="text-xs text-gray-400 capitalize">{slide.type}</p>
                  </div>
                  {lockedSlideIds.has(slide.id) && (
                    <Lock className="w-3 h-3 text-amber-500 flex-shrink-0" />
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Main content area ── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Toolbar */}
        <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            {currentSlide && (
              <SlideLockIndicator
                presentationId={presentationId}
                slideId={currentSlide.id}
                isLocked={isCurrentSlideLocked}
                lockedBy={lockedByMap[currentSlide.id]}
                onLockChange={handleLockChange}
              />
            )}
          </div>

          <div className="flex items-center gap-2">
            <ToolbarButton
              icon={<Edit2 className="w-4 h-4" />}
              label="Edit"
              active={activePanel === 'edit'}
              disabled={isCurrentSlideLocked}
              onClick={() => togglePanel('edit')}
            />
            <ToolbarButton
              icon={<Download className="w-4 h-4" />}
              label="Export"
              active={activePanel === 'export'}
              onClick={() => togglePanel('export')}
            />
            <ToolbarButton
              icon={<Clock className="w-4 h-4" />}
              label="History"
              active={activePanel === 'history'}
              onClick={() => togglePanel('history')}
            />
            <ToolbarButton
              icon={<MessageSquare className="w-4 h-4" />}
              label="Collaborate"
              active={activePanel === 'collaboration'}
              onClick={() => togglePanel('collaboration')}
            />
          </div>
        </div>

        {/* Slide canvas */}
        <div className="flex-1 overflow-auto flex items-center justify-center p-8">
          {currentSlide ? (
            <div className="w-full max-w-4xl">
              <div className="aspect-video bg-white rounded-xl shadow-lg overflow-hidden relative">
                {isCurrentSlideLocked && (
                  <div className="absolute top-3 right-3 z-10 flex items-center gap-1.5 bg-amber-100 text-amber-700 text-xs font-medium px-2 py-1 rounded-full">
                    <Lock className="w-3 h-3" />
                    Locked
                  </div>
                )}
                <SlideRenderer slide={currentSlide} theme={theme} className="w-full h-full" />
              </div>

              {/* Slide navigation */}
              <div className="flex items-center justify-center gap-4 mt-4">
                <button
                  onClick={() => setCurrentSlideIndex((i) => Math.max(0, i - 1))}
                  disabled={currentSlideIndex === 0}
                  className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  ← Previous
                </button>
                <span className="text-sm text-gray-500">
                  {currentSlideIndex + 1} / {slides.length}
                </span>
                <button
                  onClick={() => setCurrentSlideIndex((i) => Math.min(slides.length - 1, i + 1))}
                  disabled={currentSlideIndex >= slides.length - 1}
                  className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  Next →
                </button>
              </div>
            </div>
          ) : (
            <p className="text-gray-400 text-sm">No slides available.</p>
          )}
        </div>
      </div>

      {/* ── Side panels ── */}
      {activePanel === 'edit' && currentSlide && !isCurrentSlideLocked && (
        <SlideEditPanel
          presentationId={presentationId}
          slide={currentSlide}
          onClose={() => setActivePanel(null)}
          onSaved={handleSlideSaved}
        />
      )}

      {activePanel === 'export' && (
        <ExportPreviewPanel
          presentationId={presentationId}
          onClose={() => setActivePanel(null)}
        />
      )}

      {activePanel === 'history' && (
        <VersionHistoryPanel
          presentationId={presentationId}
          currentVersion={currentVersion}
          onClose={() => setActivePanel(null)}
          onRollback={handleRollback}
        />
      )}

      {activePanel === 'collaboration' && (
        <CollaborationPanel
          presentationId={presentationId}
          slides={slides.map((s) => ({ id: s.id, title: s.title }))}
          onClose={() => setActivePanel(null)}
        />
      )}
    </div>
  )
}

// ── Toolbar button helper ──────────────────────────────────────────────────

interface ToolbarButtonProps {
  icon: React.ReactNode
  label: string
  active?: boolean
  disabled?: boolean
  onClick: () => void
}

function ToolbarButton({ icon, label, active, disabled, onClick }: ToolbarButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={disabled ? `${label} (slide is locked)` : label}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
        active
          ? 'bg-blue-100 text-blue-700'
          : 'text-gray-600 hover:bg-gray-100 hover:text-gray-800'
      } disabled:opacity-40 disabled:cursor-not-allowed`}
    >
      {icon}
      {label}
    </button>
  )
}
