---
phase: 1-project-scaffold-infrastructure
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - panel/package.json
  - panel/vite.config.ts
  - panel/tsconfig.json
  - panel/tsconfig.app.json
  - panel/tsconfig.node.json
  - panel/index.html
  - panel/src/main.tsx
  - panel/src/App.tsx
  - panel/src/app.css
  - panel/src/stores/meeting.ts
  - panel/src/hooks/useSocket.ts
  - panel/src/types/messages.ts
  - panel/src/types/meeting.ts
  - panel/src/vite-env.d.ts
  - panel/biome.json
autonomous: true

must_haves:
  truths:
    - "Panel dev server starts and renders a React component in the browser"
    - "Zoom Apps SDK is installed and importable"
    - "Tailwind CSS classes apply styling correctly"
    - "TypeScript compiles with zero errors"
    - "Zustand store initializes and holds meeting state shape"
  artifacts:
    - path: "panel/package.json"
      provides: "Panel dependency manifest"
      contains: "@zoom/appssdk"
    - path: "panel/vite.config.ts"
      provides: "Vite build configuration with Tailwind plugin"
      contains: "tailwindcss"
    - path: "panel/src/App.tsx"
      provides: "Root component with Zoom SDK initialization skeleton"
      contains: "zoomSdk"
    - path: "panel/src/stores/meeting.ts"
      provides: "Zustand store for meeting state"
      contains: "create"
    - path: "panel/src/types/messages.ts"
      provides: "WebSocket message type definitions"
      contains: "type.*Event"
    - path: "panel/src/types/meeting.ts"
      provides: "Meeting domain type definitions"
      contains: "interface.*Meeting"
  key_links:
    - from: "panel/src/App.tsx"
      to: "panel/src/stores/meeting.ts"
      via: "Zustand hook import"
      pattern: "useMeetingStore"
    - from: "panel/src/App.tsx"
      to: "@zoom/appssdk"
      via: "SDK import and config call"
      pattern: "zoomSdk"
---

<objective>
Scaffold the Zoom companion panel as a Vite + React 19 + TypeScript SPA with Zoom Apps SDK, Tailwind CSS, Zustand state management, and WebSocket message type definitions.

Purpose: Create the frontend project structure that will render inside Zoom's iframe sidebar. Vite is used instead of Next.js because the panel is a pure client-side SPA inside an iframe -- no SSR, no API routes, no middleware needed.

Output: A buildable, runnable Vite React app with all dependencies installed, type definitions for WebSocket messages and meeting domain, a Zustand store skeleton, and a root component that initializes the Zoom SDK.
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/research/STACK.md
@.planning/research/ARCHITECTURE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Scaffold Vite React 19 project with all dependencies</name>
  <files>
    panel/package.json
    panel/vite.config.ts
    panel/tsconfig.json
    panel/tsconfig.app.json
    panel/tsconfig.node.json
    panel/index.html
    panel/src/main.tsx
    panel/src/vite-env.d.ts
    panel/biome.json
  </files>
  <action>
    From the project root `/opt/agency-workspace/meeting-copilot/`:

    1. Scaffold with Vite:
       ```
       npm create vite@latest panel -- --template react-ts
       ```

    2. cd into `panel/` and install all dependencies:
       ```
       npm install @zoom/appssdk react-use-websocket zustand lucide-react
       npm install tailwindcss @tailwindcss/vite
       npm install -D @biomejs/biome vitest @testing-library/react @testing-library/jest-dom jsdom
       ```

    3. Update `vite.config.ts` to include the Tailwind plugin:
       ```typescript
       import { defineConfig } from 'vite'
       import react from '@vitejs/plugin-react'
       import tailwindcss from '@tailwindcss/vite'

       export default defineConfig({
         plugins: [react(), tailwindcss()],
         server: {
           port: 3000,
         },
         build: {
           outDir: 'dist',
           sourcemap: true,
         },
       })
       ```

    4. Replace the default CSS (src/index.css or src/app.css) with a Tailwind v4 import:
       ```css
       @import "tailwindcss";
       ```

    5. Initialize Biome config:
       ```
       npx @biomejs/biome init
       ```
       Then update biome.json to enable formatting and linting for TypeScript/React.

    6. Verify the scaffold builds:
       ```
       npm run build
       ```

    Do NOT install Socket.IO, Redux, Material UI, shadcn/ui, or Next.js. See STACK.md for rationale.
  </action>
  <verify>
    - `cd panel && npm run build` exits with code 0
    - `cd panel && npm run dev` starts dev server on port 3000 (kill after confirming)
    - `ls panel/node_modules/@zoom/appssdk` exists
    - `ls panel/node_modules/zustand` exists
    - `npx tsc --noEmit` exits with code 0
  </verify>
  <done>Vite React 19 project builds successfully with all dependencies installed. Dev server starts on port 3000.</done>
</task>

