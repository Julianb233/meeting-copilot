import type { TaskStatus } from '../../types/messages.ts'

const statusConfig: Record<TaskStatus, { color: string; label: string }> = {
  pending: { color: 'bg-zinc-500', label: 'Pending' },
  running: { color: 'bg-blue-500 animate-pulse', label: 'Running' },
  completed: { color: 'bg-green-500', label: 'Done' },
  failed: { color: 'bg-red-500', label: 'Failed' },
}

export function StatusBadge({ status }: { status: TaskStatus }) {
  const { color, label } = statusConfig[status]

  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full ${color}`} />
      <span className="text-xs text-zinc-400">{label}</span>
    </span>
  )
}
