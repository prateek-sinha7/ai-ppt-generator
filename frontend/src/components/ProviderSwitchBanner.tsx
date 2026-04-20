import { Zap } from 'lucide-react'

interface ProviderSwitchBannerProps {
  fromProvider: string
  toProvider: string
}

/**
 * Non-fatal inline banner shown during generation when the pipeline
 * automatically switches to a fallback LLM provider.
 */
export default function ProviderSwitchBanner({
  fromProvider,
  toProvider,
}: ProviderSwitchBannerProps) {
  return (
    <div className="w-full max-w-3xl mx-auto px-8 mt-4">
      <div className="flex items-center gap-3 bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3">
        <Zap className="w-4 h-4 text-yellow-600 flex-shrink-0" />
        <p className="text-sm text-yellow-800">
          Switching to backup AI provider
          {fromProvider && toProvider ? (
            <>
              {' '}
              (<span className="font-medium">{fromProvider}</span> →{' '}
              <span className="font-medium">{toProvider}</span>)
            </>
          ) : null}
          , please wait…
        </p>
      </div>
    </div>
  )
}
