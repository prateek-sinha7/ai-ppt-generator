import { useState, useEffect, useCallback } from 'react'
import { X, Download, Loader2, FileText, AlertCircle, RefreshCw } from 'lucide-react'
import { getPptxExportStatus } from '../services/api'

type ExportStatus = 'idle' | 'triggering' | 'processing' | 'ready' | 'error'

interface ExportPreviewPanelProps {
  presentationId: string
  onClose: () => void
}

export default function ExportPreviewPanel({ presentationId, onClose }: ExportPreviewPanelProps) {
  const [status, setStatus] = useState<ExportStatus>('idle')
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [pollCount, setPollCount] = useState(0)

  const pollExportStatus = useCallback(async () => {
    try {
      const response = await getPptxExportStatus(presentationId)
      const data = response.data

      if (data.status === 'completed') {
        setDownloadUrl(data.download_url ?? null)
        setPreviewUrl(data.preview_url ?? null)
        setStatus('ready')
      } else if (data.status === 'failed') {
        setErrorMessage(data.error ?? 'Export failed. Please try again.')
        setStatus('error')
      } else {
        // Still processing — keep polling
        setPollCount((c) => c + 1)
      }
    } catch {
      setErrorMessage('Could not check export status.')
      setStatus('error')
    }
  }, [presentationId])

  // Poll every 3 seconds while processing
  useEffect(() => {
    if (status !== 'processing') return
    const timer = setTimeout(pollExportStatus, 3000)
    return () => clearTimeout(timer)
  }, [status, pollCount, pollExportStatus])

  const handleStartExport = async () => {
    setStatus('triggering')
    setErrorMessage(null)
    setDownloadUrl(null)
    setPreviewUrl(null)
    try {
      // Direct download URL — no polling needed
      setDownloadUrl(`/api/v1/presentations/${presentationId}/export/pptx/download`)
      setStatus('ready')
    } catch {
      setErrorMessage('Failed to prepare export. Please try again.')
      setStatus('error')
    }
  }

  const handleRetry = () => {
    setStatus('idle')
    setErrorMessage(null)
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div className="flex items-center gap-3">
            <FileText className="w-5 h-5 text-blue-600" />
            <h2 className="text-base font-semibold text-gray-900">Export Presentation</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors"
            aria-label="Close export panel"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6">
          {status === 'idle' && (
            <div className="text-center py-12">
              <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-800 mb-2">Export to PowerPoint</h3>
              <p className="text-sm text-gray-500 mb-6 max-w-sm mx-auto">
                Generate a fully formatted .pptx file with your presentation themes, charts, and tables.
              </p>
              <button
                onClick={handleStartExport}
                className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
              >
                <Download className="w-4 h-4" />
                Generate Export
              </button>
            </div>
          )}

          {(status === 'triggering' || status === 'processing') && (
            <div className="text-center py-12">
              <Loader2 className="w-12 h-12 text-blue-500 mx-auto mb-4 animate-spin" />
              <h3 className="text-lg font-medium text-gray-800 mb-2">
                {status === 'triggering' ? 'Starting export…' : 'Generating your file…'}
              </h3>
              <p className="text-sm text-gray-500">
                This usually takes 10–30 seconds. Please wait.
              </p>
            </div>
          )}

          {status === 'error' && (
            <div className="text-center py-12">
              <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-800 mb-2">Export Failed</h3>
              <p className="text-sm text-red-600 mb-6">{errorMessage}</p>
              <button
                onClick={handleRetry}
                className="inline-flex items-center gap-2 px-5 py-2.5 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                Try Again
              </button>
            </div>
          )}

          {status === 'ready' && (
            <div className="space-y-4">
              {/* PDF Preview */}
              {previewUrl ? (
                <div className="border border-gray-200 rounded-lg overflow-hidden">
                  <div className="bg-gray-50 px-4 py-2 border-b border-gray-200">
                    <p className="text-xs font-medium text-gray-600">Preview</p>
                  </div>
                  <iframe
                    src={previewUrl}
                    title="Presentation preview"
                    className="w-full h-96"
                    style={{ border: 'none' }}
                  />
                </div>
              ) : (
                <div className="border border-gray-200 rounded-lg p-8 text-center bg-gray-50">
                  <FileText className="w-10 h-10 text-gray-300 mx-auto mb-2" />
                  <p className="text-sm text-gray-500">Preview not available</p>
                </div>
              )}

              {/* Download button */}
              {downloadUrl && (
                <button
                  onClick={async () => {
                    try {
                      const { apiClient } = await import('../services/api')
                      const response = await apiClient.post(
                        `/presentations/${presentationId}/export/pptx`,
                        {},
                        { responseType: 'blob' }
                      )
                      const disposition = response.headers['content-disposition'] || ''
                      const match = disposition.match(/filename="?([^";\n]+)"?/)
                      const filename = match ? match[1] : 'presentation.pptx'
                      const url = URL.createObjectURL(new Blob([response.data], {
                        type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                      }))
                      const a = document.createElement('a')
                      a.href = url
                      a.download = filename
                      document.body.appendChild(a)
                      a.click()
                      document.body.removeChild(a)
                      URL.revokeObjectURL(url)
                    } catch {
                      setErrorMessage('Download failed. Please try again.')
                      setStatus('error')
                    }
                  }}
                  className="flex items-center justify-center gap-2 w-full px-5 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
                >
                  <Download className="w-4 h-4" />
                  Download .pptx
                </button>
              )}

              <p className="text-xs text-gray-400 text-center">
                Download link expires in 1 hour.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
