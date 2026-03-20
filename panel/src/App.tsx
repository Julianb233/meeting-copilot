import { useZoomContext } from './hooks/useZoomContext.ts'
import { useEngine } from './hooks/useEngine.ts'
import { PanelLayout } from './components/PanelLayout.tsx'
import { QuickActions } from './components/QuickActions.tsx'

function App() {
  const { zoomStatus, meetingContext } = useZoomContext()
  const { connected, connecting, sendAction } = useEngine()

  return (
    <>
      <PanelLayout
        zoomStatus={zoomStatus}
        engineConnected={connected}
        engineConnecting={connecting}
        footer={<QuickActions sendAction={sendAction} disabled={!connected} />}
      />
      {meetingContext && (
        <details className="fixed bottom-0 left-0 right-0 bg-zinc-950 p-2 text-xs text-zinc-600 z-50">
          <summary>Debug: Meeting Context</summary>
          <pre className="mt-2 overflow-auto max-h-32">
            {JSON.stringify(meetingContext, null, 2)}
          </pre>
        </details>
      )}
    </>
  )
}

export default App
