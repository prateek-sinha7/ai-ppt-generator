import { useState } from 'react'
import { Lock, Unlock, Loader2 } from 'lucide-react'
import { lockSlide, unlockSlide } from '../services/api'

interface SlideLockIndicatorProps {
  presentationId: string
  slideId: string
  isLocked: boolean
  lockedBy?: string
  onLockChange: (slideId: string, locked: boolean) => void
}

export default function SlideLockIndicator({
  presentationId,
  slideId,
  isLocked,
  lockedBy,
  onLockChange,
}: SlideLockIndicatorProps) {
  const [isLoading, setIsLoading] = useState(false)

  const handleToggle = async () => {
    setIsLoading(true)
    try {
      if (isLocked) {
        await unlockSlide(presentationId, slideId)
        onLockChange(slideId, false)
      } else {
        await lockSlide(presentationId, slideId)
        onLockChange(slideId, true)
      }
    } catch {
      // silently fail — lock state unchanged
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <button
      onClick={handleToggle}
      disabled={isLoading}
      title={isLocked ? `Locked${lockedBy ? ` by ${lockedBy}` : ''}. Click to unlock.` : 'Click to lock this slide'}
      className={`inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium transition-colors ${
        isLocked
          ? 'bg-amber-100 text-amber-700 hover:bg-amber-200'
          : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
      } disabled:opacity-50 disabled:cursor-not-allowed`}
    >
      {isLoading ? (
        <Loader2 className="w-3 h-3 animate-spin" />
      ) : isLocked ? (
        <Lock className="w-3 h-3" />
      ) : (
        <Unlock className="w-3 h-3" />
      )}
      {isLocked ? (lockedBy ? `Locked by ${lockedBy}` : 'Locked') : 'Lock'}
    </button>
  )
}
