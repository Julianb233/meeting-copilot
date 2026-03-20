# Phase 4: Zoom Companion Panel UI - Research

**Researched:** 2026-03-20
**Domain:** Zoom Apps SDK, React sidebar UI, Zoom OAuth, iframe constraints
**Confidence:** MEDIUM (Zoom docs are authoritative but scattered; some details verified only via forum posts)

## Summary

Phase 4 builds a React sidebar app that runs inside the Zoom client as a Meeting Side Panel. The existing codebase (panel/) already has Vite + React 19 + Tailwind v4 + Zoom Apps SDK v0.16.37 + Zustand + react-use-websocket scaffolded, with a working App.tsx that initializes the Zoom SDK and renders task/agent status sections. The WebSocket hook and message types are already wired.

The primary work remaining is: (1) registering the app on Zoom Marketplace as a General App with Zoom Apps SDK feature enabled, (2) handling authentication (SDK-only approach preferred -- see Open Questions), (3) building out the UI components for the constrained sidebar width, (4) adding quick action buttons that send commands via the existing WebSocket, and (5) deploying to Vercel with required OWASP security headers.

**Critical correction from prior research:** In-client OAuth (`zoomSdk.authorize()`) is NOT available for unpublished/development apps. The official docs state: "The in-client app flow to add an app is not available for unpublished apps." For a private single-user app, use the traditional OAuth redirect flow via the Marketplace "Local Test" page, OR skip OAuth entirely and rely on SDK-only capabilities (which work without tokens for basic meeting context).

**Primary recommendation:** Create a General App (user-managed) on Zoom Marketplace with Zoom Apps SDK enabled. Start with SDK-only capabilities (no OAuth token exchange needed) since the panel's data comes from the engine via WebSocket, not from Zoom REST APIs. Deploy to Vercel with the 4 required OWASP headers in vercel.json. The app stays in development/private mode. Build all UI for a minimum ~280px width with fluid scaling.

## Standard Stack

### Core (Already Installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| @zoom/appssdk | ^0.16.37 | Zoom client <-> iframe bridge | Official Zoom SDK, already installed |
| react | ^19.2.4 | UI framework | Already scaffolded |
| react-dom | ^19.2.4 | DOM rendering | Already scaffolded |
| tailwindcss | ^4.2.2 | Styling | Already scaffolded, ideal for constrained UIs |
| zustand | ^5.0.12 | State management | Already scaffolded, lightweight |
| react-use-websocket | ^4.13.0 | WebSocket client | Already scaffolded with auto-reconnect |
| lucide-react | ^0.577.0 | Icons | Already installed, tree-shakeable |
| vite | ^8.0.1 | Build tool | Already scaffolded |

### Supporting (No New Dependencies Needed)
The existing stack covers all requirements. No additional libraries are needed.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Zustand | React Context | Zustand already installed, better for WebSocket-driven updates |
| Tailwind | CSS Modules | Tailwind already configured, better for rapid constrained-width UI |
| lucide-react | heroicons | lucide already installed, same quality |

**Installation:**
```bash
# No new packages needed - stack is complete from Phase 1
cd panel && npm install  # verify existing deps
```

## Architecture Patterns

### Recommended Project Structure
```
panel/src/
├── App.tsx                    # Root: Zoom init + layout router (exists, needs refactor)
├── main.tsx                   # Entry point (exists)
├── index.css                  # Tailwind imports (exists)
├── components/
│   ├── PanelLayout.tsx        # NEW: Full panel layout with header/main/footer
│   ├── TaskFeed.tsx           # NEW: PNL-01 live task list with status badges
│   ├── TaskItem.tsx           # NEW: Individual task with status indicator
│   ├── CompletedItems.tsx     # NEW: PNL-02 completed tasks section
│   ├── DecisionLog.tsx        # NEW: PNL-03 decisions & notes log
│   ├── AgentStatusGrid.tsx    # NEW: PNL-04 agent status indicators
│   ├── QuickActions.tsx       # NEW: PNL-05/ORC-03 action button bar
│   ├── QuickActionButton.tsx  # NEW: Individual action button with loading state
│   ├── ConnectionStatus.tsx   # NEW: Zoom + Engine connection indicators (extract from App.tsx)
│   └── ui/
│       ├── StatusBadge.tsx    # NEW: Reusable status badge
│       └── CollapsibleSection.tsx  # NEW: Collapsible accordion section
├── hooks/
│   ├── useEngine.ts           # WebSocket connection (exists)
│   └── useZoomContext.ts      # NEW: Extract Zoom SDK init from App.tsx
├── stores/
│   └── meetingStore.ts        # Zustand store (exists)
├── types/
│   └── messages.ts            # TypeScript message types (exists)
└── vite-env.d.ts
```

