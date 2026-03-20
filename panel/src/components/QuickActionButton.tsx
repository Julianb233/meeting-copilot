import { useState, useEffect, useCallback } from 'react'
import { Loader2 } from 'lucide-react'
import type { QuickActionType, PanelMessage } from '../types/messages.ts'

interface QuickActionButtonProps {
  action: QuickActionType
  label: string
  icon: React.ComponentType<{ className?: string }>
  sendAction: (msg: PanelMessage) => void
  disabled: boolean
}

export function QuickActionButton({
  action,
  label,
  icon: Icon,
  sendAction,
  disabled,
}: QuickActionButtonProps) {
  const [loading, setLoading] = useState(false)

  const handleClick = useCallback(() => {
    if (disabled || loading) return
    setLoading(true)
    sendAction({ type: 'quick_action', action })
  }, [disabled, loading, sendAction, action])

  useEffect(() => {
    if (!loading) return
    const timer = setTimeout(() => setLoading(false), 5000)
    return () => clearTimeout(timer)
  }, [loading])

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={disabled || loading}
      className="flex items-center gap-2 px-3 py-2 text-xs rounded-lg transition-colors bg-zinc-800 text-zinc-300 hover:bg-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {loading ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
      ) : (
        <Icon className="w-3.5 h-3.5" />
      )}
      {label}
    </button>
  )
}
