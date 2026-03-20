import { TaskItem } from './TaskItem.tsx'
import type { MeetingTask } from '../types/messages.ts'

export function CompletedItems({ tasks }: { tasks: MeetingTask[] }) {
  if (tasks.length === 0) {
    return <p className="text-sm text-zinc-500">No completed tasks yet</p>
  }

  const sorted = [...tasks].sort((a, b) => {
    if (!a.completed_at || !b.completed_at) return 0
    return b.completed_at.localeCompare(a.completed_at)
  })

  return (
    <div className="space-y-1">
      {sorted.map((task) => (
        <TaskItem key={task.id} task={task} />
      ))}
    </div>
  )
}
