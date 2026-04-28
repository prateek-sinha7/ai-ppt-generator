import { useState, useRef, useEffect } from 'react'
import { Download, Loader2, CheckCircle, AlertCircle, ChevronDown, FileText, FileSpreadsheet, File } from 'lucide-react'
import { downloadPptx, exportPdf, exportDocx, exportXlsx, getExportStatus } from '../services/api'

interface DownloadButtonProps {
  presentationId: string
  className?: string
}

type DownloadState = 'idle' | 'building' | 'done' | 'error'
type ExportFormat = 'pptx' | 'pdf' | 'docx' | 'xlsx'

const FORMAT_OPTIONS: { value: ExportFormat; label: string; icon: React.ReactNode }[] = [
  { value: 'pptx', label: 'PowerPoint (.pptx)', icon: <File className="w-4 h-4" /> },
  { value: 'pdf', label: 'PDF (.pdf)', icon: <FileText className="w-4 h-4" /> },
  { value: 'docx', label: 'Word (.docx)', icon: <FileText className="w-4 h-4" /> },
  { value: 'xlsx', label: 'Excel (.xlsx)', icon: <FileSpreadsheet className="w-4 h-4" /> },
]

const POLL_INTERVAL_MS = 1500
const MAX_POLL_ATTEMPTS = 60

export default function DownloadButton({ presentationId, className = '' }: DownloadButtonProps) {
  const [state, setState] = useState<DownloadState>('idle')
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>('pptx')
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const pollExportStatus = async (jobId: string): Promise<string> => {
    for (let i = 0; i < MAX_POLL_ATTEMPTS; i++) {
      await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS))
      const res = await getExportStatus(presentationId, jobId)
      const data = res.data
      if (data.status === 'completed' && data.download_url) {
        return data.download_url
      }
      if (data.status === 'failed') {
        throw new Error(data.message || 'Export failed')
      }
    }
    throw new Error('Export timed out')
  }

  const handleDownloadPptx = async () => {
    const response = await downloadPptx(presentationId)
    const disposition = response.headers['content-disposition'] || ''
    const match = disposition.match(/filename="?([^";\n]+)"?/)
    const filename = match ? match[1] : `presentation-${presentationId.slice(0, 8)}.pptx`

    const url = URL.createObjectURL(
      new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      })
    )
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const handleExportFormat = async (format: ExportFormat) => {
    const exportFn = format === 'pdf' ? exportPdf : format === 'docx' ? exportDocx : exportXlsx
    const res = await exportFn(presentationId)
    const jobId: string = res.data.job_id

    const downloadUrl = await pollExportStatus(jobId)

    // Download from the signed URL
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = `presentation-${presentationId.slice(0, 8)}.${format}`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const handleDownload = async () => {
    if (state !== 'idle' && state !== 'error') return
    setState('building')

    try {
      if (selectedFormat === 'pptx') {
        await handleDownloadPptx()
      } else {
        await handleExportFormat(selectedFormat)
      }
      setState('done')
      setTimeout(() => setState('idle'), 3000)
    } catch {
      setState('error')
      setTimeout(() => setState('idle'), 4000)
    }
  }

  const handleFormatSelect = (format: ExportFormat) => {
    setSelectedFormat(format)
    setDropdownOpen(false)
  }

  const isLoading = state === 'building'

  const currentOption = FORMAT_OPTIONS.find((o) => o.value === selectedFormat)!

  const Icon = () => {
    if (state === 'done') return <CheckCircle className="w-5 h-5 flex-shrink-0" />
    if (state === 'error') return <AlertCircle className="w-5 h-5 flex-shrink-0" />
    if (isLoading) return <Loader2 className="w-5 h-5 flex-shrink-0 animate-spin" />
    return <Download className="w-5 h-5 flex-shrink-0" />
  }

  const label = () => {
    if (state === 'done') return 'Downloaded!'
    if (state === 'error') return 'Retry Download'
    if (isLoading) return `Exporting ${selectedFormat.toUpperCase()}…`
    return `Download ${currentOption.label.split(' ')[0]}`
  }

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
    <div className={`relative ${className}`} ref={dropdownRef}>
      <div className="flex w-full">
        {/* Main download button */}
        <button
          onClick={handleDownload}
          disabled={isLoading}
          className={`
            h-14 flex-1 rounded-l-xl text-sm font-semibold
            flex items-center justify-center gap-2.5
            transition-all duration-200
            ${styles()}
          `}
        >
          <Icon />
          {label()}
        </button>

        {/* Format dropdown toggle */}
        <button
          onClick={() => !isLoading && setDropdownOpen((prev) => !prev)}
          disabled={isLoading}
          className={`
            h-14 w-12 rounded-r-xl text-sm font-semibold
            flex items-center justify-center
            border-l border-white/20
            transition-all duration-200
            ${styles()}
          `}
          aria-label="Select export format"
        >
          <ChevronDown className={`w-4 h-4 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {/* Dropdown menu */}
      {dropdownOpen && (
        <div className="absolute bottom-full mb-2 left-0 right-0 bg-white rounded-xl shadow-xl border border-gray-200 overflow-hidden z-50">
          {FORMAT_OPTIONS.map((option) => (
            <button
              key={option.value}
              onClick={() => handleFormatSelect(option.value)}
              className={`
                w-full px-4 py-3 text-sm text-left flex items-center gap-3
                transition-colors duration-150
                ${selectedFormat === option.value
                  ? 'bg-blue-50 text-blue-700 font-medium'
                  : 'text-gray-700 hover:bg-gray-50'
                }
              `}
            >
              {option.icon}
              {option.label}
              {selectedFormat === option.value && (
                <CheckCircle className="w-4 h-4 ml-auto text-blue-600" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