### Pattern 1: Collapsible Sections for Narrow Sidebar
**What:** Each panel section (Tasks, Completed, Agents, etc.) is a collapsible accordion to maximize usable space in the ~280-320px sidebar.
**When to use:** Always in sidebar mode; sections expand/collapse independently.
**Example:**
```typescript
function CollapsibleSection({ title, count, children, defaultOpen = true }: Props) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border-b border-zinc-800">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-2 text-sm font-medium text-zinc-300 hover:bg-zinc-800/50"
      >
        <span>{title}</span>
        <span className="flex items-center gap-2">
          {count !== undefined && count > 0 && (
            <span className="bg-zinc-700 text-zinc-300 text-xs px-1.5 py-0.5 rounded-full">{count}</span>
          )}
          <ChevronDown className={`w-4 h-4 transition-transform ${open ? 'rotate-180' : ''}`} />
        </span>
      </button>
      {open && <div className="px-3 pb-3">{children}</div>}
    </div>
  )
}
```

### Pattern 2: Status Badge System
**What:** Consistent color-coded status indicators across tasks and agents.
**When to use:** Every task and agent status display.
**Example:**
```typescript
const STATUS_CONFIG: Record<TaskStatus, { color: string; label: string }> = {
  pending:   { color: 'bg-zinc-500',              label: 'Pending' },
  running:   { color: 'bg-blue-500 animate-pulse', label: 'Running' },
  completed: { color: 'bg-green-500',             label: 'Done' },
  failed:    { color: 'bg-red-500',               label: 'Failed' },
}

function StatusBadge({ status }: { status: TaskStatus }) {
  const config = STATUS_CONFIG[status]
  return (
    <span className="flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full ${config.color}`} />
      <span className="text-xs text-zinc-400">{config.label}</span>
    </span>
  )
}
```

### Pattern 3: Quick Action Dispatch via Existing WebSocket
**What:** Quick action buttons send typed messages through the already-wired sendAction from useEngine.
**When to use:** All quick action buttons (PNL-05/ORC-03).
**Example:**
```typescript
function QuickActions() {
  const { sendAction, connected } = useEngine()
  const actions: { type: QuickActionType; label: string; icon: LucideIcon }[] = [
    { type: 'delegate',      label: 'Delegate Task',    icon: Users },
    { type: 'create_issue',  label: 'Create Proposal',  icon: FileText },
    { type: 'research',      label: 'Research This',     icon: Search },
    { type: 'draft_email',   label: 'Draft Email',      icon: Mail },
    { type: 'check_domain',  label: 'Check Domain',     icon: Globe },
  ]
  return (
    <div className="grid grid-cols-2 gap-2">
      {actions.map((a) => (
        <button
          key={a.type}
          onClick={() => sendAction({ type: 'quick_action', action: a.type })}
          disabled={!connected}
          className="flex items-center gap-2 px-3 py-2 text-xs text-zinc-300 bg-zinc-800 hover:bg-zinc-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <a.icon className="w-3.5 h-3.5" />
          {a.label}
        </button>
      ))}
    </div>
  )
}
```

### Pattern 4: Responsive Sidebar Layout
**What:** Full-height flex layout with fixed header/footer and scrollable main area.
**When to use:** Root panel layout.
**Example:**
```typescript
function PanelLayout() {
  const meetingState = useMeetingStore((s) => s.state)
  const activeTasks = meetingState.tasks.filter(t => t.status !== 'completed')
  const completedTasks = meetingState.tasks.filter(t => t.status === 'completed')

  return (
    <div className="h-screen flex flex-col bg-zinc-950 text-zinc-100">
      <header className="flex-shrink-0 px-3 py-2 border-b border-zinc-800">
        <ConnectionStatus />
      </header>

      <main className="flex-1 overflow-y-auto">
        <CollapsibleSection title="Active Tasks" count={activeTasks.length} defaultOpen>
          <TaskFeed tasks={activeTasks} />
        </CollapsibleSection>
        <CollapsibleSection title="Completed" count={completedTasks.length} defaultOpen={false}>
          <CompletedItems tasks={completedTasks} />
        </CollapsibleSection>
        <CollapsibleSection title="Agents" count={meetingState.agents.length} defaultOpen>
          <AgentStatusGrid agents={meetingState.agents} />
        </CollapsibleSection>
      </main>

      <footer className="flex-shrink-0 px-3 py-2 border-t border-zinc-800">
        <QuickActions />
      </footer>
    </div>
  )
}
```

### Anti-Patterns to Avoid
- **Fixed pixel widths:** The sidebar width varies by OS and user resizing. Use `w-full` and relative sizing, never `w-[320px]`.
- **Heavy scroll areas:** Avoid deeply nested scroll containers. Use one main scrollable area with collapsible sections.
- **Storing auth tokens in localStorage:** Zoom's embedded browser clears localStorage when the app closes. Use server-side session storage if OAuth is needed.
- **In-client OAuth for unpublished apps:** `zoomSdk.authorize()` does NOT work for development/unpublished apps. Use traditional OAuth redirect or SDK-only approach.
- **Blocking the main thread:** All WebSocket handling and Zoom SDK calls are async. Never block on these.
- **Calling SDK methods before config():** `zoomSdk.config()` must be the FIRST SDK call. It establishes the communication channel.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WebSocket connection | Custom WebSocket manager | react-use-websocket (already installed) | Handles reconnect, heartbeat, state |
| Zoom SDK communication | Direct postMessage to parent | @zoom/appssdk | Required protocol, handles iframe bridging |
| OAuth token exchange | Custom token handling in frontend | Backend proxy endpoint (if needed) | Tokens must never be in frontend code |
| Status badge colors | Per-component color logic | Centralized STATUS_CONFIG map | Consistency across all components |
| Scrollable containers | Custom scroll handling | CSS overflow-y-auto with Tailwind | Native scrolling works fine in Zoom's embedded browser |
| PKCE generation | Custom base64 utils | Web Crypto API (built-in) | Browser-native, secure, no dependencies |

**Key insight:** The existing codebase already has the hard parts (WebSocket, Zustand store, Zoom SDK init, message types). Phase 4 is primarily UI component work + Zoom app registration configuration.

## Common Pitfalls

### Pitfall 1: Missing OWASP Headers Blocks App Rendering
**What goes wrong:** The Zoom embedded browser silently refuses to render the app, showing a blank panel.
**Why it happens:** Zoom requires 4 OWASP security headers on ALL HTML responses with 200 status. Missing any one blocks rendering entirely.
**How to avoid:** Configure these headers in vercel.json for all routes:
```json
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "Strict-Transport-Security", "value": "max-age=63072000; includeSubDomains" },
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "Referrer-Policy", "value": "same-origin" },
        {
          "key": "Content-Security-Policy",
          "value": "default-src 'self'; script-src 'self' 'unsafe-inline' https://appssdk.zoom.us; style-src 'self' 'unsafe-inline'; connect-src 'self' wss://ENGINE_DOMAIN https://api.zoom.us; img-src 'self' data:; font-src 'self' data:; frame-ancestors 'self'"
        }
      ]
    }
  ]
}
```
**Warning signs:** Blank white panel in Zoom, console error "Missing OWASP Secure Headers".

### Pitfall 2: In-Client OAuth NOT Available for Unpublished Apps
**What goes wrong:** Calling `zoomSdk.authorize()` fails or shows no consent screen.
**Why it happens:** Zoom restricts in-client OAuth to published/beta apps. Official docs: "The in-client app flow to add an app is not available for unpublished apps."
**How to avoid:** For a private app used by one account:
1. Use the Zoom Marketplace "Local Test" page to add the app to Julian's account
2. If Zoom REST API access is needed, implement traditional OAuth via a backend redirect endpoint
3. If only SDK capabilities are needed (getMeetingContext, etc.), skip OAuth entirely -- config() works without tokens
**Warning signs:** `authorize()` throws an error or hangs indefinitely.

### Pitfall 3: localStorage/Cookies Cleared on App Close
**What goes wrong:** User state, tokens, or preferences disappear when the Zoom app panel is closed and reopened.
**Why it happens:** Zoom's embedded browser clears cookies and localStorage when the app closes.
**How to avoid:** Store all persistent data server-side. Use the Zoom user_id (from getUserContext) as the key to restore state on app reopen.
**Warning signs:** Users have to re-authenticate every time they open the panel.

### Pitfall 4: CSP Must Match Domain Allow List in Marketplace
**What goes wrong:** Resources (scripts, WebSocket connections, fonts) are blocked in the Zoom embedded browser.
**Why it happens:** The CSP headers in your response AND the Domain Allow List configured in Zoom Marketplace must BOTH permit the same domains. They must mirror each other.
**How to avoid:** Mirror every domain in your CSP in the Marketplace Domain Allow List configuration. Include: your Vercel domain, the engine WebSocket domain, `appssdk.zoom.us`.
**Warning signs:** Console errors about blocked resources, WebSocket connects in standalone browser but fails inside Zoom.

### Pitfall 5: expandApp() Only Works In Meeting
**What goes wrong:** Calling expandApp() outside a meeting context throws an error.
**Why it happens:** The API is meeting-context-only.
**How to avoid:** Check `getRunningContext()` result before calling meeting-specific APIs. Only offer expand/meeting features when `runningContext === 'inMeeting'`.
**Warning signs:** Runtime error when testing in standalone mode or main client context.

### Pitfall 6: config() Must Be Called First
**What goes wrong:** SDK API calls fail with cryptic errors or timeouts.
**Why it happens:** `zoomSdk.config()` must be the FIRST SDK call. It establishes the communication channel between iframe and Zoom client.
**How to avoid:** Already handled in App.tsx -- ensure no other SDK calls happen before config() resolves.
**Warning signs:** "SDK not configured" or timeout errors.

## Code Examples

### vercel.json with Required OWASP Headers
```json
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "Strict-Transport-Security", "value": "max-age=63072000; includeSubDomains" },
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "Referrer-Policy", "value": "same-origin" },
        {
          "key": "Content-Security-Policy",
          "value": "default-src 'self'; script-src 'self' 'unsafe-inline' https://appssdk.zoom.us; style-src 'self' 'unsafe-inline'; connect-src 'self' wss://ENGINE_DOMAIN https://api.zoom.us; img-src 'self' data:; font-src 'self' data:; frame-ancestors 'self'"
        }
      ]
    }
  ]
}
```
Note: Replace `ENGINE_DOMAIN` with actual VPS domain. The CSP domains MUST also be added to the Zoom Marketplace Domain Allow List.

### Zoom SDK Initialization with Context Check
```typescript
// Source: existing panel/src/App.tsx + Zoom Apps SDK docs
import zoomSdk from '@zoom/appssdk'

