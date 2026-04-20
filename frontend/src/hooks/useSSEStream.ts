import { useEffect, useRef, useState } from 'react'

export type SSEEventType = 
  | 'agent_start' 
  | 'agent_complete' 
  | 'slide_ready' 
  | 'quality_score' 
  | 'complete' 
  | 'error'

export interface SSEEvent {
  id: string
  type: SSEEventType
  data: any
}

export interface SSEStreamState {
  events: SSEEvent[]
  isConnected: boolean
  error: string | null
  lastEventId: string | null
}

export function useSSEStream(presentationId: string | null, enabled: boolean = true) {
  const [state, setState] = useState<SSEStreamState>({
    events: [],
    isConnected: false,
    error: null,
    lastEventId: null,
  })

  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)

  useEffect(() => {
    if (!presentationId || !enabled) {
      return
    }

    const connect = () => {
      // Get token from localStorage
      const token = localStorage.getItem('access_token')
      if (!token) {
        console.error('No access token found for SSE connection')
        setState((prev) => ({ 
          ...prev, 
          error: 'Authentication required',
          isConnected: false 
        }))
        return
      }

      // EventSource doesn't support custom headers, so we pass token as query param
      const url = `/api/v1/presentations/${presentationId}/stream?token=${encodeURIComponent(token)}`
      
      const eventSource = new EventSource(url)

      eventSource.onopen = () => {
        setState((prev) => ({ ...prev, isConnected: true, error: null }))
      }

      eventSource.onerror = (err) => {
        console.error('SSE connection error:', err)
        setState((prev) => ({ 
          ...prev, 
          isConnected: false,
          error: 'Connection lost. Reconnecting...'
        }))
        
        eventSource.close()
        
        // Attempt reconnection after 3 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          connect()
        }, 3000)
      }

      // Register handlers for each event type
      const eventTypes: SSEEventType[] = [
        'agent_start',
        'agent_complete',
        'slide_ready',
        'quality_score',
        'complete',
        'error',
      ]

      eventTypes.forEach((eventType) => {
        eventSource.addEventListener(eventType, (event: MessageEvent) => {
          const messageEvent = event as MessageEvent
          const data = JSON.parse(messageEvent.data)
          const eventId = (event as any).lastEventId || messageEvent.lastEventId || null

          const sseEvent: SSEEvent = {
            id: eventId,
            type: eventType,
            data,
          }

          setState((prev) => ({
            ...prev,
            events: [...prev.events, sseEvent],
            lastEventId: eventId,
          }))

          // Close connection on terminal events
          if (eventType === 'complete' || eventType === 'error') {
            eventSource.close()
            setState((prev) => ({ ...prev, isConnected: false }))
          }
        })
      })

      eventSourceRef.current = eventSource
    }

    connect()

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
    }
  }, [presentationId, enabled])

  return state
}
