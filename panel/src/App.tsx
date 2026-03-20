import { useEffect, useState } from 'react'
import zoomSdk from '@zoom/appssdk'
import { useEngine } from './hooks/useEngine.ts'
import { useMeetingStore } from './stores/meetingStore.ts'

type ZoomConnectionStatus = 'connecting' | 'connected' | 'error' | 'standalone'

function App() {
  const [zoomStatus, setZoomStatus] = useState<ZoomConnectionStatus>('connecting')
  const [meetingContext, setMeetingContext] = useState<Record<string, unknown> | null>(null)
  const { connected: engineConnected, connecting: engineConnecting } = useEngine()
  const meetingState = useMeetingStore((s) => s.state)

  useEffect(() => {
    async function initZoom() {
      try {
        const configResponse = await zoomSdk.config({
          capabilities: [
            'getMeetingContext',
            'onMeeting',
            'openUrl',
          ],
        })
        console.log('Zoom SDK configured:', configResponse)
        setZoomStatus('connected')

        const ctx = await zoomSdk.getMeetingContext()
        setMeetingContext(ctx as Record<string, unknown>)
      } catch (err) {
        console.log('Not running inside Zoom, standalone mode:', err)
        setZoomStatus('standalone')
      }
    }
    initZoom()
  }, [])

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-4 font-sans">
      <header className="mb-6">
        <h1 className="text-lg font-semibold text-white">Meeting Copilot</h1>
        <div className="flex items-center gap-4 mt-1">
          <div className="flex items-center gap-2">
            <span className={`inline-block w-2 h-2 rounded-full ${
              zoomStatus === 'connected' ? 'bg-green-500' :
              zoomStatus === 'standalone' ? 'bg-yellow-500' :
              zoomStatus === 'error' ? 'bg-red-500' :
              'bg-zinc-500 animate-pulse'
            }`} />
            <span className="text-xs text-zinc-400">
              {zoomStatus === 'connected' ? 'Zoom' :
               zoomStatus === 'standalone' ? 'Standalone' :
               zoomStatus === 'error' ? 'Zoom Error' :
               'Connecting...'}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className={`inline-block w-2 h-2 rounded-full ${
              engineConnected ? 'bg-green-500' :
              engineConnecting ? 'bg-zinc-500 animate-pulse' :
              'bg-red-500'
            }`} />
            <span className="text-xs text-zinc-400">
              {engineConnected ? 'Engine' :
               engineConnecting ? 'Engine...' :
               'Engine Offline'}
            </span>
          </div>
        </div>
      </header>

      <section className="space-y-4">
        <div className="bg-zinc-900 rounded-lg p-4 border border-zinc-800">
          <h2 className="text-sm font-medium text-zinc-300 mb-2">Status</h2>
          <p className="text-sm text-zinc-500">
            {meetingState.active
              ? `Meeting active: ${meetingState.context.title ?? 'Untitled'}`
              : 'Waiting for meeting to start...'}
          </p>
        </div>

        <div className="bg-zinc-900 rounded-lg p-4 border border-zinc-800">
          <h2 className="text-sm font-medium text-zinc-300 mb-2">Tasks</h2>
          {meetingState.tasks.length > 0 ? (
            <ul className="space-y-1">
              {meetingState.tasks.map((task) => (
                <li key={task.id} className="text-sm text-zinc-400 flex items-center gap-2">
                  <span className={`inline-block w-1.5 h-1.5 rounded-full ${
                    task.status === 'completed' ? 'bg-green-500' :
                    task.status === 'failed' ? 'bg-red-500' :
                    task.status === 'running' ? 'bg-blue-500 animate-pulse' :
                    'bg-zinc-600'
                  }`} />
                  {task.title}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-zinc-500">No active tasks</p>
          )}
        </div>

        <div className="bg-zinc-900 rounded-lg p-4 border border-zinc-800">
          <h2 className="text-sm font-medium text-zinc-300 mb-2">Agent Status</h2>
          <div className="grid grid-cols-2 gap-2">
            {meetingState.agents.map((agent) => (
              <div key={agent.name} className="flex items-center gap-2 text-sm text-zinc-400">
                <span className={`inline-block w-1.5 h-1.5 rounded-full ${
                  agent.status === 'idle' ? 'bg-zinc-600' :
                  agent.status === 'busy' ? 'bg-blue-500 animate-pulse' :
                  'bg-yellow-500'
                }`} />
                <span>{agent.name}</span>
                <span className="text-zinc-600 text-xs">
                  {agent.current_task ?? agent.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {meetingContext && (
        <details className="mt-4 text-xs text-zinc-600">
          <summary>Debug: Meeting Context</summary>
          <pre className="mt-2 overflow-auto">{JSON.stringify(meetingContext, null, 2)}</pre>
        </details>
      )}
    </div>
  )
}

export default App