async function initZoom() {
  try {
    const configResponse = await zoomSdk.config({
      capabilities: [
        'getMeetingContext',
        'getUserContext',
        'getRunningContext',
        'expandApp',
        'onMeeting',
        'openUrl',
      ],
    })
    console.log('Zoom SDK configured:', configResponse)

    // Check running context before calling meeting-specific APIs
    const runCtx = await zoomSdk.getRunningContext()
    if (runCtx.context === 'inMeeting') {
      const meetingCtx = await zoomSdk.getMeetingContext()
      // meetingCtx has: meetingTopic, meetingID
    }

    return { status: 'connected' as const, configResponse }
  } catch (err) {
    console.log('Not running inside Zoom, standalone mode:', err)
    return { status: 'standalone' as const }
  }
}
```

### Quick Action Button with Loading State
```typescript
function QuickActionButton({ action, label, icon: Icon }: QuickActionButtonProps) {
  const { sendAction, connected } = useEngine()
  const [loading, setLoading] = useState(false)

  const handleClick = () => {
    if (!connected) return
    setLoading(true)
    sendAction({ type: 'quick_action', action })
    setTimeout(() => setLoading(false), 5000) // fallback timeout
  }

  return (
    <button
      onClick={handleClick}
      disabled={!connected || loading}
      className="flex items-center gap-2 px-3 py-2 text-xs rounded-lg transition-colors
        bg-zinc-800 text-zinc-300 hover:bg-zinc-700
        disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Icon className="w-3.5 h-3.5" />}
      {label}
    </button>
  )
}
```

## Zoom App Registration Guide

### Step-by-Step for Private Meeting Side Panel App

1. **Go to** https://marketplace.zoom.us/ > Develop > Build App
2. **Select** "General App" > Create
3. **Basic Info:**
   - App name: "Meeting Copilot"
   - Management type: **User-managed** (enables Zoom Apps SDK, In-Client OAuth, Guest Mode)
4. **OAuth Configuration:**
   - Redirect URL: `https://your-vercel-domain.vercel.app/api/zoomapp/auth` (only needed if using OAuth)
   - OAuth Allow List: `https://your-vercel-domain.vercel.app`
