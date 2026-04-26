import { useState, useEffect } from 'react'
import { CheckCircle, Sparkles, RefreshCw } from 'lucide-react'
import { useSSEStream } from '../hooks/useSSEStream'
import { Theme } from '../types'
import PresentationGenerator from './PresentationGenerator'
import ProgressIndicator from './ProgressIndicator'
import PptxPreviewPanel from './PptxPreviewPanel'
import ErrorDisplay, { ErrorType } from './ErrorDisplay'
import ProviderSwitchBanner from './ProviderSwitchBanner'
import Header from './Header'
import DownloadButton from './DownloadButton'
import { apiClient } from '../services/api'

type WorkflowState = 'input' | 'generating' | 'completed' | 'error'

interface ProviderSwitch {
  fromProvider: string
  toProvider: string
}

/** Classify an SSE error event payload into a typed ErrorType */
function classifyError(errorData: any): ErrorType {
  const msg: string = (errorData?.error ?? errorData?.message ?? '').toLowerCase()
  const code: string = (errorData?.error_code ?? '').toLowerCase()

  if (code === 'rate_limit_exceeded' || msg.includes('rate limit') || msg.includes('too many requests')) {
    return 'rate_limit'
  }
  if (code === 'timeout' || msg.includes('timeout') || msg.includes('timed out')) {
    return 'timeout'
  }
  if (
    code === 'provider_failure' ||
    msg.includes('provider') ||
    msg.includes('all providers') ||
    msg.includes('llm')
  ) {
    return 'provider_failure'
  }
  if (code === 'quality_failure' || msg.includes('quality') || msg.includes('score')) {
    return 'quality_failure'
  }
  if (code === 'unauthorized' || msg.includes('auth') || msg.includes('unauthorized')) {
    return 'authentication'
  }
  return 'unknown'
}

