import type { MeetingTask } from '../types/messages.ts'
import { TaskItem } from './TaskItem.tsx'

export function TaskFeed({ tasks }: { tasks: MeetingTask[] }) {
  const activeTasks = tasks.filter((t) => t.status !== 'completed')

  if (activeTasks.length === 0) {
    return <p className="text-sm text-zinc-500">No active tasks</p>
  }

  return (
    <div className="space-y-1">
      {activeTasks.map((task) => (
        <TaskItem key={task.id} task={task} />
      ))}
    </div>
  )
}