5. **Select Features:**
   - Product: **Meetings**
   - Enable: **Zoom Apps SDK** feature (this makes it a side panel app)
   - Client support: Desktop
6. **Scopes:**
   - `zoomapp:inmeeting` (required for in-meeting apps)
   - `user:read` (optional, for user context)
7. **Surface Configuration:**
   - Home URL: `https://your-vercel-domain.vercel.app`
   - Domain Allow List: your Vercel domain, `appssdk.zoom.us`, your engine WebSocket domain
8. **Local Test:**
   - Use the "Local Test" page to add the app to Julian's account
   - No marketplace publishing required for private use

### Key Registration Notes
- The app stays in **development mode** -- no review needed for private use
- Only the developer's account can use it (perfect for Julian's single-account use case)
- The Home URL MUST return the 4 OWASP headers or the app will not render
- Domain Allow List must include every external domain the app connects to
- The Domain Allow List and your CSP headers must mirror each other

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| JWT apps | OAuth / Server-to-Server OAuth | Sept 2023 | JWT fully deprecated; must use OAuth |
| Separate Zoom App types | General App with selectable features | 2024 | Single app type, features selected during config |
| CDN-loaded SDK script tag | npm @zoom/appssdk | 2023+ | npm preferred, better TS support |
| Cookie-based sessions | Server-side sessions keyed by user_id | Ongoing | Zoom clears cookies; must use server storage |

