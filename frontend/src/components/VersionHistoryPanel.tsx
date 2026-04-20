import { useState, useEffect } from 'react'
import { X, Clock, RotateCcw, GitCompare, ChevronRight, Loader2, AlertCircle } from 'lucide-react'
import { getVersions, getDiff, rollbackVersion } from '../services/api'

interface Version {
  version: number
  created_at: string
  created_by?: string
  change_summary?: string
  slide_count: number
}

interface DiffEntry {
  slide_id: string
  slide_title: string
  change_type: 'added' | 'removed' | 'modified'
  field?: string
  before?: string
  after?: string
}

interface VersionHistoryPanelProps {
  presentationId: string
  currentVersion: number
  onClose: () => void
  onRollback: (version: number) => void
}

export default function VersionHistoryPanel({
  presentationId,
  currentVersion,
  onClose,
  onRollback,
}: VersionHistoryPanelProps) {
  const [versions, setVersions] = useState<Version[]>([])
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null)
  const [diffEntries, setDiffEntries] = useState<DiffEntry[]>([])
  const [isLoadingVersions, setIsLoadingVersions] = useState(true)
  const [isLoadingDiff, setIsLoadingDiff] = useState(false)
  const [isRollingBack, setIsRollingBack] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [rollbackError, setRollbackError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      setIsLoadingVersions(true)
      try {
        const response = await getVersions(presentationId)
        setVersions(response.data.versions ?? [])
      } catch {
        setError('Failed to load version history.')
      } finally {
        setIsLoadingVersions(false)
      }
    }
    load()
  }, [presentationId])

  const handleSelectVersion = async (version: number) => {
    if (version === selectedVersion) {
      setSelectedVersion(null)
      setDiffEntries([])
      return
    }
    setSelectedVersion(version)
    setIsLoadingDiff(true)
    setDiffEntries([])
    try {
      const response = await getDiff(presentationId, version, currentVersion)
      setDiffEntries(response.data.changes ?? [])
    } catch {
      setDiffEntries([])
    } finally {
      setIsLoadingDiff(false)
    }
  }

  const handleRollback = async (version: number) => {
    setIsRollingBack(true)
    setRollbackError(null)
    try {
      await rollbackVersion(presentationId, version)
      onRollback(version)
      onClose()
    } catch {
      setRollbackError(`Failed to rollback to version ${version}.`)
    } finally {
      setIsRollingBack(false)
    }
  }

  const formatDate = (iso: string) => {
    try {
      return new Intl.DateTimeFormat('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      }).format(new Date(iso))
    } catch {
      return iso
    }
  }

  const changeTypeColor = (type: DiffEntry['change_type']) => {
    switch (type) {
      case 'added': return 'text-green-700 bg-green-50 border-green-200'
      case 'removed': return 'text-red-700 bg-red-50 border-red-200'
      case 'modified': return 'text-amber-700 bg-amber-50 border-amber-200'
    }
  }

  return (
    <div className="fixed inset-y-0 right-0 w-[480px] bg-white shadow-2xl border-l border-gray-200 flex flex-col z-50">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <Clock className="w-5 h-5 text-blue-600" />
          <h2 className="text-base font-semibold text-gray-900">Version History</h2>
        </div>
        <button
          onClick={onClose}
          className="p-2 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors"
          aria-label="Close version history"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto">
        {isLoadingVersions && (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 m-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}

        {!isLoadingVersions && !error && versions.length === 0 && (
          <div className="text-center py-16 text-gray-400">
            <Clock className="w-10 h-10 mx-auto mb-3 opacity-40" />
            <p className="text-sm">No version history yet.</p>
          </div>
        )}

        {!isLoadingVersions && versions.length > 0 && (
          <div className="divide-y divide-gray-100">
            {versions.map((v) => {
              const isCurrent = v.version === currentVersion
              const isSelected = v.version === selectedVersion

              return (
                <div key={v.version} className="px-4 py-3">
                  {/* Version row */}
                  <div
                    className={`flex items-start gap-3 cursor-pointer rounded-lg p-2 transition-colors ${
                      isSelected ? 'bg-blue-50' : 'hover:bg-gray-50'
                    }`}
                    onClick={() => handleSelectVersion(v.version)}
                  >
                    <div className="flex-shrink-0 mt-0.5">
                      <div
                        className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                          isCurrent
                            ? 'bg-blue-600 text-white'
                            : 'bg-gray-200 text-gray-600'
                        }`}
                      >
                        {v.version}
                      </div>
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-800">
                          Version {v.version}
                        </span>
                        {isCurrent && (
                          <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded font-medium">
                            Current
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500 mt-0.5">{formatDate(v.created_at)}</p>
                      {v.change_summary && (
                        <p className="text-xs text-gray-600 mt-1 truncate">{v.change_summary}</p>
                      )}
                      <p className="text-xs text-gray-400 mt-0.5">{v.slide_count} slides</p>
                    </div>

                    <div className="flex items-center gap-1 flex-shrink-0">
                      {!isCurrent && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            handleRollback(v.version)
                          }}
                          disabled={isRollingBack}
                          className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                          title={`Rollback to version ${v.version}`}
                        >
                          <RotateCcw className="w-4 h-4" />
                        </button>
                      )}
                      <ChevronRight
                        className={`w-4 h-4 text-gray-400 transition-transform ${isSelected ? 'rotate-90' : ''}`}
                      />
                    </div>
                  </div>

                  {/* Diff view */}
                  {isSelected && (
                    <div className="mt-2 ml-10">
                      {isLoadingDiff && (
                        <div className="flex items-center gap-2 text-xs text-gray-500 py-2">
                          <Loader2 className="w-3 h-3 animate-spin" />
                          Loading diff…
                        </div>
                      )}

                      {!isLoadingDiff && diffEntries.length === 0 && !isCurrent && (
                        <div className="flex items-center gap-2 text-xs text-gray-400 py-2">
                          <GitCompare className="w-3 h-3" />
                          No differences found
                        </div>
                      )}

                      {!isLoadingDiff && diffEntries.length > 0 && (
                        <div className="space-y-1.5">
                          <p className="text-xs font-medium text-gray-500 flex items-center gap-1 mb-2">
                            <GitCompare className="w-3 h-3" />
                            Changes vs current
                          </p>
                          {diffEntries.map((entry, i) => (
                            <div
                              key={i}
                              className={`text-xs border rounded p-2 ${changeTypeColor(entry.change_type)}`}
                            >
                              <div className="flex items-center gap-1.5 font-medium">
                                <span className="capitalize">{entry.change_type}</span>
                                <span className="opacity-70">·</span>
                                <span className="truncate">{entry.slide_title}</span>
                              </div>
                              {entry.field && (
                                <p className="mt-0.5 opacity-80">Field: {entry.field}</p>
                              )}
                              {entry.before && (
                                <p className="mt-0.5 line-through opacity-60 truncate">
                                  {entry.before}
                                </p>
                              )}
                              {entry.after && (
                                <p className="mt-0.5 truncate">{entry.after}</p>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Footer */}
      {rollbackError && (
        <div className="px-6 py-3 border-t border-gray-200">
          <p className="text-xs text-red-600">{rollbackError}</p>
        </div>
      )}
    </div>
  )
}
