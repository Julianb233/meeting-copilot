import type { AgentStatus } from '../types/messages.ts'

export function AgentStatusGrid({ agents }: { agents: AgentStatus[] }) {
  return (
    <div className="grid grid-cols-2 gap-2">
      {agents.map((agent) => (
        <div key={agent.name} className="flex items-center gap-2">
          <span
            className={`inline-block w-2 h-2 rounded-full ${
              agent.status === 'idle'
                ? 'bg-zinc-600'
                : agent.status === 'busy'
                  ? 'bg-blue-500 animate-pulse'
                  : 'bg-yellow-500'
            }`}
          />
          <div className="min-w-0">
            <span className="text-sm text-zinc-300">{agent.name}</span>
            <span className="text-xs text-zinc-500 ml-1 truncate">
              {agent.current_task ?? agent.status}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}