**Deprecated/outdated:**
- JWT app type: Fully deprecated, cannot create new ones
- Zoom Apps SDK via CDN script tag: Still works but npm package is standard
- In-client OAuth for unpublished apps: Was never available; use traditional OAuth or SDK-only

## Open Questions

1. **Do We Actually Need OAuth?**
   - What we know: The panel's data comes from the engine via WebSocket, NOT from Zoom REST APIs. The SDK `config()` call works for basic capabilities (getMeetingContext, getUserContext) without OAuth tokens. OAuth is only needed if the panel needs to call Zoom REST APIs directly (e.g., list participants, manage recordings).
   - What's unclear: Whether any planned feature requires Zoom REST API access.
   - Recommendation: **Start without OAuth.** Use SDK-only capabilities. The panel gets meeting context from the SDK and everything else from the engine WebSocket. Add OAuth later only if a specific Zoom API call is needed. This eliminates the need for a backend token exchange endpoint and simplifies deployment significantly (pure SPA on Vercel).

2. **Exact Sidebar Dimensions**
   - What we know: Collapsed view is approximately 280-320px. Users can drag to resize via a handlebar. There are collapsed, expanded, and pop-out modes. No fixed documented dimensions.
   - What's unclear: Exact minimum width across OS platforms.
   - Recommendation: Design for 280px minimum width. Use fluid layout (no fixed widths). Test on macOS Zoom client.

