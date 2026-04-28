import { CheckCircle, Loader2, XCircle, Clock, Zap } from 'lucide-react'
import { SSEEvent } from '../hooks/useSSEStream'

type GenerationMode = 'code' | 'hybrid' | 'json'

interface ProgressIndicatorProps {
  events: SSEEvent[]
  isConnected: boolean
  /** When true, the synthetic "Rendering Preview" step shows as running */
  previewRendering?: boolean
  /** When true, the synthetic "Rendering Preview" step shows as completed */
  previewReady?: boolean
  /** Elapsed time in ms for the rendering preview step */
  previewElapsedMs?: number
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
    name: 'design',
    displayName: 'Design System',
    description: 'Choosing palette, motif & typography for this topic',
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
    name: 'visual_refinement',
    displayName: 'Visual Refinement',
    description: 'Polishing visual hierarchy & slide aesthetics',
  },
  {
    name: 'quality_scoring',
    displayName: 'Quality Scoring',
    description: 'Scoring presentation quality & feedback',
  },
  {
    name: 'visual_qa',
    displayName: 'Visual QA',
    description: 'Inspecting slides for visual defects',
  },
]

// Mode-specific description overrides for Content Generation and Validation steps
const MODE_DESCRIPTIONS: Record<GenerationMode, Record<string, string>> = {
  code: {
    llm_provider: 'Generating pptxgenjs slide code with AI',
    validation: 'Validating generated code structure',
  },
  hybrid: {
    llm_provider: 'Generating slide content and code snippets',
    validation: 'Validating JSON structure and code snippets',
  },
  json: {},
}

// Badge labels and colors per generation mode
const MODE_BADGE: Record<GenerationMode, { label: string; className: string }> = {
  code: { label: 'Code Mode', className: 'bg-purple-500/20 text-purple-200 border-purple-400/30' },
  hybrid: { label: 'Hybrid Mode', className: 'bg-amber-500/20 text-amber-200 border-amber-400/30' },
  json: { label: 'JSON Mode', className: 'bg-blue-500/20 text-blue-200 border-blue-400/30' },
}

// Synthetic step appended after all agents complete
const PREVIEW_STEP_NAME = '__preview_render__'

