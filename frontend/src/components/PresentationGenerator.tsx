import { useState } from 'react'
import { apiClient } from '../services/api'

interface PresentationGeneratorProps {
  onGenerationStart: (presentationId: string, jobId: string) => void
}

export default function PresentationGenerator({ onGenerationStart }: PresentationGeneratorProps) {
  const [topic, setTopic] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!topic.trim()) {
      setError('Please enter a presentation topic')
      return
    }

    if (topic.length > 500) {
      setError('Topic must be 500 characters or less')
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      console.log('Submitting presentation request:', { topic: topic.trim() })
      const response = await apiClient.post('/presentations', { topic: topic.trim() })
      console.log('Presentation response:', response.data)
      
      const { presentation_id, job_id } = response.data
      
      onGenerationStart(presentation_id, job_id)
      setTopic('')
    } catch (err: any) {
      console.error('Presentation generation error:', err)
      console.error('Error response:', err.response)
      
      if (err.response?.status === 429) {
        setError('Rate limit exceeded. Please try again later.')
      } else if (err.response?.status === 401) {
        setError('Authentication required. Please log in.')
        // Redirect to login after a short delay
        setTimeout(() => {
          window.location.href = '/login'
        }, 2000)
      } else if (err.response?.data?.detail) {
        setError(err.response.data.detail)
      } else if (err.message) {
        setError(err.message)
      } else {
        setError('Failed to start presentation generation')
      }
      setIsSubmitting(false)
    }
  }

  return (
    <div className="w-full max-w-3xl mx-auto p-8">
      <div className="bg-white rounded-lg shadow-lg p-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          AI Presentation Generator
        </h1>
        <p className="text-gray-600 mb-8">
          Enter your presentation topic and let AI create a professional presentation for you
        </p>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label htmlFor="topic" className="block text-sm font-medium text-gray-700 mb-2">
              Presentation Topic
            </label>
            <textarea
              id="topic"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g., Healthcare market analysis for Q4 2024"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              rows={4}
              maxLength={500}
              disabled={isSubmitting}
            />
            <div className="flex justify-between items-center mt-2">
              <span className="text-sm text-gray-500">
                {topic.length}/500 characters
              </span>
              {error && (
                <span className="text-sm text-red-600">
                  {error}
                </span>
              )}
            </div>
          </div>

          <button
            type="submit"
            disabled={isSubmitting || !topic.trim()}
            className="w-full bg-blue-600 text-white py-3 px-6 rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
          >
            {isSubmitting ? 'Starting Generation...' : 'Generate Presentation'}
          </button>
        </form>
      </div>
    </div>
  )
}
