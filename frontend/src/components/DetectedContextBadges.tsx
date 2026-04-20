import { Building2, Users, FileText, Sparkles } from 'lucide-react'

interface DetectedContext {
  industry?: string
  audience?: string
  template_id?: string
  template_name?: string
  confidence_score?: number
  theme?: string
}

interface DetectedContextBadgesProps {
  context: DetectedContext | null
}

export default function DetectedContextBadges({ context }: DetectedContextBadgesProps) {
  if (!context) {
    return null
  }

  const badges = []

  // Industry badge
  if (context.industry) {
    badges.push({
      icon: Building2,
      label: 'Industry',
      value: context.industry,
      color: 'blue',
    })
  }

  // Audience badge
  if (context.audience) {
    badges.push({
      icon: Users,
      label: 'Audience',
      value: context.audience,
      color: 'green',
    })
  }

  // Template badge
  if (context.template_name || context.template_id) {
    badges.push({
      icon: FileText,
      label: 'Template',
      value: context.template_name || `Template ${context.template_id?.slice(0, 8)}`,
      color: 'purple',
    })
  }

  // Theme badge
  if (context.theme) {
    badges.push({
      icon: Sparkles,
      label: 'Theme',
      value: context.theme.replace('-', ' ').replace(/\b\w/g, (l) => l.toUpperCase()),
      color: 'pink',
    })
  }

  if (badges.length === 0) {
    return null
  }

  const colorClasses = {
    blue: 'bg-blue-100 text-blue-800 border-blue-200',
    green: 'bg-green-100 text-green-800 border-green-200',
    purple: 'bg-purple-100 text-purple-800 border-purple-200',
    pink: 'bg-pink-100 text-pink-800 border-pink-200',
  }

  return (
    <div className="w-full max-w-3xl mx-auto px-8 pb-4">
      <div className="bg-white rounded-lg shadow-md p-4">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles className="w-5 h-5 text-gray-600" />
          <h3 className="text-sm font-semibold text-gray-700">
            Auto-Detected Context
          </h3>
          {context.confidence_score !== undefined && (
            <span className="text-xs text-gray-500 ml-auto">
              {Math.round(context.confidence_score * 100)}% confidence
            </span>
          )}
        </div>
        
        <div className="flex flex-wrap gap-2">
          {badges.map((badge, index) => {
            const Icon = badge.icon
            return (
              <div
                key={index}
                className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-sm font-medium ${
                  colorClasses[badge.color as keyof typeof colorClasses]
                }`}
              >
                <Icon className="w-4 h-4" />
                <span className="text-xs font-semibold opacity-75">
                  {badge.label}:
                </span>
                <span>{badge.value}</span>
              </div>
            )
          })}
        </div>

        <p className="text-xs text-gray-500 mt-3">
          These settings were automatically detected from your topic and cannot be changed.
        </p>
      </div>
    </div>
  )
}
