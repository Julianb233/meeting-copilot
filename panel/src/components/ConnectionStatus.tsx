interface ConnectionStatusProps {
  zoomStatus: 'connecting' | 'connected' | 'error' | 'standalone'
  engineConnected: boolean
  engineConnecting: boolean
}

export function ConnectionStatus({
  zoomStatus,
  engineConnected,
  engineConnecting,
}: ConnectionStatusProps) {
  return (
    <div>
      <h1 className="text-lg font-semibold text-white">Meeting Copilot</h1>
      <div className="flex items-center gap-4 mt-1">
        <div className="flex items-center gap-2">
          <span
            className={`inline-block w-2 h-2 rounded-full ${
              zoomStatus === 'connected'
                ? 'bg-green-500'
                : zoomStatus === 'standalone'
                  ? 'bg-yellow-500'
                  : zoomStatus === 'error'
                    ? 'bg-red-500'
                    : 'bg-zinc-500 animate-pulse'
            }`}
          />
          <span className="text-xs text-zinc-400">
            {zoomStatus === 'connected'
              ? 'Zoom'
              : zoomStatus === 'standalone'
                ? 'Standalone'
                : zoomStatus === 'error'
                  ? 'Zoom Error'
                  : 'Connecting...'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`inline-block w-2 h-2 rounded-full ${
              engineConnected
                ? 'bg-green-500'
                : engineConnecting
                  ? 'bg-zinc-500 animate-pulse'
                  : 'bg-red-500'
            }`}
          />
          <span className="text-xs text-zinc-400">
            {engineConnected
              ? 'Engine'
              : engineConnecting
                ? 'Engine...'
                : 'Engine Offline'}
          </span>
        </div>
      </div>
    </div>
  )
}
