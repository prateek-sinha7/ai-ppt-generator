import axios from 'axios'
import { SlideData } from '../types'

export const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    } else {
      console.warn('No access token found in localStorage')
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      console.error('401 Unauthorized - clearing token and redirecting to login')
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

// --- Slide reordering ---
export const reorderSlides = (presentationId: string, slideIds: string[]) =>
  apiClient.patch(`/presentations/${presentationId}/slides/reorder`, { slide_ids: slideIds })

// --- Slide editing ---
export const updateSlide = (presentationId: string, slideId: string, content: Partial<SlideData>) =>
  apiClient.patch(`/presentations/${presentationId}/slides/${slideId}`, content)

// --- Export ---
export const triggerPptxExport = (presentationId: string) =>
  apiClient.post(`/presentations/${presentationId}/export/pptx`)

export const getPptxExportStatus = (presentationId: string) =>
  apiClient.get(`/presentations/${presentationId}/export/pptx/status`)

// --- Versions ---
export const getVersions = (presentationId: string) =>
  apiClient.get(`/presentations/${presentationId}/versions`)

export const getVersion = (presentationId: string, version: number) =>
  apiClient.get(`/presentations/${presentationId}/versions/${version}`)

export const getDiff = (presentationId: string, fromVersion: number, toVersion: number) =>
  apiClient.get(`/presentations/${presentationId}/diff`, { params: { from: fromVersion, to: toVersion } })

export const rollbackVersion = (presentationId: string, version: number) =>
  apiClient.post(`/presentations/${presentationId}/rollback`, { version })

// --- Slide locks ---
export const lockSlide = (presentationId: string, slideId: string) =>
  apiClient.post(`/presentations/${presentationId}/slides/${slideId}/lock`)

export const unlockSlide = (presentationId: string, slideId: string) =>
  apiClient.delete(`/presentations/${presentationId}/slides/${slideId}/lock`)

// --- Comments ---
export const getComments = (presentationId: string) =>
  apiClient.get(`/presentations/${presentationId}/comments`)

export const addComment = (presentationId: string, slideId: string, text: string) =>
  apiClient.post(`/presentations/${presentationId}/comments`, { slide_id: slideId, text })

export const resolveComment = (presentationId: string, commentId: string) =>
  apiClient.patch(`/presentations/${presentationId}/comments/${commentId}/resolve`)

// --- Approval workflow ---
export const getApprovalStatus = (presentationId: string) =>
  apiClient.get(`/presentations/${presentationId}/approval`)

export const submitForApproval = (presentationId: string) =>
  apiClient.post(`/presentations/${presentationId}/approval/submit`)

export const approvePresentation = (presentationId: string) =>
  apiClient.post(`/presentations/${presentationId}/approval/approve`)

export const rejectPresentation = (presentationId: string, reason: string) =>
  apiClient.post(`/presentations/${presentationId}/approval/reject`, { reason })
