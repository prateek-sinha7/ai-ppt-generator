import { CheckCircle, Loader2, XCircle, Clock, Zap } from 'lucide-react'
import { SSEEvent } from '../hooks/useSSEStream'

interface ProgressIndicatorProps {
  events: SSEEvent[]
  isConnected: boolean
}

interface AgentStatus {
  name: string
  displayName: string
  description: string
  status: 'pending' | 'running' | 'completed' | 'error'
  startedAt?: number
  elapsedMs?: number
}

// Must match exactly what the backend sends as agent names
const AGENT_PIPELINE: { name: string; displayName: string; description: string }[] = [
  {
    name: 'industry_classifier',
    displayName: 'Industry Classification',
    description: 'Detecting industry, audience & template',
  },
  {
    name: 'storyboarding',
    displayName: 'Storyboarding',
    description: 'Building presentation structure & sections',
  },
  {
    name: 'research',
    displayName: 'Research & Analysis',
    description: 'Gathering insights, risks & opportunities',
  },
  {
    name: 'data_enrichment',
    displayName: 'Data Enrichment',
    description: 'Generating charts, tables & KPI metrics',
  },
  {
    name: 'prompt_engineering',
    displayName: 'Prompt Engineering',
    description: 'Optimising prompts for content generation',
  },
  {
    name: 'llm_provider',
    displayName: 'Content Generation',
    description: 'Generating slide content with AI',
  },
  {
    name: 'validation',
    displayName: 'Validation',
    description: 'Validating & correcting slide structure',
  },
  {
    name: 'quality_scoring',
    displayName: 'Quality Scoring',
    description: 'Scoring presentation quality & feedback',
  },
]

