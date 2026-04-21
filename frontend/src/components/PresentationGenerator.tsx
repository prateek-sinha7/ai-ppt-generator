import { useState } from 'react'
import { apiClient } from '../services/api'

interface PresentationGeneratorProps {
  onGenerationStart: (presentationId: string, jobId: string) => void
}

const MAX_TOPIC_LENGTH = 5000

export default function PresentationGenerator({ onGenerationStart }: PresentationGeneratorProps) {
  const [topic, setTopic] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!topic.trim()) {
      setError('Please enter a presentation topic or paste your content')
      return
    }

    if (topic.length > MAX_TOPIC_LENGTH) {
      setError(`Content must be ${MAX_TOPIC_LENGTH.toLocaleString()} characters or less`)
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      const response = await apiClient.post('/presentations', { topic: topic.trim() })
      const { presentation_id, job_id } = response.data
      onGenerationStart(presentation_id, job_id)
      setTopic('')
    } catch (err: any) {
      if (err.response?.status === 429) {
        setError('Rate limit exceeded. Please try again later.')
      } else if (err.response?.status === 401) {
        setError('Authentication required. Please log in.')
        setTimeout(() => { window.location.href = '/login' }, 2000)
      } else if (err.response?.data?.detail) {
        setError(err.response.data.detail)
      } else {
        setError(err.message || 'Failed to start presentation generation')
      }
      setIsSubmitting(false)
    }
  }

  const charCount = topic.length
  const isNearLimit = charCount > MAX_TOPIC_LENGTH * 0.9
  const isOverLimit = charCount > MAX_TOPIC_LENGTH

  return (
    <div className="w-full max-w-3xl mx-auto p-8">
      <div className="bg-white rounded-lg shadow-lg p-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          AI Presentation Generator
        </h1>
        <p className="text-gray-600 mb-8">
          Enter a topic or paste your content — the AI will structure it into a professional presentation
        </p>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label htmlFor="topic" className="block text-sm font-medium text-gray-700 mb-2">
              Topic or Content
            </label>
            <textarea
              id="topic"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder={`Enter a topic (e.g., "Healthcare market analysis Q4 2024") or paste your content directly — up to ${MAX_TOPIC_LENGTH.toLocaleString()} characters`}
              className={`w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-y ${
                isOverLimit ? 'border-red-400 bg-red-50' : 'border-gray-300'
              }`}
              rows={6}
              maxLength={MAX_TOPIC_LENGTH}
              disabled={isSubmitting}
            />
            <div className="flex justify-between items-center mt-2">
              <span className={`text-sm ${isOverLimit ? 'text-red-600 font-medium' : isNearLimit ? 'text-orange-500' : 'text-gray-500'}`}>
                {charCount.toLocaleString()} / {MAX_TOPIC_LENGTH.toLocaleString()} characters
              </span>
              {error && (
                <span className="text-sm text-red-600">{error}</span>
              )}
            </div>
          </div>

          <button
            type="submit"
            disabled={isSubmitting || !topic.trim() || isOverLimit}
            className="w-full bg-blue-600 text-white py-3 px-6 rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
          >
            {isSubmitting ? 'Starting Generation…' : 'Generate Presentation'}
          </button>
        </form>
      </div>
    </div>
  )
}
