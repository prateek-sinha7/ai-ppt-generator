import { useState } from 'react'
import { Download, Loader2, CheckCircle, AlertCircle } from 'lucide-react'
import { apiClient } from '../services/api'

interface DownloadButtonProps {
  presentationId: string
  className?: string
}

type DownloadState = 'idle' | 'queuing' | 'polling' | 'done' | 'error'

export default function DownloadButton({ presentationId, className = '' }: DownloadButtonProps) {
  const [state, setState] = useState<DownloadState>('idle')
  const [errorMsg, setErrorMsg] = useState('')

  const handleDownload = async () => {
    if (state !== 'idle' && state !== 'error') return
    setState('queuing')
    setErrorMsg('')

    try {
      // 1. Enqueue export job
      const enqueueRes = await apiClient.post(`/presentations/${presentationId}/export`)
      const jobId: string = enqueueRes.data.job_id
      setState('polling')

      // 2. Poll until done (max 60s, every 2s)
      const maxAttempts = 30
      for (let attempt = 0; attempt < maxAttempts; attempt++) {
        await new Promise((r) => setTimeout(r, 2000))

        const statusRes = await apiClient.get(
          `/presentations/${presentationId}/export/status?job_id=${jobId}`
        )
        const { status, download_url } = statusRes.data

        if (status === 'completed' && download_url) {
          setState('done')
          // Trigger browser download
          const a = document.createElement('a')
          a.href = download_url
          a.download = `presentation-${presentationId.slice(0, 8)}.pptx`
          document.body.appendChild(a)
          a.click()
          document.body.removeChild(a)
          // Reset after 3s
          setTimeout(() => setState('idle'), 3000)
          return
        }

        if (status === 'failed') {
          throw new Error(statusRes.data.message || 'Export failed')
        }
      }

      throw new Error('Export timed out. Please try again.')
    } catch (err: any) {
      setState('error')
      setErrorMsg(err?.response?.data?.detail || err?.message || 'Export failed')
      setTimeout(() => setState('idle'), 4000)
    }
  }

  const isLoading = state === 'queuing' || state === 'polling'

  return (
    <div className={`flex flex-col items-center gap-1 ${className}`}>
      <button
        onClick={handleDownload}
        disabled={isLoading}
        className={`flex items-center gap-2 px-5 py-2.5 rounded-lg font-semibold text-sm transition-all ${
          state === 'done'
            ? 'bg-green-600 text-white'
            : state === 'error'
            ? 'bg-red-100 text-red-700 border border-red-300'
            : isLoading
            ? 'bg-blue-100 text-blue-600 cursor-not-allowed'
            : 'bg-blue-600 text-white hover:bg-blue-700 shadow-sm hover:shadow-md'
        }`}
      >
        {state === 'done' ? (
          <>
            <CheckCircle className="w-4 h-4" />
            Downloaded!
          </>
        ) : state === 'error' ? (
          <>
            <AlertCircle className="w-4 h-4" />
            Retry Download
          </>
        ) : isLoading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            {state === 'queuing' ? 'Preparing...' : 'Generating PPTX...'}
          </>
        ) : (
          <>
            <Download className="w-4 h-4" />
            Download PPTX
          </>
        )}
      </button>

      {state === 'polling' && (
        <p className="text-xs text-gray-500 animate-pulse">
          Building your presentation file…
        </p>
      )}
      {state === 'error' && errorMsg && (
        <p className="text-xs text-red-500 max-w-xs text-center">{errorMsg}</p>
      )}
    </div>
  )
}
