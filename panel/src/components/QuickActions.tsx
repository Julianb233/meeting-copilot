import { Users, FileText, Search, Mail, Globe } from 'lucide-react'
import { QuickActionButton } from './QuickActionButton.tsx'
import type { QuickActionType, PanelMessage } from '../types/messages.ts'

interface QuickAction {
  type: QuickActionType
  label: string
  icon: React.ComponentType<{ className?: string }>
}

const QUICK_ACTIONS: QuickAction[] = [
  { type: 'delegate', label: 'Delegate Task', icon: Users },
  { type: 'create_issue', label: 'Create Proposal', icon: FileText },
  { type: 'research', label: 'Research This', icon: Search },
  { type: 'draft_email', label: 'Draft Email', icon: Mail },
  { type: 'check_domain', label: 'Check Domain', icon: Globe },
]

interface QuickActionsProps {
  sendAction: (msg: PanelMessage) => void
  disabled: boolean
}

export function QuickActions({ sendAction, disabled }: QuickActionsProps) {
  return (
    <div className="grid grid-cols-2 gap-2">
      {QUICK_ACTIONS.map((qa) => (
        <QuickActionButton
          key={qa.type}
          action={qa.type}
          label={qa.label}
          icon={qa.icon}
          sendAction={sendAction}
          disabled={disabled}
        />
      ))}
    </div>
  )
}
