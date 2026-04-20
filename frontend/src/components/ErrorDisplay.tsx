import { useEffect, useState } from 'react'
import { AlertCircle, Clock, Zap, Shield, RefreshCw, XCircle } from 'lucide-react'

export type ErrorType =
  | 'provider_failure'
  | 'quality_failure'
  | 'timeout'
  | 'rate_limit'
  | 'authentication'
  | 'unknown'

interface ErrorDisplayProps {
  errorType: ErrorType
  errorMessage: string
  /** Seconds until the rate limit resets (from X-RateLimit-Reset or SSE retry_after) */
  retryAfterSeconds?: number
  onRetry?: () => void
  onCancel?: () => void
}

const ERROR_CONFIGS: Record<
  ErrorType,
  {
    icon: React.ElementType
    title: string
    description: string
    color: 'yellow' | 'blue' | 'orange' | 'red'
    showRetry: boolean
  }
> = {
  provider_failure: {
    icon: Zap,
    title: 'AI Provider Issue',
    description: 'Switching to backup AI provider, please wait...',
    color: 'yellow',
    showRetry: true,
  },
  quality_failure: {
    icon: Shield,
    title: 'Quality Enhancement Failed',
    description:
      'The presentation could not meet quality standards after multiple attempts. The best available result has been saved.',
    color: 'blue',
    showRetry: true,
  },
  timeout: {
    icon: Clock,
    title: 'Generation Taking Longer Than Expected',
    description:
      'Generation is taking longer than expected. Would you like to try again with a simpler topic?',
    color: 'orange',
    showRetry: true,
  },
  rate_limit: {
    icon: AlertCircle,
    title: 'High Demand Detected',
    description: 'You have reached the request limit. Please wait before trying again.',
    color: 'red',
    showRetry: true,
  },
  authentication: {
    icon: Shield,
    title: 'Authentication Required',
    description: 'Please log in to continue.',
    color: 'red',
    showRetry: false,
  },
  unknown: {
    icon: XCircle,
    title: 'Something Went Wrong',
    description: 'An unexpected error occurred. Please try again.',
    color: 'red',
    showRetry: true,
  },
}

const COLOR_CLASSES = {
  yellow: {
    bg: 'bg-yellow-50',
    border: 'border-yellow-200',
    icon: 'text-yellow-600',
    title: 'text-yellow-900',
    text: 'text-yellow-800',
    button: 'bg-yellow-600 hover:bg-yellow-700',
    detail: 'bg-yellow-100 border-yellow-200',
  },
  blue: {
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    icon: 'text-blue-600',
    title: 'text-blue-900',
    text: 'text-blue-800',
    button: 'bg-blue-600 hover:bg-blue-700',
    detail: 'bg-blue-100 border-blue-200',
  },
  orange: {
    bg: 'bg-orange-50',
    border: 'border-orange-200',
    icon: 'text-orange-600',
    title: 'text-orange-900',
    text: 'text-orange-800',
    button: 'bg-orange-600 hover:bg-orange-700',
    detail: 'bg-orange-100 border-orange-200',
  },
  red: {
    bg: 'bg-red-50',
    border: 'border-red-200',
    icon: 'text-red-600',
    title: 'text-red-900',
    text: 'text-red-800',
    button: 'bg-red-600 hover:bg-red-700',
    detail: 'bg-red-100 border-red-200',
  },
}

/** Countdown timer shown for rate-limit errors when retryAfterSeconds is provided */
function RateLimitCountdown({
  initialSeconds,
  onExpired,
}: {
  initialSeconds: number
  onExpired: () => void
}) {
  const [remaining, setRemaining] = useState(initialSeconds)

  useEffect(() => {
    if (remaining <= 0) {
      onExpired()
      return
    }
    const timer = setTimeout(() => setRemaining((s) => s - 1), 1000)
    return () => clearTimeout(timer)
  }, [remaining, onExpired])

  const minutes = Math.floor(remaining / 60)
  const seconds = remaining % 60
  const formatted = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`

  return (
    <p className="text-sm font-medium text-red-700 mt-3">
      Estimated wait time:{' '}
      <span className="font-mono font-bold">{formatted}</span>
    </p>
  )
}

export default function ErrorDisplay({
  errorType,
  errorMessage,
  retryAfterSeconds,
  onRetry,
  onCancel,
}: ErrorDisplayProps) {
  const [retryEnabled, setRetryEnabled] = useState(
    errorType !== 'rate_limit' || !retryAfterSeconds
  )

  const config = ERROR_CONFIGS[errorType] ?? ERROR_CONFIGS.unknown
  const Icon = config.icon
  const colors = COLOR_CLASSES[config.color]

  const handleCountdownExpired = () => setRetryEnabled(true)

  return (
    <div className="w-full max-w-3xl mx-auto p-8">
      <div className={`${colors.bg} border ${colors.border} rounded-lg shadow-lg p-8`}>
        <div className="flex items-start gap-4">
          <div className={`flex-shrink-0 ${colors.icon}`}>
            <Icon className="w-8 h-8" />
          </div>

          <div className="flex-1">
            <h2 className={`text-xl font-semibold ${colors.title} mb-2`}>
              {config.title}
            </h2>

            <p className={`${colors.text} mb-2`}>{config.description}</p>

            {/* Rate-limit countdown */}
            {errorType === 'rate_limit' && retryAfterSeconds && retryAfterSeconds > 0 && (
              <RateLimitCountdown
                initialSeconds={retryAfterSeconds}
                onExpired={handleCountdownExpired}
              />
            )}

            {/* Raw error detail (collapsed, monospace) */}
            {errorMessage && (
              <div
                className={`mt-3 p-3 rounded border ${colors.detail}`}
              >
                <p className="text-xs font-mono text-gray-700 break-all">{errorMessage}</p>
              </div>
            )}

            {/* Action buttons */}
            <div className="flex gap-3 mt-6">
              {config.showRetry && onRetry && (
                <button
                  onClick={onRetry}
                  disabled={!retryEnabled}
                  className={`flex items-center gap-2 px-4 py-2 ${colors.button} text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  <RefreshCw className="w-4 h-4" />
                  {retryEnabled ? 'Try Again' : 'Please wait…'}
                </button>
              )}

              {onCancel && (
                <button
                  onClick={onCancel}
                  className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg font-medium hover:bg-gray-300 transition-colors"
                >
                  Cancel
                </button>
              )}
            </div>

            {/* Contextual tips */}
            {errorType === 'rate_limit' && (
              <p className="text-xs text-gray-600 mt-4">
                Tip: Premium users have higher rate limits. Consider upgrading for faster access.
              </p>
            )}
            {errorType === 'timeout' && (
              <p className="text-xs text-gray-600 mt-4">
                Tip: Complex topics may take longer to process. Try breaking your topic into
                smaller, more focused sections.
              </p>
            )}
            {errorType === 'provider_failure' && (
              <p className="text-xs text-gray-600 mt-4">
                Tip: The system automatically retries with backup providers. Retrying now should
                succeed.
              </p>
            )}
            {errorType === 'quality_failure' && (
              <p className="text-xs text-gray-600 mt-4">
                Tip: Try rephrasing your topic with more specific industry context for better
                results.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
