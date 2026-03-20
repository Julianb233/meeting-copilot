import { useEffect, useCallback, useRef } from 'react'
import useWebSocket, { ReadyState } from 'react-use-websocket'
import { useMeetingStore } from '../stores/meetingStore.ts'
import type { EngineMessage, PanelMessage } from '../types/messages.ts'

export function useEngine() {
  const {
    engineUrl,
    setConnected,
    setFullState,
    setMeetingStarted,
    addTask,
    updateTaskCompleted,
    updateTaskFailed,
    setAgentStatus,
  } = useMeetingStore()

  const pingInterval = useRef<ReturnType<typeof setInterval> | null>(null)

  const { sendJsonMessage, readyState, lastJsonMessage } = useWebSocket(engineUrl, {
    shouldReconnect: () => true,
    reconnectAttempts: Infinity,
    reconnectInterval: 3000,
    onOpen: () => {
      console.log('[Engine] WebSocket connected')
      setConnected(true)
      // Start ping interval
      pingInterval.current = setInterval(() => {
        sendJsonMessage({ type: 'ping' })
      }, 30000)
    },
    onClose: () => {
      console.log('[Engine] WebSocket disconnected')
      setConnected(false)
      if (pingInterval.current) {
        clearInterval(pingInterval.current)
        pingInterval.current = null
      }
    },
    onError: (event) => {
      console.error('[Engine] WebSocket error:', event)
    },
  })

  // Handle incoming messages
  useEffect(() => {
    if (!lastJsonMessage) return
    const msg = lastJsonMessage as EngineMessage

    switch (msg.type) {
      case 'connection_ack':
        setFullState(msg.meeting_state)
        break
      case 'meeting_started':
        setMeetingStarted(msg.context)
        break
      case 'task_dispatched':
        addTask(msg.task)
        break
      case 'task_completed':
        updateTaskCompleted(msg.task_id, msg.result)
        break
      case 'task_failed':
        updateTaskFailed(msg.task_id, msg.error)
        break
      case 'agent_status':
        setAgentStatus(msg.agents)
        break
      case 'pong':
        // heartbeat response, no action needed
        break
      default:
        console.log('[Engine] Unhandled message:', msg)
    }
  }, [lastJsonMessage, setFullState, setMeetingStarted, addTask, updateTaskCompleted, updateTaskFailed, setAgentStatus])

  const sendAction = useCallback(
    (message: PanelMessage) => {
      sendJsonMessage(message)
    },
    [sendJsonMessage],
  )

  return {
    connected: readyState === ReadyState.OPEN,
    connecting: readyState === ReadyState.CONNECTING,
    sendAction,
  }
}