function formatElapsed(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

export default function ProgressIndicator({ events, isConnected }: ProgressIndicatorProps) {
  // Track start times locally using event timestamps
  const agentStartTimes: Record<string, number> = {}
  const agentElapsed: Record<string, number> = {}

  events.forEach((e) => {
    if (e.type === 'agent_start') {
      agentStartTimes[e.data.agent] = Date.now()
    }
    if (e.type === 'agent_complete') {
      agentElapsed[e.data.agent] = e.data.elapsed_ms
    }
  })

  const agentStatuses: AgentStatus[] = AGENT_PIPELINE.map((agent) => {
    const startEvent = events.find(
      (e) => e.type === 'agent_start' && e.data.agent === agent.name
    )
    const completeEvent = events.find(
      (e) => e.type === 'agent_complete' && e.data.agent === agent.name
    )
    const errorEvent = events.find(
      (e) => e.type === 'error' && e.data.failed_agent === agent.name
    )

    if (errorEvent) return { ...agent, status: 'error' as const }
    if (completeEvent) {
      return {
        ...agent,
        status: 'completed' as const,
        elapsedMs: completeEvent.data.elapsed_ms,
      }
    }
    if (startEvent) return { ...agent, status: 'running' as const }
    return { ...agent, status: 'pending' as const }
  })

  const completedCount = agentStatuses.filter((a) => a.status === 'completed').length
  const hasError = agentStatuses.some((a) => a.status === 'error')
  const currentAgent = agentStatuses.find((a) => a.status === 'running')
  const progressPercent = Math.round((completedCount / AGENT_PIPELINE.length) * 100)

  // Check for quality score
  const qualityEvent = events.find((e) => e.type === 'quality_score')
  const qualityScore = qualityEvent?.data?.composite_score

  return (
    <div className="w-full max-w-3xl mx-auto p-8">
      <div className="bg-white rounded-xl shadow-lg overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-blue-700 px-8 py-6 text-white">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              {hasError ? (
                <XCircle className="w-6 h-6 text-red-300" />
              ) : completedCount === AGENT_PIPELINE.length ? (
                <CheckCircle className="w-6 h-6 text-green-300" />
              ) : (
                <Loader2 className="w-6 h-6 animate-spin text-blue-200" />
              )}
              <h2 className="text-xl font-semibold">
                {hasError
                  ? 'Generation Failed'
                  : completedCount === AGENT_PIPELINE.length
                  ? 'Presentation Ready!'
                  : 'Generating Presentation'}
              </h2>
            </div>
            <div className="text-right">
              <span className="text-2xl font-bold">{progressPercent}%</span>
              <p className="text-xs text-blue-200 mt-0.5">
                {completedCount} / {AGENT_PIPELINE.length} agents
              </p>
            </div>
          </div>

          {/* Progress bar */}
          <div className="w-full bg-blue-800 rounded-full h-2.5 overflow-hidden">
            <div
              className={`h-2.5 rounded-full transition-all duration-700 ease-out ${
                hasError ? 'bg-red-400' : 'bg-green-400'
              }`}
              style={{ width: `${progressPercent}%` }}
            />
          </div>

          {/* Status line */}
          <div className="mt-3 flex items-center justify-between text-sm text-blue-100">
            <span>
              {currentAgent
                ? `⚡ ${currentAgent.displayName}...`
                : hasError
                ? 'Pipeline stopped due to error'
                : completedCount === AGENT_PIPELINE.length
                ? '✅ All agents completed successfully'
                : 'Initialising pipeline...'}
            </span>
            {!isConnected && completedCount < AGENT_PIPELINE.length && !hasError && (
              <span className="flex items-center gap-1 text-yellow-300">
                <Loader2 className="w-3 h-3 animate-spin" />
                Reconnecting...
              </span>
            )}
          </div>
        </div>

        {/* Quality score badge */}
        {qualityScore !== undefined && (
          <div className="px-8 py-3 bg-green-50 border-b border-green-100 flex items-center gap-2">
            <Zap className="w-4 h-4 text-green-600" />
            <span className="text-sm font-medium text-green-800">
              Quality Score: {qualityScore.toFixed(1)} / 10
            </span>
            <div className="flex-1 bg-green-200 rounded-full h-1.5 ml-2">
              <div
                className="bg-green-500 h-1.5 rounded-full"
                style={{ width: `${(qualityScore / 10) * 100}%` }}
              />
            </div>
          </div>
        )}

        {/* Agent list */}
        <div className="p-6 space-y-2">
          {agentStatuses.map((agent, index) => (
            <div
              key={agent.name}
              className={`flex items-center gap-4 p-3 rounded-lg transition-all duration-300 ${
                agent.status === 'running'
                  ? 'bg-blue-50 border border-blue-200 shadow-sm'
                  : agent.status === 'completed'
                  ? 'bg-gray-50'
                  : agent.status === 'error'
                  ? 'bg-red-50 border border-red-200'
                  : 'opacity-50'
              }`}
            >
              {/* Step number / icon */}
              <div className="flex-shrink-0 w-8 h-8 flex items-center justify-center">
                {agent.status === 'completed' && (
                  <CheckCircle className="w-6 h-6 text-green-500" />
                )}
                {agent.status === 'running' && (
                  <Loader2 className="w-6 h-6 text-blue-600 animate-spin" />
                )}
                {agent.status === 'error' && (
                  <XCircle className="w-6 h-6 text-red-500" />
                )}
                {agent.status === 'pending' && (
                  <div className="w-6 h-6 rounded-full border-2 border-gray-300 flex items-center justify-center">
                    <span className="text-xs text-gray-400 font-medium">{index + 1}</span>
                  </div>
                )}
              </div>

              {/* Agent info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p
                    className={`text-sm font-semibold ${
                      agent.status === 'completed'
                        ? 'text-gray-800'
                        : agent.status === 'running'
                        ? 'text-blue-700'
                        : agent.status === 'error'
                        ? 'text-red-700'
                        : 'text-gray-400'
                    }`}
                  >
                    {agent.displayName}
                  </p>
                  {agent.status === 'running' && (
                    <span className="text-xs bg-blue-100 text-blue-600 px-2 py-0.5 rounded-full font-medium animate-pulse">
                      Running
                    </span>
                  )}
                </div>
                <p
                  className={`text-xs mt-0.5 ${
                    agent.status === 'pending' ? 'text-gray-300' : 'text-gray-500'
                  }`}
                >
                  {agent.description}
                </p>
              </div>

              {/* Elapsed time */}
              {agent.elapsedMs !== undefined && (
                <div className="flex-shrink-0 flex items-center gap-1 text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
                  <Clock className="w-3 h-3" />
                  {formatElapsed(agent.elapsedMs)}
                </div>
              )}
              {agent.status === 'running' && (
                <div className="flex-shrink-0 text-xs text-blue-500 animate-pulse">
                  In progress...
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Footer summary */}
        {completedCount > 0 && (
          <div className="px-6 pb-6">
            <div className="bg-gray-50 rounded-lg p-4 flex items-center justify-between text-sm text-gray-600">
              <span className="flex items-center gap-2">
                <Clock className="w-4 h-4" />
                {completedCount === AGENT_PIPELINE.length
                  ? `Total pipeline time: ${formatElapsed(
                      agentStatuses.reduce((s, a) => s + (a.elapsedMs ?? 0), 0)
                    )}`
                  : `${completedCount} of ${AGENT_PIPELINE.length} agents completed`}
              </span>
              {completedCount === AGENT_PIPELINE.length && (
                <span className="text-green-600 font-medium flex items-center gap-1">
                  <CheckCircle className="w-4 h-4" />
                  Pipeline complete
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
