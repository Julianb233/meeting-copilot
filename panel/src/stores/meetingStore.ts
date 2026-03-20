import { create } from 'zustand'
import type { MeetingState, MeetingTask, AgentStatus, MeetingContext } from '../types/messages.ts'

interface MeetingStore {
  // State
  state: MeetingState
  connected: boolean
  engineUrl: string

  // Actions
  setConnected: (connected: boolean) => void
  setFullState: (state: MeetingState) => void
  setMeetingStarted: (context: MeetingContext) => void
  addTask: (task: MeetingTask) => void
  updateTaskCompleted: (taskId: string, result: string) => void
  updateTaskFailed: (taskId: string, error: string) => void
  setAgentStatus: (agents: AgentStatus[]) => void
}

const defaultState: MeetingState = {
  active: false,
  context: { meeting_id: null, title: null, attendees: [], started_at: null },
  tasks: [],
  intents: [],
  transcript_chunks: [],
  agents: [
    { name: 'agent1', status: 'idle', current_task: null },
    { name: 'agent2', status: 'idle', current_task: null },
    { name: 'agent3', status: 'idle', current_task: null },
    { name: 'agent4', status: 'idle', current_task: null },
  ],
}

export const useMeetingStore = create<MeetingStore>((set) => ({
  state: defaultState,
  connected: false,
  engineUrl: import.meta.env.VITE_ENGINE_WS_URL || 'ws://localhost:8900/ws',

  setConnected: (connected) => set({ connected }),

  setFullState: (state) => set({ state }),

  setMeetingStarted: (context) =>
    set((s) => ({ state: { ...s.state, active: true, context } })),

  addTask: (task) =>
    set((s) => ({ state: { ...s.state, tasks: [...s.state.tasks, task] } })),

  updateTaskCompleted: (taskId, result) =>
    set((s) => ({
      state: {
        ...s.state,
        tasks: s.state.tasks.map((t) =>
          t.id === taskId ? { ...t, status: 'completed' as const, result } : t
        ),
      },
    })),

  updateTaskFailed: (taskId, error) =>
    set((s) => ({
      state: {
        ...s.state,
        tasks: s.state.tasks.map((t) =>
          t.id === taskId ? { ...t, status: 'failed' as const, error } : t
        ),
      },
    })),

  setAgentStatus: (agents) =>
    set((s) => ({ state: { ...s.state, agents } })),
}))
