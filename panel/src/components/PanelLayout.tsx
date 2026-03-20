import { useMeetingStore } from '../stores/meetingStore.ts'
import { ConnectionStatus } from './ConnectionStatus.tsx'
import { CollapsibleSection } from './ui/CollapsibleSection.tsx'
import { TaskFeed } from './TaskFeed.tsx'
import { CompletedItems } from './CompletedItems.tsx'
import { DecisionLog } from './DecisionLog.tsx'
import { AgentStatusGrid } from './AgentStatusGrid.tsx'

interface PanelLayoutProps {
  zoomStatus: 'connecting' | 'connected' | 'error' | 'standalone'
  engineConnected: boolean
  engineConnecting: boolean
}

export function PanelLayout({
  zoomStatus,
  engineConnected,
  engineConnecting,
}: PanelLayoutProps) {
  const meetingState = useMeetingStore((s) => s.state)

  const activeTasks = meetingState.tasks.filter((t) => t.status !== 'completed')
  const completedTasks = meetingState.tasks.filter(
    (t) => t.status === 'completed',
  )
  const decisions: { id: string; text: string; timestamp: string }[] = []

  return (
    <div className="h-screen flex flex-col bg-zinc-950 text-zinc-100">
      <header className="flex-shrink-0 px-3 py-2 border-b border-zinc-800">
        <ConnectionStatus
          zoomStatus={zoomStatus}
          engineConnected={engineConnected}
          engineConnecting={engineConnecting}
        />
      </header>

      <main className="flex-1 overflow-y-auto">
        <CollapsibleSection
          title="Active Tasks"
          count={activeTasks.length}
          defaultOpen
        >
          <TaskFeed tasks={meetingState.tasks} />
        </CollapsibleSection>

        <CollapsibleSection
          title="Completed"
          count={completedTasks.length}
          defaultOpen={false}
        >
          <CompletedItems tasks={meetingState.tasks} />
        </CollapsibleSection>

        <CollapsibleSection
          title="Decisions"
          count={decisions.length}
          defaultOpen={false}
        >
          <DecisionLog decisions={decisions} />
        </CollapsibleSection>

        <CollapsibleSection title="Agents" defaultOpen>
          <AgentStatusGrid agents={meetingState.agents} />
        </CollapsibleSection>
      </main>

      {/* QuickActions added in Plan 03 */}
    </div>
  )
}
