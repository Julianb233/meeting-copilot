import type { MeetingTask } from '../types/messages.ts'
import { StatusBadge } from './ui/StatusBadge.tsx'

export function TaskItem({ task }: { task: MeetingTask }) {
  return (
    <div className="p-2">
      <div className="flex items-center gap-2">
        <StatusBadge status={task.status} />
        <span className="text-sm text-zinc-300 truncate">{task.title}</span>
      </div>
      {task.result && (
        <p className="text-xs text-zinc-500 mt-0.5 ml-3.5">{task.result}</p>
      )}
      {task.error && (
        <p className="text-xs text-red-400 mt-0.5 ml-3.5">{task.error}</p>
      )}
    </div>
  )
}