function formatElapsed(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

/**
 * Extract generation_mode from the first agent_start SSE event that carries it.
 */
function extractGenerationMode(events: SSEEvent[]): GenerationMode | null {
  for (const e of events) {
    if (e.type === 'agent_start' && e.data.generation_mode) {
      const mode = e.data.generation_mode as string
      if (mode === 'code' || mode === 'hybrid' || mode === 'json') {
        return mode
      }
    }
  }
  return null
}

export default function ProgressIndicator({ events, isConnected, previewRendering = false, previewReady = false, previewElapsedMs }: ProgressIndicatorProps) {
  // Detect generation mode from SSE events
  const generationMode = extractGenerationMode(events)
  const modeOverrides = generationMode ? MODE_DESCRIPTIONS[generationMode] : {}

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

    // Apply mode-specific description override if available
    const description = modeOverrides[agent.name] ?? agent.description

    if (errorEvent) return { ...agent, description, status: 'error' as const }
    if (completeEvent) {
      return {
        ...agent,
        description,
        status: 'completed' as const,
        elapsedMs: completeEvent.data.elapsed_ms,
      }
    }
    if (startEvent) return { ...agent, description, status: 'running' as const }
    return { ...agent, description, status: 'pending' as const }
  })

  // Synthetic "Rendering Preview" step — appended after all pipeline agents
  const allAgentsComplete = agentStatuses.every((a) => a.status === 'completed')
  const previewStepStatus: AgentStatus['status'] = previewReady
    ? 'completed'
    : previewRendering || allAgentsComplete
    ? 'running'
    : 'pending'

  const previewStep: AgentStatus = {
    name: PREVIEW_STEP_NAME,
    displayName: 'Rendering Preview',
    description: 'Building PPTX and converting slides to images',
    status: previewStepStatus,
    elapsedMs: previewReady && previewElapsedMs ? previewElapsedMs : undefined,
  }

  const allStatuses = [...agentStatuses, previewStep]

  const completedCount = allStatuses.filter((a) => a.status === 'completed').length
  const totalSteps = allStatuses.length
  const hasError = agentStatuses.some((a) => a.status === 'error')
  const currentAgent = allStatuses.find((a) => a.status === 'running')
  // 100% only when preview is also ready
  const progressPercent = Math.round((completedCount / totalSteps) * 100)

  // Check for quality score
  const qualityEvent = events.find((e) => e.type === 'quality_score')
  const qualityScore = qualityEvent?.data?.composite_score

  // Badge info for the active generation mode
  const badge = generationMode ? MODE_BADGE[generationMode] : null

  return (
    <div className="w-full max-w-3xl mx-auto p-8">
      <div className="bg-white rounded-xl shadow-lg overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-slate-800 via-slate-700 to-slate-800 px-8 py-6 text-white">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              {hasError ? (
                <XCircle className="w-6 h-6 text-red-300" />
              ) : completedCount === totalSteps ? (
                <CheckCircle className="w-6 h-6 text-green-300" />
              ) : (
                <Loader2 className="w-6 h-6 animate-spin text-blue-200" />
              )}
              <h2 className="text-xl font-semibold">
                {hasError
                  ? 'Generation Failed'
                  : completedCount === totalSteps
                  ? 'Presentation Ready!'
                  : previewRendering || (allAgentsComplete && !previewReady)
                  ? 'Rendering Preview…'
                  : 'Generating Presentation'}
              </h2>
              {badge && (
                <span className={`text-xs font-medium px-2.5 py-0.5 rounded-full border ${badge.className}`}>
                  {badge.label}
                </span>
              )}
            </div>
            <div className="text-right">
              <span className="text-2xl font-bold">{progressPercent}%</span>
              <p className="text-xs text-blue-200 mt-0.5">
                {completedCount} / {totalSteps} steps
              </p>
            </div>
          </div>

          {/* Progress bar */}
          <div className="w-full bg-white/10 rounded-full h-2.5 overflow-hidden">
            <div
              className={`h-2.5 rounded-full transition-all duration-700 ease-out relative overflow-hidden ${
                hasError ? 'bg-red-400' : 'bg-emerald-400'
              }`}
              style={{ width: `${progressPercent}%` }}
            >
              {!hasError && progressPercent < 100 && (
                <div
                  className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-[shimmer_1.5s_infinite]"
                  style={{ backgroundSize: '200% 100%' }}
                />
              )}
            </div>
          </div>

          {/* Status line */}
          <div className="mt-3 flex items-center justify-between text-sm text-blue-100">
            <span>
              {currentAgent
                ? currentAgent.name === PREVIEW_STEP_NAME
                  ? '🖼️ Rendering slides to images…'
                  : `⚡ ${currentAgent.displayName}...`
                : hasError
                ? 'Pipeline stopped due to error'
                : completedCount === totalSteps
                ? '✅ All steps completed successfully'
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
          <style>{`
            @keyframes shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
            @keyframes slideIn { from { opacity: 0; transform: translateX(-8px); } to { opacity: 1; transform: translateX(0); } }
          `}</style>
          {allStatuses.map((agent, index) => (
            <div
              key={agent.name}
              className={`flex items-center gap-4 p-3 rounded-lg transition-all duration-300 ${
                agent.status === 'running'
                  ? 'bg-slate-50 border border-slate-200 shadow-sm'
                  : agent.status === 'completed'
                  ? 'bg-gray-50'
                  : agent.status === 'error'
                  ? 'bg-red-50 border border-red-200'
                  : 'opacity-40'
              }`}
              style={agent.status === 'completed' ? {
                animation: `slideIn 0.3s ease-out`,
                animationDelay: `${index * 0.05}s`,
                animationFillMode: 'both',
              } : undefined}
            >
              {/* Step number / icon */}
              <div className="flex-shrink-0 w-8 h-8 flex items-center justify-center">
                {agent.status === 'completed' && (
                  <CheckCircle className="w-6 h-6 text-green-500" />
                )}
                {agent.status === 'running' && (
                  <Loader2 className="w-6 h-6 text-slate-600 animate-spin" />
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
                        ? 'text-slate-700'
                        : agent.status === 'error'
                        ? 'text-red-700'
                        : 'text-gray-400'
                    }`}
                  >
                    {agent.displayName}
                  </p>
                  {agent.status === 'running' && (
                    <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-medium animate-pulse">
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
                <div className="flex-shrink-0 text-xs text-slate-500 animate-pulse">
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
                {completedCount === totalSteps
                  ? `Total time: ${formatElapsed(
                      allStatuses.reduce((s, a) => s + (a.elapsedMs ?? 0), 0)
                    )}`
                  : `${completedCount} of ${totalSteps} steps completed`}
              </span>
              {completedCount === totalSteps && (
                <span className="text-green-600 font-medium flex items-center gap-1">
                  <CheckCircle className="w-4 h-4" />
                  Ready
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
