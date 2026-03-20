import { useEffect, useState } from 'react'
import zoomSdk from '@zoom/appssdk'

type ConnectionStatus = 'connecting' | 'connected' | 'error' | 'standalone'

function App() {
  const [zoomStatus, setZoomStatus] = useState<ConnectionStatus>('connecting')
  const [meetingContext, setMeetingContext] = useState<Record<string, unknown> | null>(null)

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
        <div className="flex items-center gap-2 mt-1">
          <span className={`inline-block w-2 h-2 rounded-full ${
            zoomStatus === 'connected' ? 'bg-green-500' :
            zoomStatus === 'standalone' ? 'bg-yellow-500' :
            zoomStatus === 'error' ? 'bg-red-500' :
            'bg-zinc-500 animate-pulse'
          }`} />
          <span className="text-xs text-zinc-400">
            {zoomStatus === 'connected' ? 'Connected to Zoom' :
             zoomStatus === 'standalone' ? 'Standalone Mode' :
             zoomStatus === 'error' ? 'Connection Error' :
             'Connecting...'}
          </span>
        </div>
      </header>

      <section className="space-y-4">
        <div className="bg-zinc-900 rounded-lg p-4 border border-zinc-800">
          <h2 className="text-sm font-medium text-zinc-300 mb-2">Status</h2>
          <p className="text-sm text-zinc-500">Waiting for meeting to start...</p>
        </div>

        <div className="bg-zinc-900 rounded-lg p-4 border border-zinc-800">
          <h2 className="text-sm font-medium text-zinc-300 mb-2">Tasks</h2>
          <p className="text-sm text-zinc-500">No active tasks</p>
        </div>

        <div className="bg-zinc-900 rounded-lg p-4 border border-zinc-800">
          <h2 className="text-sm font-medium text-zinc-300 mb-2">Agent Status</h2>
          <p className="text-sm text-zinc-500">All agents idle</p>
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
