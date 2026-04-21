import { useState } from 'react'
import { Download, Loader2, CheckCircle, AlertCircle } from 'lucide-react'
import { downloadPptx } from '../services/api'

interface DownloadButtonProps {
  presentationId: string
  className?: string
}

type DownloadState = 'idle' | 'building' | 'done' | 'error'

export default function DownloadButton({ presentationId, className = '' }: DownloadButtonProps) {
  const [state, setState] = useState<DownloadState>('idle')

  const handleDownload = async () => {
    if (state !== 'idle' && state !== 'error') return
    setState('building')

    try {
      const response = await downloadPptx(presentationId)

      const disposition = response.headers['content-disposition'] || ''
      const match = disposition.match(/filename="?([^";\n]+)"?/)
      const filename = match ? match[1] : `presentation-${presentationId.slice(0, 8)}.pptx`

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

      setState('done')
      setTimeout(() => setState('idle'), 3000)
    } catch (err: any) {
      setState('error')
      setTimeout(() => setState('idle'), 4000)
    }
  }

  const isLoading = state === 'building'

  // Icon
  const Icon = () => {
    if (state === 'done')    return <CheckCircle className="w-5 h-5 flex-shrink-0" />
    if (state === 'error')   return <AlertCircle className="w-5 h-5 flex-shrink-0" />
    if (isLoading)           return <Loader2 className="w-5 h-5 flex-shrink-0 animate-spin" />
    return <Download className="w-5 h-5 flex-shrink-0" />
  }

  // Label
  const label = () => {
    if (state === 'done')    return 'Downloaded!'
    if (state === 'error')   return 'Retry Download'
    if (isLoading)           return 'Building PPTX…'
    return 'Download PPTX'
  }

  // Styles per state
  const styles = () => {
    if (state === 'done')
      return 'bg-emerald-600 hover:bg-emerald-700 text-white shadow-lg shadow-emerald-200/60'
    if (state === 'error')
      return 'bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-200/60'
    if (isLoading)
      return 'bg-blue-500/90 text-white cursor-not-allowed shadow-lg shadow-blue-200/60'
    return [
      'text-white',
      'bg-gradient-to-br from-blue-600 via-blue-600 to-indigo-700',
      'hover:from-blue-500 hover:via-blue-500 hover:to-indigo-600',
      'active:from-blue-700 active:to-indigo-800',
      'shadow-lg shadow-blue-300/50 hover:shadow-xl hover:shadow-blue-300/60',
    ].join(' ')
  }

  return (
    <button
      onClick={handleDownload}
      disabled={isLoading}
      className={`
        h-14 w-full rounded-xl text-sm font-semibold
        flex items-center justify-center gap-2.5
        transition-all duration-200
        ${styles()}
        ${className}
      `}
    >
      <Icon />
      {label()}
    </button>
  )
}
