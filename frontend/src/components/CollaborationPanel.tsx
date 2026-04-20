import { useState, useEffect, useCallback } from 'react'
import {
  X,
  MessageSquare,
  CheckCircle2,
  XCircle,
  Clock,
  Send,
  Loader2,
  AlertCircle,
  CheckCheck,
} from 'lucide-react'
import {
  getComments,
  addComment,
  resolveComment,
  getApprovalStatus,
  submitForApproval,
  approvePresentation,
  rejectPresentation,
} from '../services/api'

// ─── Types ───────────────────────────────────────────────────────────────────

interface Comment {
  id: string
  slide_id: string
  slide_title: string
  text: string
  author: string
  created_at: string
  resolved: boolean
}

type ApprovalStatus = 'draft' | 'pending_review' | 'approved' | 'rejected'

interface ApprovalInfo {
  status: ApprovalStatus
  submitted_at?: string
  reviewed_at?: string
  reviewer?: string
  rejection_reason?: string
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function ApprovalBadge({ status }: { status: ApprovalStatus }) {
  const config: Record<ApprovalStatus, { label: string; className: string; Icon: React.FC<{ className?: string }> }> = {
    draft: { label: 'Draft', className: 'bg-gray-100 text-gray-600', Icon: Clock },
    pending_review: { label: 'Pending Review', className: 'bg-amber-100 text-amber-700', Icon: Clock },
    approved: { label: 'Approved', className: 'bg-green-100 text-green-700', Icon: CheckCircle2 },
    rejected: { label: 'Rejected', className: 'bg-red-100 text-red-700', Icon: XCircle },
  }
  const { label, className, Icon } = config[status]
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${className}`}>
      <Icon className="w-3.5 h-3.5" />
      {label}
    </span>
  )
}

// ─── Main Component ───────────────────────────────────────────────────────────

interface CollaborationPanelProps {
  presentationId: string
  slides: Array<{ id: string; title: string }>
  onClose: () => void
}

export default function CollaborationPanel({
  presentationId,
  slides,
  onClose,
}: CollaborationPanelProps) {
  const [activeTab, setActiveTab] = useState<'comments' | 'approval'>('comments')

  // Comments state
  const [comments, setComments] = useState<Comment[]>([])
  const [isLoadingComments, setIsLoadingComments] = useState(true)
  const [newCommentText, setNewCommentText] = useState('')
  const [selectedSlideId, setSelectedSlideId] = useState<string>(slides[0]?.id ?? '')
  const [isSubmittingComment, setIsSubmittingComment] = useState(false)
  const [commentError, setCommentError] = useState<string | null>(null)
  const [showResolved, setShowResolved] = useState(false)

  // Approval state
  const [approval, setApproval] = useState<ApprovalInfo | null>(null)
  const [isLoadingApproval, setIsLoadingApproval] = useState(true)
  const [isSubmittingApproval, setIsSubmittingApproval] = useState(false)
  const [approvalError, setApprovalError] = useState<string | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const [showRejectForm, setShowRejectForm] = useState(false)

  const loadComments = useCallback(async () => {
    setIsLoadingComments(true)
    try {
      const response = await getComments(presentationId)
      setComments(response.data.comments ?? [])
    } catch {
      // silently fail — comments are non-critical
    } finally {
      setIsLoadingComments(false)
    }
  }, [presentationId])

  const loadApproval = useCallback(async () => {
    setIsLoadingApproval(true)
    try {
      const response = await getApprovalStatus(presentationId)
      setApproval(response.data)
    } catch {
      setApproval({ status: 'draft' })
    } finally {
      setIsLoadingApproval(false)
    }
  }, [presentationId])

  useEffect(() => {
    loadComments()
    loadApproval()
  }, [loadComments, loadApproval])

  // ── Comment actions ──

  const handleAddComment = async () => {
    if (!newCommentText.trim() || !selectedSlideId) return
    setIsSubmittingComment(true)
    setCommentError(null)
    try {
      const response = await addComment(presentationId, selectedSlideId, newCommentText.trim())
      setComments((prev) => [response.data, ...prev])
      setNewCommentText('')
    } catch {
      setCommentError('Failed to add comment.')
    } finally {
      setIsSubmittingComment(false)
    }
  }

  const handleResolveComment = async (commentId: string) => {
    try {
      await resolveComment(presentationId, commentId)
      setComments((prev) =>
        prev.map((c) => (c.id === commentId ? { ...c, resolved: true } : c)),
      )
    } catch {
      // silently fail
    }
  }

  // ── Approval actions ──

  const handleSubmitForApproval = async () => {
    setIsSubmittingApproval(true)
    setApprovalError(null)
    try {
      await submitForApproval(presentationId)
      setApproval((prev) => ({ ...prev!, status: 'pending_review', submitted_at: new Date().toISOString() }))
    } catch {
      setApprovalError('Failed to submit for approval.')
    } finally {
      setIsSubmittingApproval(false)
    }
  }

  const handleApprove = async () => {
    setIsSubmittingApproval(true)
    setApprovalError(null)
    try {
      await approvePresentation(presentationId)
      setApproval((prev) => ({ ...prev!, status: 'approved', reviewed_at: new Date().toISOString() }))
    } catch {
      setApprovalError('Failed to approve.')
    } finally {
      setIsSubmittingApproval(false)
    }
  }

  const handleReject = async () => {
    if (!rejectReason.trim()) return
    setIsSubmittingApproval(true)
    setApprovalError(null)
    try {
      await rejectPresentation(presentationId, rejectReason.trim())
      setApproval((prev) => ({
        ...prev!,
        status: 'rejected',
        reviewed_at: new Date().toISOString(),
        rejection_reason: rejectReason.trim(),
      }))
      setShowRejectForm(false)
      setRejectReason('')
    } catch {
      setApprovalError('Failed to reject.')
    } finally {
      setIsSubmittingApproval(false)
    }
  }

  const formatDate = (iso?: string) => {
    if (!iso) return ''
    try {
      return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(iso))
    } catch {
      return iso
    }
  }

  const visibleComments = comments.filter((c) => showResolved || !c.resolved)
  const unresolvedCount = comments.filter((c) => !c.resolved).length

  return (
    <div className="fixed inset-y-0 right-0 w-96 bg-white shadow-2xl border-l border-gray-200 flex flex-col z-50">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
        <h2 className="text-base font-semibold text-gray-900">Collaboration</h2>
        <button
          onClick={onClose}
          className="p-2 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors"
          aria-label="Close collaboration panel"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200">
        <button
          onClick={() => setActiveTab('comments')}
          className={`flex-1 flex items-center justify-center gap-2 py-3 text-sm font-medium transition-colors ${
            activeTab === 'comments'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          <MessageSquare className="w-4 h-4" />
          Comments
          {unresolvedCount > 0 && (
            <span className="bg-blue-100 text-blue-700 text-xs px-1.5 py-0.5 rounded-full font-semibold">
              {unresolvedCount}
            </span>
          )}
        </button>
        <button
          onClick={() => setActiveTab('approval')}
          className={`flex-1 flex items-center justify-center gap-2 py-3 text-sm font-medium transition-colors ${
            activeTab === 'approval'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          <CheckCircle2 className="w-4 h-4" />
          Approval
        </button>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto">
        {/* ── Comments tab ── */}
        {activeTab === 'comments' && (
          <div className="flex flex-col h-full">
            {/* New comment form */}
            <div className="p-4 border-b border-gray-100 space-y-3">
              <select
                value={selectedSlideId}
                onChange={(e) => setSelectedSlideId(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {slides.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.title}
                  </option>
                ))}
              </select>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newCommentText}
                  onChange={(e) => setNewCommentText(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddComment()}
                  placeholder="Add a comment…"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  onClick={handleAddComment}
                  disabled={!newCommentText.trim() || isSubmittingComment}
                  className="p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  aria-label="Send comment"
                >
                  {isSubmittingComment ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                </button>
              </div>
              {commentError && <p className="text-xs text-red-600">{commentError}</p>}
            </div>

            {/* Filter toggle */}
            <div className="px-4 py-2 flex items-center justify-between border-b border-gray-100">
              <p className="text-xs text-gray-500">
                {unresolvedCount} unresolved · {comments.length - unresolvedCount} resolved
              </p>
              <button
                onClick={() => setShowResolved((v) => !v)}
                className="text-xs text-blue-600 hover:text-blue-700"
              >
                {showResolved ? 'Hide resolved' : 'Show resolved'}
              </button>
            </div>

            {/* Comment list */}
            <div className="flex-1 overflow-y-auto divide-y divide-gray-100">
              {isLoadingComments && (
                <div className="flex items-center justify-center py-10">
                  <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
                </div>
              )}

              {!isLoadingComments && visibleComments.length === 0 && (
                <div className="text-center py-10 text-gray-400">
                  <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-40" />
                  <p className="text-sm">No comments yet.</p>
                </div>
              )}

              {visibleComments.map((comment) => (
                <div
                  key={comment.id}
                  className={`px-4 py-3 ${comment.resolved ? 'opacity-50' : ''}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-semibold text-gray-700">{comment.author}</span>
                        <span className="text-xs text-gray-400">{formatDate(comment.created_at)}</span>
                      </div>
                      <p className="text-xs text-gray-500 mb-1 truncate">
                        On: {comment.slide_title}
                      </p>
                      <p className="text-sm text-gray-800">{comment.text}</p>
                    </div>
                    {!comment.resolved && (
                      <button
                        onClick={() => handleResolveComment(comment.id)}
                        className="flex-shrink-0 p-1.5 text-gray-400 hover:text-green-600 hover:bg-green-50 rounded transition-colors"
                        title="Mark as resolved"
                      >
                        <CheckCheck className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Approval tab ── */}
        {activeTab === 'approval' && (
          <div className="p-4 space-y-4">
            {isLoadingApproval && (
              <div className="flex items-center justify-center py-10">
                <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
              </div>
            )}

            {!isLoadingApproval && approval && (
              <>
                {/* Status card */}
                <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-700">Status</span>
                    <ApprovalBadge status={approval.status} />
                  </div>
                  {approval.submitted_at && (
                    <p className="text-xs text-gray-500">
                      Submitted: {formatDate(approval.submitted_at)}
                    </p>
                  )}
                  {approval.reviewed_at && (
                    <p className="text-xs text-gray-500">
                      Reviewed: {formatDate(approval.reviewed_at)}
                      {approval.reviewer && ` by ${approval.reviewer}`}
                    </p>
                  )}
                  {approval.rejection_reason && (
                    <div className="bg-red-50 border border-red-200 rounded p-2">
                      <p className="text-xs text-red-700 font-medium">Rejection reason:</p>
                      <p className="text-xs text-red-600 mt-0.5">{approval.rejection_reason}</p>
                    </div>
                  )}
                </div>

                {/* Actions */}
                {approvalError && (
                  <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    {approvalError}
                  </div>
                )}

                {approval.status === 'draft' && (
                  <button
                    onClick={handleSubmitForApproval}
                    disabled={isSubmittingApproval}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
                  >
                    {isSubmittingApproval ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Send className="w-4 h-4" />
                    )}
                    Submit for Review
                  </button>
                )}

                {approval.status === 'pending_review' && (
                  <div className="space-y-2">
                    <button
                      onClick={handleApprove}
                      disabled={isSubmittingApproval}
                      className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
                    >
                      {isSubmittingApproval ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <CheckCircle2 className="w-4 h-4" />
                      )}
                      Approve
                    </button>

                    {!showRejectForm ? (
                      <button
                        onClick={() => setShowRejectForm(true)}
                        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border border-red-300 text-red-600 rounded-lg text-sm font-medium hover:bg-red-50 transition-colors"
                      >
                        <XCircle className="w-4 h-4" />
                        Reject
                      </button>
                    ) : (
                      <div className="space-y-2">
                        <textarea
                          value={rejectReason}
                          onChange={(e) => setRejectReason(e.target.value)}
                          placeholder="Reason for rejection…"
                          rows={3}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-red-400 resize-none"
                        />
                        <div className="flex gap-2">
                          <button
                            onClick={() => { setShowRejectForm(false); setRejectReason('') }}
                            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-600 hover:bg-gray-50 transition-colors"
                          >
                            Cancel
                          </button>
                          <button
                            onClick={handleReject}
                            disabled={!rejectReason.trim() || isSubmittingApproval}
                            className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-50 transition-colors"
                          >
                            {isSubmittingApproval ? (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                              <XCircle className="w-3 h-3" />
                            )}
                            Confirm Reject
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {(approval.status === 'approved' || approval.status === 'rejected') && (
                  <button
                    onClick={handleSubmitForApproval}
                    disabled={isSubmittingApproval}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border border-gray-300 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 disabled:opacity-50 transition-colors"
                  >
                    <Send className="w-4 h-4" />
                    Resubmit for Review
                  </button>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
