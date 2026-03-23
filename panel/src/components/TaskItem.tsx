import { StatusBadge } from './ui/StatusBadge.tsx'
import type { MeetingTask } from '../types/messages.ts'

export function TaskItem({ task }: { task: MeetingTask }) {
  return (
    <div className="flex items-start gap-2 p-2">
      <StatusBadge status={task.status} />
      <div className="min-w-0 flex-1">
        <p className="text-sm text-zinc-300 truncate">{task.title}</p>
        {task.result && (
          <p className="text-xs text-zinc-500 mt-0.5 truncate">{task.result}</p>
        )}
        {task.error && (
          <p className="text-xs text-red-400 mt-0.5 truncate">{task.error}</p>
        )}
      </div>
    </div>
  )
}
