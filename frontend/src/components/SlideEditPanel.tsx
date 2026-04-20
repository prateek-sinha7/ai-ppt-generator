import { useState, useEffect } from 'react'
import { X, Save, Plus, Trash2, Loader2 } from 'lucide-react'
import { SlideData } from '../types'
import { updateSlide } from '../services/api'

interface SlideEditPanelProps {
  presentationId: string
  slide: SlideData
  onClose: () => void
  onSaved: (updated: SlideData) => void
}

export default function SlideEditPanel({
  presentationId,
  slide,
  onClose,
  onSaved,
}: SlideEditPanelProps) {
  const [title, setTitle] = useState(slide.title)
  const [subtitle, setSubtitle] = useState(slide.subtitle ?? '')
  const [bullets, setBullets] = useState<string[]>(slide.bullets ?? [])
  const [highlightText, setHighlightText] = useState(slide.highlight_text ?? '')
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [titleError, setTitleError] = useState<string | null>(null)

  // Reset when slide changes
  useEffect(() => {
    setTitle(slide.title)
    setSubtitle(slide.subtitle ?? '')
    setBullets(slide.bullets ?? [])
    setHighlightText(slide.highlight_text ?? '')
    setError(null)
    setTitleError(null)
  }, [slide.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const validateTitle = (value: string) => {
    const wordCount = value.trim().split(/\s+/).filter(Boolean).length
    if (wordCount > 8) {
      setTitleError('Title must be 8 words or fewer')
    } else {
      setTitleError(null)
    }
  }

  const handleTitleChange = (value: string) => {
    setTitle(value)
    validateTitle(value)
  }

  const handleBulletChange = (index: number, value: string) => {
    const updated = [...bullets]
    updated[index] = value
    setBullets(updated)
  }

  const handleAddBullet = () => {
    if (bullets.length < 4) {
      setBullets([...bullets, ''])
    }
  }

  const handleRemoveBullet = (index: number) => {
    setBullets(bullets.filter((_, i) => i !== index))
  }

  const handleSave = async () => {
    if (titleError) return

    const patch: Partial<SlideData> = { title }
    if (slide.type === 'title') patch.subtitle = subtitle
    if (slide.bullets !== undefined) patch.bullets = bullets.filter((b) => b.trim())
    if (highlightText) patch.highlight_text = highlightText

    setIsSaving(true)
    setError(null)
    try {
      const response = await updateSlide(presentationId, slide.id, patch)
      onSaved({ ...slide, ...patch, ...response.data })
    } catch {
      setError('Failed to save changes. Please try again.')
    } finally {
      setIsSaving(false)
    }
  }

  const hasChanges =
    title !== slide.title ||
    subtitle !== (slide.subtitle ?? '') ||
    JSON.stringify(bullets) !== JSON.stringify(slide.bullets ?? []) ||
    highlightText !== (slide.highlight_text ?? '')

  return (
    <div className="fixed inset-y-0 right-0 w-96 bg-white shadow-2xl border-l border-gray-200 flex flex-col z-50">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
        <div>
          <h2 className="text-base font-semibold text-gray-900">Edit Slide</h2>
          <p className="text-xs text-gray-500 capitalize mt-0.5">{slide.type} slide</p>
        </div>
        <button
          onClick={onClose}
          className="p-2 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors"
          aria-label="Close edit panel"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Form */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-5">
        {/* Title */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Title <span className="text-gray-400 font-normal">(max 8 words)</span>
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => handleTitleChange(e.target.value)}
            className={`w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
              titleError ? 'border-red-400' : 'border-gray-300'
            }`}
          />
          {titleError && <p className="text-xs text-red-500 mt-1">{titleError}</p>}
        </div>

        {/* Subtitle (title slides only) */}
        {slide.type === 'title' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Subtitle</label>
            <input
              type="text"
              value={subtitle}
              onChange={(e) => setSubtitle(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        )}

        {/* Bullets (content slides) */}
        {slide.bullets !== undefined && (
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-sm font-medium text-gray-700">
                Bullets <span className="text-gray-400 font-normal">(max 4, 8 words each)</span>
              </label>
              {bullets.length < 4 && (
                <button
                  onClick={handleAddBullet}
                  className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700"
                >
                  <Plus className="w-3 h-3" /> Add
                </button>
              )}
            </div>
            <div className="space-y-2">
              {bullets.map((bullet, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input
                    type="text"
                    value={bullet}
                    onChange={(e) => handleBulletChange(i, e.target.value)}
                    placeholder={`Bullet ${i + 1}`}
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <button
                    onClick={() => handleRemoveBullet(i)}
                    className="p-1.5 text-gray-400 hover:text-red-500 transition-colors"
                    aria-label="Remove bullet"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
              {bullets.length === 0 && (
                <p className="text-xs text-gray-400 italic">No bullets. Click Add to create one.</p>
              )}
            </div>
          </div>
        )}

        {/* Highlight text */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Highlight Text <span className="text-gray-400 font-normal">(optional)</span>
          </label>
          <input
            type="text"
            value={highlightText}
            onChange={(e) => setHighlightText(e.target.value)}
            placeholder="Key metric or emphasis phrase"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Read-only info */}
        <div className="bg-gray-50 rounded-lg p-3 space-y-1">
          <p className="text-xs text-gray-500">
            <span className="font-medium">Layout:</span> {slide.visual_hint}
          </p>
          <p className="text-xs text-gray-500">
            <span className="font-medium">Type:</span> {slide.type}
          </p>
        </div>
      </div>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-gray-200 space-y-2">
        {error && <p className="text-xs text-red-600">{error}</p>}
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={!hasChanges || isSaving || !!titleError}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isSaving ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Saving…
              </>
            ) : (
              <>
                <Save className="w-4 h-4" /> Save
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
