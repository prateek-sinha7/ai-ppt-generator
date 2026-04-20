import { useState, useCallback } from 'react'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
  arrayMove,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical, Lock } from 'lucide-react'
import { SlideData, Theme } from '../types'
import { reorderSlides } from '../services/api'

interface SortableSlideItemProps {
  slide: SlideData
  index: number
  isLocked: boolean
  isActive: boolean
}

function SortableSlideItem({ slide, index, isLocked, isActive }: SortableSlideItemProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: slide.id,
    disabled: isLocked,
  })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-3 p-3 bg-white rounded-lg border transition-shadow ${
        isActive ? 'shadow-lg border-blue-400' : 'border-gray-200 hover:border-gray-300'
      } ${isLocked ? 'opacity-60' : ''}`}
    >
      <button
        {...attributes}
        {...listeners}
        className={`text-gray-400 ${isLocked ? 'cursor-not-allowed' : 'cursor-grab active:cursor-grabbing hover:text-gray-600'}`}
        aria-label={isLocked ? 'Slide is locked' : 'Drag to reorder'}
        disabled={isLocked}
      >
        {isLocked ? <Lock className="w-4 h-4" /> : <GripVertical className="w-4 h-4" />}
      </button>

      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center text-xs font-semibold text-gray-600">
        {index + 1}
      </div>

      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-800 truncate">{slide.title}</p>
        <p className="text-xs text-gray-500 capitalize">{slide.type}</p>
      </div>

      <div className="flex-shrink-0 w-16 h-10 bg-gray-50 rounded border border-gray-200 flex items-center justify-center text-xs text-gray-400">
        {slide.type}
      </div>
    </div>
  )
}

interface DraggableSlideListProps {
  presentationId: string
  slides: SlideData[]
  lockedSlideIds: Set<string>
  theme: Theme
  onReorder: (slides: SlideData[]) => void
}

export default function DraggableSlideList({
  presentationId,
  slides,
  lockedSlideIds,
  onReorder,
}: DraggableSlideListProps) {
  const [activeId, setActiveId] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const handleDragStart = useCallback((event: DragStartEvent) => {
    setActiveId(event.active.id as string)
    setSaveError(null)
  }, [])

  const handleDragEnd = useCallback(
    async (event: DragEndEvent) => {
      const { active, over } = event
      setActiveId(null)

      if (!over || active.id === over.id) return

      const oldIndex = slides.findIndex((s) => s.id === active.id)
      const newIndex = slides.findIndex((s) => s.id === over.id)

      if (oldIndex === -1 || newIndex === -1) return

      const reordered = arrayMove(slides, oldIndex, newIndex)
      onReorder(reordered)

      setIsSaving(true)
      try {
        await reorderSlides(
          presentationId,
          reordered.map((s) => s.id),
        )
      } catch {
        setSaveError('Failed to save order. Please try again.')
        onReorder(slides) // revert
      } finally {
        setIsSaving(false)
      }
    },
    [slides, presentationId, onReorder],
  )

  const activeSlide = activeId ? slides.find((s) => s.id === activeId) : null

  return (
    <div className="space-y-2">
      {isSaving && (
        <p className="text-xs text-blue-600 text-center py-1">Saving order…</p>
      )}
      {saveError && (
        <p className="text-xs text-red-600 text-center py-1">{saveError}</p>
      )}

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <SortableContext items={slides.map((s) => s.id)} strategy={verticalListSortingStrategy}>
          <div className="space-y-2">
            {slides.map((slide, index) => (
              <SortableSlideItem
                key={slide.id}
                slide={slide}
                index={index}
                isLocked={lockedSlideIds.has(slide.id)}
                isActive={slide.id === activeId}
              />
            ))}
          </div>
        </SortableContext>

        <DragOverlay>
          {activeSlide && (
            <div className="flex items-center gap-3 p-3 bg-white rounded-lg border border-blue-400 shadow-xl opacity-90">
              <GripVertical className="w-4 h-4 text-gray-400" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">{activeSlide.title}</p>
                <p className="text-xs text-gray-500 capitalize">{activeSlide.type}</p>
              </div>
            </div>
          )}
        </DragOverlay>
      </DndContext>
    </div>
  )
}