3. **Vercel Domain for Home URL**
   - What we know: The panel is configured for Vercel deployment. Vercel provides automatic HTTPS (required by Zoom).
   - What's unclear: The exact Vercel project/domain isn't set up yet.
   - Recommendation: Deploy to Vercel first with a temporary `.vercel.app` domain, configure Zoom Marketplace with that domain. Can switch to custom domain later. Marketplace config can be updated at any time.

4. **Development Testing Without Zoom**
   - What we know: The panel already has standalone mode (catches SDK init failure gracefully).
   - What's unclear: How to test the full Zoom integration loop locally.
   - Recommendation: Keep standalone mode for UI development. For Zoom integration testing, use ngrok to tunnel localhost to HTTPS, configure that as Home URL temporarily. Only final testing needs actual Vercel deployment.

## Sources

### Primary (HIGH confidence)
- [Zoom Apps Authentication](https://developers.zoom.us/docs/zoom-apps/authentication/) - OAuth flow details, critical note about unpublished apps
- [Zoom Apps OWASP Headers](https://developers.zoom.us/docs/zoom-apps/security/owasp/) - Required 4 security headers
- [Zoom Platform Key Concepts](https://developers.zoom.us/docs/platform/key-concepts/) - App types: private, beta, published, unlisted
- [Create a Zoom App](https://developers.zoom.us/docs/zoom-apps/create/) - Registration workflow
- [Select General App Features](https://developers.zoom.us/docs/build-flow/create-oauth-apps/) - Feature selection, management types
- [Zoom Apps Components & Capabilities](https://developers.zoom.us/docs/zoom-apps/design/components-and-capabilities/) - Side panel modes (collapsed, expanded, pop-out)
- [Zoom Apps SDK API Reference](https://appssdk.zoom.us/types/ZoomSdkTypes.Apis.html) - Full API list

### Secondary (MEDIUM confidence)
- [Zoom Apps Advanced React Sample](https://github.com/zoom/zoomapps-advancedsample-react) - Reference architecture with OAuth, Express backend, Redis sessions
- [Zoom CSP Forum Discussion](https://devforum.zoom.us/t/what-is-an-appropiate-content-security-policy-csp-for-embedding-an-application-on-the-zoom-client/73158) - Recommended CSP values
- [Side Panel Width Forum](https://devforum.zoom.us/t/zoom-right-panel-default-width/88837) - Width is variable by OS/display
- [Side Panel Resize Forum](https://devforum.zoom.us/t/is-there-a-way-to-resize-the-zoom-app-side-panel-for-the-user-using-code-or-setting/87267) - ~320px collapsed, no programmatic resize API

### Tertiary (LOW confidence)
- [Cookies Cleared Forum](https://devforum.zoom.us/t/cookies-and-localstorage-gets-clear-after-closing-app/109516) - localStorage/cookies cleared on app close (forum report)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - verified from existing package.json and node_modules, no new deps needed
- Architecture patterns: MEDIUM - patterns derived from Zoom sample apps + React best practices; sidebar dimensions approximate
- Zoom registration: MEDIUM - official docs cover General App creation; Meeting Side Panel is enabled via "Zoom Apps SDK" feature selection
- OWASP headers: HIGH - officially documented, app will not render without all 4 headers
- OAuth flow: HIGH - official docs confirm in-client OAuth unavailable for unpublished apps
- Side panel constraints: MEDIUM - combination of official docs (variable width, handlebar resize) and forum reports (~280-320px collapsed)
- Pitfalls: MEDIUM - combination of official docs and developer forum reports

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (Zoom SDK stable, no major changes expected in 30 days)
