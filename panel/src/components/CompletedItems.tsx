import type { MeetingTask } from '../types/messages.ts'
import { TaskItem } from './TaskItem.tsx'

export function CompletedItems({ tasks }: { tasks: MeetingTask[] }) {
  const completed = tasks
    .filter((t) => t.status === 'completed')
    .sort((a, b) => {
      if (!a.completed_at || !b.completed_at) return 0
      return b.completed_at.localeCompare(a.completed_at)
    })

  if (completed.length === 0) {
    return <p className="text-sm text-zinc-500">No completed tasks yet</p>
  }

  return (
    <div className="space-y-1">
      {completed.map((task) => (
        <TaskItem key={task.id} task={task} />
      ))}
    </div>
  )
}