<task type="auto">
  <name>Task 2: Create type definitions, Zustand store, and Zoom SDK initialization</name>
  <files>
    panel/src/types/messages.ts
    panel/src/types/meeting.ts
    panel/src/stores/meeting.ts
    panel/src/hooks/useSocket.ts
    panel/src/App.tsx
    panel/src/app.css
  </files>
  <action>
    1. Create `panel/src/types/meeting.ts` with domain types matching the architecture's MeetingContext:
       ```typescript
       export type MeetingType = 'client' | 'internal' | 'prospect'
       export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed'
       export type AgentId = 'agent1' | 'agent2' | 'agent3' | 'agent4'
       export type AgentStatus = 'idle' | 'busy'

       export interface Attendee {
         name: string
         email: string
         company?: string
         role?: string
       }

       export interface MeetingTask {
         id: string
         title: string
         status: TaskStatus
         project?: string
         agentId?: AgentId
         createdAt: string
         completedAt?: string
         result?: string
       }

       export interface Decision {
         id: string
         text: string
         timestamp: string
       }

       export interface AgentInfo {
         id: AgentId
         status: AgentStatus
         currentTask?: string
       }

       export interface MeetingState {
         meetingId: string | null
         title: string
         meetingType: MeetingType | null
         attendees: Attendee[]
         tasks: MeetingTask[]
         completedTasks: MeetingTask[]
         decisions: Decision[]
         agents: AgentInfo[]
         connected: boolean
         contextLoaded: boolean
       }
       ```

    2. Create `panel/src/types/messages.ts` with WebSocket message types matching ARCHITECTURE.md protocol:
       ```typescript
       // Engine -> Panel events
       export type ServerEventType =
         | 'transcript.new'
         | 'task.created'
         | 'task.status'
         | 'agent.spawned'
         | 'agent.completed'
         | 'context.loaded'
         | 'decision.logged'
         | 'meeting.ended'

       // Panel -> Engine events
       export type ClientEventType =
         | 'action.delegate'
         | 'action.research'
         | 'action.email'
         | 'action.proposal'
         | 'action.domain'
         | 'action.custom'

       export interface ServerEvent {
         type: ServerEventType
         payload: Record<string, unknown>
         ts: string
         meeting_id: string
       }

       export interface ClientEvent {
         type: ClientEventType
         payload: Record<string, unknown>
         ts: string
       }
       ```

    3. Create `panel/src/stores/meeting.ts` with Zustand store:
       ```typescript
       import { create } from 'zustand'
       import type { MeetingState, MeetingTask, Decision, AgentInfo, Attendee, MeetingType } from '../types/meeting'

       interface MeetingStore extends MeetingState {
         // Actions
         setMeetingContext: (meetingId: string, title: string, meetingType: MeetingType, attendees: Attendee[]) => void
         addTask: (task: MeetingTask) => void
         updateTaskStatus: (taskId: string, status: MeetingTask['status'], result?: string) => void
         addDecision: (decision: Decision) => void
         updateAgent: (agent: AgentInfo) => void
         setConnected: (connected: boolean) => void
         reset: () => void
       }

       const initialState: MeetingState = {
         meetingId: null,
         title: '',
         meetingType: null,
         attendees: [],
         tasks: [],
         completedTasks: [],
         decisions: [],
         agents: [
           { id: 'agent1', status: 'idle' },
           { id: 'agent2', status: 'idle' },
           { id: 'agent3', status: 'idle' },
           { id: 'agent4', status: 'idle' },
         ],
         connected: false,
         contextLoaded: false,
       }

       export const useMeetingStore = create<MeetingStore>((set) => ({
         ...initialState,
         setMeetingContext: (meetingId, title, meetingType, attendees) =>
           set({ meetingId, title, meetingType, attendees, contextLoaded: true }),
         addTask: (task) =>
           set((state) => ({ tasks: [...state.tasks, task] })),
         updateTaskStatus: (taskId, status, result) =>
           set((state) => {
             const tasks = state.tasks.map((t) =>
               t.id === taskId ? { ...t, status, result, completedAt: status === 'completed' ? new Date().toISOString() : t.completedAt } : t
             )
             const completedTasks = tasks.filter((t) => t.status === 'completed')
             const activeTasks = tasks.filter((t) => t.status !== 'completed')
             return { tasks: activeTasks, completedTasks }
           }),
         addDecision: (decision) =>
           set((state) => ({ decisions: [...state.decisions, decision] })),
         updateAgent: (agent) =>
           set((state) => ({
             agents: state.agents.map((a) => (a.id === agent.id ? agent : a)),
           })),
         setConnected: (connected) => set({ connected }),
         reset: () => set(initialState),
       }))
       ```

    4. Create `panel/src/hooks/useSocket.ts` as a placeholder WebSocket hook skeleton:
       ```typescript
       // Placeholder — will be fully implemented in Phase 4 when panel connects to engine
       // Uses react-use-websocket library for reconnection, heartbeat, etc.
       export function useSocket(_url: string) {
         // TODO: Implement WebSocket connection with react-use-websocket
         // - Connect to engine WSS endpoint
         // - Dispatch incoming ServerEvents to Zustand store
         // - Expose sendMessage for ClientEvents
         return {
           connected: false,
           sendMessage: (_msg: string) => {},
         }
       }
       ```

    5. Update `panel/src/App.tsx` to initialize Zoom SDK and show a minimal panel shell:
       ```typescript
       import { useEffect, useState } from 'react'
       import zoomSdk from '@zoom/appssdk'
       import { useMeetingStore } from './stores/meeting'
       import './app.css'

       function App() {
         const [sdkReady, setSdkReady] = useState(false)
         const [sdkError, setSdkError] = useState<string | null>(null)
         const { connected, meetingId, title } = useMeetingStore()

         useEffect(() => {
           async function initZoomSdk() {
             try {
               const config = await zoomSdk.config({
                 capabilities: [
                   'getMeetingContext',
                   'getMeetingParticipants',
                   'onMeeting',
                 ],
               })
               console.log('[ZoomSDK] Configured:', config)
               setSdkReady(true)
             } catch (err) {
               // SDK fails outside Zoom — expected during development
               console.warn('[ZoomSDK] Not in Zoom context:', err)
               setSdkError('Not running inside Zoom')
               setSdkReady(true) // Allow dev mode to continue
             }
           }
           initZoomSdk()
         }, [])

         if (!sdkReady) {
           return (
             <div className="flex items-center justify-center h-screen bg-zinc-900 text-zinc-400">
               <p>Initializing...</p>
             </div>
           )
         }

         return (
           <div className="min-h-screen bg-zinc-900 text-zinc-100 p-4 font-sans">
             <header className="mb-4">
               <h1 className="text-lg font-semibold">Meeting Copilot</h1>
               {sdkError && (
                 <p className="text-xs text-amber-400 mt-1">Dev Mode: {sdkError}</p>
               )}
               <div className="flex items-center gap-2 mt-2 text-sm text-zinc-400">
                 <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-zinc-600'}`} />
                 <span>{connected ? 'Connected' : 'Disconnected'}</span>
               </div>
             </header>

             <main className="space-y-4">
               <section>
                 <h2 className="text-sm font-medium text-zinc-400 uppercase tracking-wide">Tasks</h2>
                 <p className="text-sm text-zinc-500 mt-2">No active tasks</p>
               </section>

               <section>
                 <h2 className="text-sm font-medium text-zinc-400 uppercase tracking-wide">Decisions</h2>
                 <p className="text-sm text-zinc-500 mt-2">No decisions logged</p>
               </section>

               <section>
                 <h2 className="text-sm font-medium text-zinc-400 uppercase tracking-wide">Agents</h2>
                 <p className="text-sm text-zinc-500 mt-2">All agents idle</p>
               </section>
             </main>
           </div>
         )
       }

       export default App
       ```

    6. Replace `panel/src/app.css` (or index.css, whichever the scaffold creates) with:
       ```css
       @import "tailwindcss";
       ```
       Remove any default Vite scaffold CSS files that aren't needed (App.css if separate from app.css, index.css if it exists).

    Ensure `main.tsx` imports the CSS file correctly (e.g., `import './app.css'`).
  </action>
  <verify>
    - `cd panel && npx tsc --noEmit` exits with code 0 (all types compile)
    - `cd panel && npm run build` exits with code 0
    - `grep -r "useMeetingStore" panel/src/` returns hits in App.tsx and stores/meeting.ts
    - `grep -r "zoomSdk" panel/src/` returns hits in App.tsx
    - `ls panel/src/types/messages.ts panel/src/types/meeting.ts panel/src/stores/meeting.ts panel/src/hooks/useSocket.ts` all exist
  </verify>
  <done>Panel has typed WebSocket message definitions, meeting domain types, a Zustand store with meeting state shape and actions, a Zoom SDK initialization flow in App.tsx, and Tailwind styling applied. Project builds with zero TypeScript errors.</done>
</task>

</tasks>

<verification>
- `cd panel && npm run build` produces `dist/` with no errors
- `cd panel && npx tsc --noEmit` passes with zero errors
- All type definition files exist and are importable
- Zustand store creates correctly (no runtime errors)
- Tailwind classes render (check build output includes Tailwind utilities)
- `@zoom/appssdk` is importable (present in node_modules)
</verification>

<success_criteria>
A complete Vite + React 19 + TypeScript panel project exists in `panel/` with:
1. All dependencies installed (Zoom SDK, Zustand, Tailwind, react-use-websocket, Lucide, Biome)
2. Type definitions for WebSocket messages and meeting domain
3. Zustand store with meeting state shape and all CRUD actions
4. Root App component with Zoom SDK init and dev-mode fallback
5. Tailwind CSS configured and applying styles
6. Zero TypeScript errors, zero build errors
</success_criteria>

<output>
After completion, create `.planning/phases/1-project-scaffold-infrastructure/1-01-SUMMARY.md`
</output>
