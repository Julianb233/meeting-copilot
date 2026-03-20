/**
 * TypeScript types matching engine Pydantic models (engine/models.py).
 * Keep in sync with Python definitions.
 */

// --- Enums ---

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed'

export type QuickActionType =
  | 'create_issue'
  | 'draft_email'
  | 'research'
  | 'delegate'
  | 'check_domain'

// --- Meeting State ---

export interface MeetingTask {
  id: string
  title: string
  status: TaskStatus
  agent: string | null
  created_at: string
  completed_at: string | null
  result: string | null
  error: string | null
}

export interface AgentStatus {
  name: string
  status: string
  current_task: string | null
}

export interface MeetingContext {
  meeting_id: string | null
  title: string | null
  attendees: string[]
  started_at: string | null
}

export interface MeetingState {
  active: boolean
  context: MeetingContext
  tasks: MeetingTask[]
  intents: Record<string, unknown>[]
  transcript_chunks: Record<string, unknown>[]
  agents: AgentStatus[]
}

// --- Panel -> Engine Messages ---

export type PanelMessage =
  | { type: 'ping' }
  | { type: 'quick_action'; action: QuickActionType; payload?: Record<string, unknown> }

// --- Engine -> Panel Messages ---

export type EngineMessage =
  | { type: 'connection_ack'; meeting_state: MeetingState }
  | { type: 'pong' }
  | { type: 'meeting_started'; context: MeetingContext }
  | { type: 'task_dispatched'; task: MeetingTask }
  | { type: 'task_completed'; task_id: string; result: string }
  | { type: 'task_failed'; task_id: string; error: string }
  | { type: 'agent_status'; agents: AgentStatus[] }
  | { type: 'transcript_chunk'; text: string; speaker: string; timestamp: number }
  | { type: 'meeting_ended'; summary: Record<string, unknown> }