export default function PresentationWorkflow() {
  const [state, setState] = useState<WorkflowState>('input')
  const [presentationId, setPresentationId] = useState<string | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [_theme, setTheme] = useState<Theme>('hexaware_corporate')
  const [detectedContext, setDetectedContext] = useState<any>(null)
  const [errorType, setErrorType] = useState<ErrorType>('unknown')
  const [errorMessage, setErrorMessage] = useState<string>('')
  const [retryAfterSeconds, setRetryAfterSeconds] = useState<number | undefined>(undefined)
  const [providerSwitch, setProviderSwitch] = useState<ProviderSwitch | null>(null)
  const [qualityScore, setQualityScore] = useState<number | null>(null)
  const [totalSlides, setTotalSlides] = useState<number>(0)
  const [_designSpec, setDesignSpec] = useState<any>(null)
  const [previewReady, setPreviewReady] = useState(false)
  const [previewStartTime, setPreviewStartTime] = useState<number | null>(null)
  const [previewElapsedMs, setPreviewElapsedMs] = useState<number | undefined>(undefined)

  const sseState = useSSEStream(presentationId, state === 'generating')

  // Check authentication on mount
  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      window.location.href = '/login'
    }
  }, [])

  // Handle generation start
  const handleGenerationStart = (newPresentationId: string, newJobId: string) => {
    setPresentationId(newPresentationId)
    setJobId(newJobId)
    setState('generating')
    setProviderSwitch(null)
    setQualityScore(null)
    setTotalSlides(0)
    setDetectedContext(null)
    setDesignSpec(null)
    setPreviewReady(false)
    setPreviewStartTime(null)
    setPreviewElapsedMs(undefined)
  }

  // Monitor SSE events
  useEffect(() => {
    if (sseState.events.length === 0) return

    const lastEvent = sseState.events[sseState.events.length - 1]

    // Provider switch banner
    if (lastEvent.type === 'agent_start' && lastEvent.data?.provider_switch) {
      setProviderSwitch({
        fromProvider: lastEvent.data.provider_switch.from ?? '',
        toProvider: lastEvent.data.provider_switch.to ?? '',
      })
      setTimeout(() => setProviderSwitch(null), 6000)
    }

    // Track quality score
    if (lastEvent.type === 'quality_score') {
      setQualityScore(lastEvent.data?.composite_score ?? null)
    }

    // Track slide count from slide_ready events — deduplicate by slide_number
    const slideReadyEvents = sseState.events.filter((e) => e.type === 'slide_ready')
    if (slideReadyEvents.length > 0) {
      // Count unique slide numbers (feedback loop re-emits same slides)
      const uniqueSlideNumbers = new Set(
        slideReadyEvents.map((e) => e.data?.slide?.slide_number ?? e.data?.slide_number ?? 0)
      )
      const latestEvent = slideReadyEvents[slideReadyEvents.length - 1]
      const declared = latestEvent.data?.total_slides
      setTotalSlides(declared && declared > 0 ? declared : uniqueSlideNumbers.size)
    }

    // Handle completion
    if (lastEvent.type === 'complete') {
      setState('completed')
      setProviderSwitch(null)
      setPreviewStartTime(Date.now())

      if (presentationId) {
        apiClient
          .get(`/presentations/${presentationId}`)
          .then((response) => {
            setTheme(response.data.theme || 'hexaware_corporate')
            setDesignSpec(response.data.design_spec || null)
            setDetectedContext({
              industry: response.data.detected_industry,
              audience: response.data.detected_audience,
              template_id: response.data.metadata?.template_id,
              template_name: response.data.metadata?.template_name,
              theme: response.data.theme,
              confidence_score: response.data.detection_confidence,
              design_palette: response.data.design_spec?.palette_name,
            })
          })
          .catch((err) => console.error('Failed to fetch presentation details:', err))
      }
    }

    // Handle terminal errors
    if (lastEvent.type === 'error') {
      const errorData = lastEvent.data
      setState('error')
      setProviderSwitch(null)
      const classified = classifyError(errorData)
      setErrorType(classified)
      setErrorMessage(errorData?.error ?? errorData?.message ?? 'An unexpected error occurred.')
      if (classified === 'rate_limit' && errorData?.retry_after) {
        setRetryAfterSeconds(Number(errorData.retry_after))
      }
    }

    // Extract detected context once industry classifier completes
    const industryClassifierComplete = sseState.events.find(
      (e) => e.type === 'agent_complete' && e.data.agent === 'industry_classifier'
    )
    if (industryClassifierComplete && presentationId && !detectedContext) {
      apiClient
        .get(`/presentations/${presentationId}/status`)
        .then((response) => {
          if (response.data.detected_context) {
            setDetectedContext(response.data.detected_context)
          }
        })
        .catch((err) => console.error('Failed to fetch detected context:', err))
    }
  }, [sseState.events, presentationId]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleRetry = () => {
    setState('input')
    setPresentationId(null)
    setJobId(null)
    setErrorType('unknown')
    setErrorMessage('')
    setRetryAfterSeconds(undefined)
    setDetectedContext(null)
    setProviderSwitch(null)
    setQualityScore(null)
    setTotalSlides(0)
    setPreviewReady(false)
    setPreviewStartTime(null)
    setPreviewElapsedMs(undefined)
  }

  const handleCancel = async () => {
    if (jobId) {
      try {
        await apiClient.delete(`/jobs/${jobId}`)
      } catch (err) {
        console.error('Failed to cancel job:', err)
      }
    }
    handleRetry()
  }

  return (
    <>
      <Header />
      <div className="min-h-screen bg-gray-50 py-8">

        {/* ── INPUT STATE ── */}
        {state === 'input' && (
          <PresentationGenerator onGenerationStart={handleGenerationStart} />
        )}

        {/* ── GENERATING STATE ── */}
        {state === 'generating' && (
          <div className="space-y-4">
            {providerSwitch && (
              <ProviderSwitchBanner
                fromProvider={providerSwitch.fromProvider}
                toProvider={providerSwitch.toProvider}
              />
            )}

            {/* Progress pipeline */}
            <ProgressIndicator
              events={sseState.events}
              isConnected={sseState.isConnected}
            />

            {/* Slide count indicator — no UI preview, just a count */}
            {totalSlides > 0 && (
              <div className="w-full max-w-3xl mx-auto px-8">
                <div className="bg-blue-50 border border-blue-100 rounded-xl px-5 py-3 flex items-center gap-3">
                  <Sparkles className="w-4 h-4 text-blue-500 flex-shrink-0 animate-pulse" />
                  <p className="text-sm text-blue-700 font-medium">
                    {totalSlides} slide{totalSlides !== 1 ? 's' : ''} generated — preview will appear once complete
                  </p>
                </div>
              </div>
            )}

            {/* Cancel button */}
            <div className="w-full max-w-3xl mx-auto px-8">
              <button
                onClick={handleCancel}
                className="w-full py-2 px-4 text-sm text-gray-500 border border-gray-300 rounded-lg hover:bg-gray-100 transition-colors"
              >
                Cancel Generation
              </button>
            </div>
          </div>
        )}

        {/* ── COMPLETED STATE ── */}
        {state === 'completed' && (
          <div className="space-y-6">
            {/* Completion banner */}
            <div className="w-full max-w-3xl mx-auto px-8">
              <div className="bg-green-50 border border-green-200 rounded-xl p-5 flex items-start gap-4">
                <div className="flex-shrink-0 w-10 h-10 bg-green-100 rounded-full flex items-center justify-center">
                  <CheckCircle className="w-6 h-6 text-green-600" />
                </div>
                <div className="flex-1">
                  <h3 className="text-base font-semibold text-green-800">
                    Presentation Generated Successfully!
                  </h3>
                  <div className="mt-1 flex flex-wrap gap-4 text-sm text-green-700">
                    {totalSlides > 0 && (
                      <span>📊 {totalSlides} slides created</span>
                    )}
                    {qualityScore !== null && (
                      <span>⭐ Quality score: {qualityScore.toFixed(1)} / 10</span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Completed pipeline summary — stays at 99% until preview is ready */}
            <ProgressIndicator
              events={sseState.events}
              isConnected={false}
              previewRendering={!previewReady}
              previewReady={previewReady}
              previewElapsedMs={previewElapsedMs}
            />

            {/* Slides — real PPTX images (pixel-perfect match with download) */}
            <PptxPreviewPanel
              presentationId={presentationId!}
              inline
              onReady={() => {
                setPreviewReady(true)
                if (previewStartTime) {
                  setPreviewElapsedMs(Date.now() - previewStartTime)
                }
              }}
            />

            {/* Actions */}
            <div className="w-full max-w-3xl mx-auto px-8 pb-8">
              <div className="grid grid-cols-2 gap-3">
                {/* Download PPTX */}
                <DownloadButton presentationId={presentationId!} />

                {/* Create Another */}
                <button
                  onClick={handleRetry}
                  className="h-14 rounded-xl font-semibold text-sm transition-all duration-200 flex items-center justify-center gap-2.5 border border-gray-200 bg-white text-gray-700 hover:bg-gray-50 hover:border-gray-300 hover:shadow-md active:bg-gray-100 shadow-sm"
                >
                  <RefreshCw className="w-4 h-4 text-gray-500" />
                  Create Another
                </button>
              </div>

              {/* Subtext row */}
              <p className="text-xs text-center text-gray-400 mt-2">
                Download link is available for 1 hour · PPTX format compatible with PowerPoint &amp; Keynote
              </p>
            </div>
          </div>
        )}

        {/* ── ERROR STATE ── */}
        {state === 'error' && (
          <div className="space-y-4">
            {/* Show pipeline progress even on error */}
            {sseState.events.length > 0 && (
              <ProgressIndicator
                events={sseState.events}
                isConnected={false}
              />
            )}
            <ErrorDisplay
              errorType={errorType}
              errorMessage={errorMessage}
              retryAfterSeconds={retryAfterSeconds}
              onRetry={handleRetry}
              onCancel={handleCancel}
            />
          </div>
        )}
      </div>
    </>
  )
}
