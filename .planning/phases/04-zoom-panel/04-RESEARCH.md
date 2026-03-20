# Phase 4: Zoom Companion Panel UI - Research

**Researched:** 2026-03-20
**Domain:** Zoom Apps SDK, OAuth, iframe-embedded React app, WebSocket in Zoom
**Confidence:** MEDIUM-HIGH (SDK types verified from installed package, Zoom docs verified via official sources)

## Summary

Phase 4 involves registering a private Zoom App that renders as a Meeting Side Panel (iframe), implementing OAuth for authentication, and building a React UI inside the Zoom sidebar that connects to the engine via WebSocket for real-time updates.

The Zoom Apps SDK (`@zoom/appssdk` v0.16.37, already installed) provides the bridge between the iframe and the Zoom client. The app loads as a web page inside Zoom's embedded browser (Chromium-based), configured via a "Home URL" pointing to the Vercel-hosted panel. WebSocket connections ARE supported inside Zoom Apps but require explicit domain whitelisting and CSP `connect-src` configuration.

The panel is already scaffolded with SDK init, WebSocket hook, Zustand store, and basic UI. Phase 4 completes the Zoom Marketplace registration, implements in-client OAuth with PKCE, builds the full panel UI components, and wires up quick action buttons.

**Primary recommendation:** Register a private "General (OAuth)" app on Zoom Marketplace with `zoomapp:inmeeting` scope. Use in-client OAuth (`zoomSdk.authorize` + `onAuthorized` + PKCE) rather than redirect-based OAuth. Add the VPS WebSocket domain to both CSP `connect-src` and the Marketplace Domain Allow List.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| @zoom/appssdk | 0.16.37 | Zoom client <-> iframe bridge | Official Zoom SDK, already installed |
| react | 19.2.4 | UI framework | Already scaffolded |
| zustand | 5.0.12 | State management | Already scaffolded, lightweight |
| react-use-websocket | 4.13.0 | WebSocket client | Already scaffolded in useEngine hook |
| tailwindcss | 4.2.2 | Styling | Already scaffolded |
| lucide-react | 0.577.0 | Icons | Already installed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (none needed) | - | - | Stack is complete for this phase |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| react-use-websocket | native WebSocket | react-use-websocket handles reconnection, already integrated |
| zustand | jotai/redux | zustand already wired up, changing would break existing code |

**Installation:** No new packages needed. Stack is already installed.

## Architecture Patterns

### Zoom App Registration Flow (Marketplace)

The app is registered on marketplace.zoom.us as a **General (OAuth) App** with distribution OFF (private):

1. Go to marketplace.zoom.us > Develop > Build App > General App
2. Toggle distribution OFF (keeps app private, never published)
3. Set management type to "User-managed" (single user: Julian)
4. Configure OAuth:
   - Redirect URL: `https://<vercel-domain>/api/zoomapp/auth`
   - OAuth Allow List: same domain
5. Configure Features:
   - Home URL: `https://<vercel-domain>`
   - Domain Allow List: `<vercel-domain>`, `<vps-domain>` (for WebSocket), `appssdk.zoom.us`
6. Add Scopes: `zoomapp:inmeeting`
7. Use "Local Test" to install for Julian's account

### In-Client OAuth Flow (PKCE)

The Zoom Apps SDK supports **in-client OAuth** which avoids browser redirects. This is the correct pattern for a Zoom App:

```
1. App loads in Zoom iframe
2. zoomSdk.config() returns auth.status
3. If auth.status === 'unauthorized':
   a. Generate PKCE code_verifier + code_challenge
   b. Call zoomSdk.authorize({ codeChallenge, state })
   c. Listen for zoomSdk.onAuthorized(event)
   d. Event contains { code, redirectUri, result, state }
   e. Send `code` + `code_verifier` to backend
   f. Backend exchanges code for access_token via Zoom OAuth token endpoint
   g. Store token server-side (single user, can use file/env)
4. If auth.status === 'authorized': proceed normally
```

### Recommended Project Structure (Panel)
```
panel/src/
  App.tsx                  # Main app with Zoom SDK init (exists)
  main.tsx                 # Entry point (exists)
  index.css                # Tailwind imports (exists)
  hooks/
    useEngine.ts           # WebSocket connection (exists)
    useZoomAuth.ts         # NEW: in-client OAuth with PKCE
  stores/
    meetingStore.ts         # Zustand store (exists, needs expansion)
  components/
    TaskFeed.tsx            # NEW: PNL-01 live task feed with status badges
    CompletedItems.tsx      # NEW: PNL-02 completed items section
    DecisionsLog.tsx        # NEW: PNL-03 decisions & notes log
    AgentStatus.tsx         # NEW: PNL-04 agent status indicators
    QuickActions.tsx        # NEW: PNL-05/ORC-03 quick action buttons
    StatusBadge.tsx         # NEW: reusable status badge component
  types/
    messages.ts             # Shared types (exists, needs expansion)
  lib/
    pkce.ts                 # NEW: PKCE code_verifier/challenge generation
```

### Pattern 1: Zoom SDK Initialization with Auth Check
**What:** Initialize SDK, check auth status, trigger OAuth if needed
**When to use:** App startup (already partially implemented in App.tsx)
**Example:**
```typescript
// Source: @zoom/appssdk v0.16.37 sdk.d.ts type definitions
import zoomSdk from '@zoom/appssdk'

async function initZoom() {
  const configResponse = await zoomSdk.config({
    capabilities: [
      'getMeetingContext',
      'getUserContext',
      'onMeeting',
      'onMyUserContextChange',
      'onAuthorized',
      'authorize',
      'openUrl',
    ],
  })

  if (configResponse.auth.status === 'unauthorized') {
    // Trigger in-client OAuth
    const { codeVerifier, codeChallenge } = await generatePKCE()
    // Store codeVerifier for later exchange
    sessionStorage.setItem('pkce_verifier', codeVerifier)

    zoomSdk.onAuthorized(async (event) => {
      if (event.result) {
        // Send event.code + codeVerifier to backend for token exchange
        await fetch('/api/zoomapp/token', {
          method: 'POST',
          body: JSON.stringify({ code: event.code, codeVerifier }),
        })
      }
    })

    await zoomSdk.authorize({ codeChallenge, state: crypto.randomUUID() })
  }

  // Auth is good, get meeting context
  if (configResponse.runningContext === 'inMeeting') {
    const ctx = await zoomSdk.getMeetingContext()
    // ctx: { meetingTopic: string, meetingID: string }
  }
}
```

### Pattern 2: PKCE Code Challenge Generation
**What:** Generate cryptographically secure PKCE pair for OAuth
**When to use:** Before calling `zoomSdk.authorize()`
**Example:**
```typescript
// Source: OAuth 2.0 PKCE standard (RFC 7636)
export async function generatePKCE() {
  const array = new Uint8Array(32)
  crypto.getRandomValues(array)
  const codeVerifier = btoa(String.fromCharCode(...array))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '')

  const encoder = new TextEncoder()
  const data = encoder.encode(codeVerifier)
  const digest = await crypto.subtle.digest('SHA-256', data)
  const codeChallenge = btoa(String.fromCharCode(...new Uint8Array(digest)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '')

  return { codeVerifier, codeChallenge }
}
```

### Pattern 3: Quick Action Button Dispatch
**What:** Send quick action via WebSocket to engine, which spawns fleet agents
**When to use:** PNL-05/ORC-03 quick action buttons
**Example:**
```typescript
// Source: existing types/messages.ts PanelMessage type
const { sendAction } = useEngine()

function handleQuickAction(action: QuickActionType) {
  sendAction({
    type: 'quick_action',
    action,
    payload: {
      meeting_id: meetingState.context.meeting_id,
      // Additional context from current meeting
    },
  })
}
```

### Anti-Patterns to Avoid
- **Redirect-based OAuth in Zoom iframe:** Zoom Apps run in an embedded browser. Do NOT redirect to external OAuth pages. Use `zoomSdk.authorize()` for in-client OAuth.
- **Polling for updates:** Use the existing WebSocket connection, not REST polling.
- **localStorage for tokens:** Zoom's embedded browser may clear storage between sessions. Store tokens server-side (engine).
- **Ignoring runningContext:** Always check `configResponse.runningContext` before calling meeting-specific APIs. The app could be running in `inMainClient` (outside a meeting).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PKCE generation | Custom crypto utils | Web Crypto API (built-in) | Browser-native, secure, no dependencies |
| WebSocket reconnection | Custom retry logic | react-use-websocket (already installed) | Handles reconnect, heartbeat, ready state |
| State management | Context + useReducer | Zustand (already installed) | Already wired up, simpler API |
| Status badges | Custom CSS classes | Tailwind utility classes | Already using Tailwind, consistent design |
| OAuth token exchange | Custom fetch + parse | FastAPI endpoint on engine | Backend handles securely, stores tokens |

**Key insight:** The panel scaffold already has the hard infrastructure (WebSocket, Zustand, SDK init). Phase 4 is about completing the Marketplace registration, adding OAuth, building UI components, and wiring quick actions -- not building new infrastructure.

## Common Pitfalls

### Pitfall 1: WebSocket blocked by Zoom CSP
**What goes wrong:** WebSocket connection to VPS fails silently or with CSP error inside Zoom
**Why it happens:** Zoom's embedded browser enforces CSP. The WebSocket domain must be in BOTH the app's Domain Allow List (Marketplace config) AND the page's CSP `connect-src` header.
**How to avoid:**
1. Add VPS domain (e.g., `vps.example.com`) to Marketplace Domain Allow List
2. Serve panel with CSP header: `connect-src 'self' wss://vps.example.com:8900`
3. Add `appssdk.zoom.us` to Domain Allow List (required for SDK)
**Warning signs:** WebSocket connects fine in standalone browser but fails in Zoom

### Pitfall 2: OAuth Redirect URL Mismatch
**What goes wrong:** OAuth flow fails with "redirect_uri mismatch" error
**Why it happens:** Zoom strictly validates redirect URLs. Development vs production URLs differ.
**How to avoid:**
1. Configure BOTH development and production redirect URLs in Marketplace
2. Use environment-specific Vercel URLs
3. If using ngrok for dev, update Marketplace config whenever ngrok URL changes
**Warning signs:** OAuth works in one environment but not another

### Pitfall 3: getMeetingContext Fails Outside Meeting
**What goes wrong:** `zoomSdk.getMeetingContext()` throws when app opens from main client
**Why it happens:** This API is only available when `runningContext === 'inMeeting'`
**How to avoid:** Always check `configResponse.runningContext` before calling meeting-specific APIs
**Warning signs:** "API not available in this context" errors

### Pitfall 4: Zoom Embedded Browser Clears State
**What goes wrong:** Auth state lost when user closes and reopens the panel
**Why it happens:** Zoom's embedded Chromium may not persist localStorage/sessionStorage between panel opens
**How to avoid:** Store auth tokens server-side (engine). On panel open, verify auth status via `zoomSdk.config()` response.
**Warning signs:** User has to re-auth every time they open the panel

### Pitfall 5: Side Panel Size Constraints
**What goes wrong:** UI renders incorrectly or elements are cut off
**Why it happens:** Zoom side panel has fixed width (~340-480px). Designing for wider viewports breaks layout.
**How to avoid:** Design for 340px minimum width. Use single-column layout. Test in actual Zoom panel.
**Warning signs:** UI looks fine in browser but broken in Zoom

### Pitfall 6: config() Must Be Called First
**What goes wrong:** SDK API calls fail with cryptic errors
**Why it happens:** `zoomSdk.config()` must be the FIRST SDK call. It establishes the communication channel.
**How to avoid:** Already handled in App.tsx -- just ensure no other SDK calls happen before config resolves
**Warning signs:** "SDK not configured" or timeout errors

## Code Examples

### CSP Headers for Vercel (vercel.json)
```json
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "Content-Security-Policy",
          "value": "default-src 'self'; connect-src 'self' wss://ENGINE_DOMAIN:8900 https://ENGINE_DOMAIN:8900; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors https://*.zoom.us"
        },
        {
          "key": "Strict-Transport-Security",
          "value": "max-age=31536000; includeSubDomains"
        },
        {
          "key": "X-Content-Type-Options",
          "value": "nosniff"
        }
      ]
    }
  ]
}
```

### Backend Token Exchange Endpoint (FastAPI)
```python
# Source: Zoom OAuth documentation
# POST /api/zoomapp/token
@app.post("/api/zoomapp/token")
async def exchange_zoom_token(code: str, code_verifier: str):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://zoom.us/oauth/token",
            params={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "code_verifier": code_verifier,
            },
            auth=(CLIENT_ID, CLIENT_SECRET),
        )
    tokens = resp.json()
    # Store tokens server-side (single user, file or env is fine)
    save_tokens(tokens["access_token"], tokens["refresh_token"])
    return {"ok": True}
```

### Zoom Marketplace Configuration Checklist
```
App Type: General (OAuth)
Distribution: OFF (private)
Management: User-managed

OAuth:
  Redirect URL: https://<vercel-domain>/api/zoomapp/auth
  Allow List: https://<vercel-domain>

Features:
  Home URL: https://<vercel-domain>
  Domain Allow List:
    - <vercel-domain>
    - <vps-domain>  (for WebSocket)
    - appssdk.zoom.us

Scopes:
  - zoomapp:inmeeting

Local Test:
  - Add Julian's account for testing
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| JWT app type | General (OAuth) app type | 2023 | JWT deprecated, must use OAuth |
| Redirect-based OAuth | In-client OAuth (authorize + PKCE) | SDK 0.16+ | No external redirects, smoother UX |
| CDN SDK script tag | NPM @zoom/appssdk | v0.16+ | Better TypeScript support, tree-shaking |
| frame-ancestors * | frame-ancestors https://*.zoom.us | Security update | Must explicitly allow Zoom to frame your app |

**Deprecated/outdated:**
- JWT app type: Fully deprecated by Zoom. Use General (OAuth) app.
- `sendAppInvitation` event name changed to just `sendAppInvitation` (old: `onSendAppInvitation`)
- SDK version "0.14" is deprecated in favor of "0.16"

## Open Questions

1. **Vercel domain for Home URL**
   - What we know: The panel is configured for Vercel deployment. Vercel provides automatic HTTPS.
   - What's unclear: The exact Vercel domain isn't set up yet (Phase 6 handles deployment).
   - Recommendation: For development, use ngrok tunnel. For production, use Vercel custom domain or default `.vercel.app` domain. Marketplace config can be updated.

2. **Token storage strategy for single user**
   - What we know: Only Julian uses this app. Tokens need to survive engine restarts.
   - What's unclear: Whether to use a file, env var, or simple SQLite for token persistence.
   - Recommendation: Use a JSON file on the VPS (e.g., `~/.meeting-copilot/tokens.json`). Simple, no database needed for single user.

3. **Development testing without Zoom**
   - What we know: The panel already has standalone mode (catches SDK init failure).
   - What's unclear: How much of the OAuth flow can be tested outside Zoom.
   - Recommendation: Keep the standalone mode fallback. Mock the Zoom SDK in development. Test OAuth flow only in actual Zoom client via ngrok.

## Sources

### Primary (HIGH confidence)
- `@zoom/appssdk` v0.16.37 `sdk.d.ts` - Installed package, read directly. All type definitions, API signatures, and capability enums verified from source.
- [Zoom Apps SDK API Reference](https://appssdk.zoom.us/classes/ZoomSdk.ZoomSdk.html) - Official TypeDoc reference
- [Zoom Apps SDK GitHub](https://github.com/zoom/appssdk) - Source code and README

### Secondary (MEDIUM confidence)
- [Zoom Developer Docs - Create a Zoom App](https://developers.zoom.us/docs/zoom-apps/create/) - Marketplace registration steps
- [Zoom Developer Docs - Security Guidelines](https://developers.zoom.us/docs/zoom-apps/security/) - CSP, TLS, OWASP requirements
- [Zoom Developer Docs - Internal Apps](https://developers.zoom.us/docs/internal-apps/) - Private app configuration
- [Zoom Advanced React Sample](https://github.com/zoom/zoomapps-advancedsample-react) - Official reference implementation with OAuth, session management
- [Zoom Developer Forum - WebSocket in Zoom Apps](https://devforum.zoom.us/t/can-i-use-websocket-in-zoom-apps/84848) - Official confirmation WebSockets work with CSP config
- [Zoom Developer Forum - WebSocket Connection Fix](https://devforum.zoom.us/t/cannot-connect-to-websocket-in-zoom-app/102782) - Domain Allow List vs OAuth Allow List distinction

### Tertiary (LOW confidence)
- [ngrok + Zoom Apps blog](https://ngrok.com/blog/building-zoom-apps-with-ngrok) - Development tunnel setup (community source, verified pattern)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All packages already installed and verified from node_modules
- Zoom SDK API surface: HIGH - Read directly from installed sdk.d.ts type definitions
- Marketplace registration steps: MEDIUM - Verified from official docs but UI may have changed
- OAuth in-client flow: HIGH - API types verified from SDK, pattern confirmed in official sample app
- WebSocket in Zoom iframe: HIGH - Confirmed working by Zoom staff on dev forum, CSP config documented
- Side panel constraints: MEDIUM - Width constraints inferred from popout size constraints in SDK types + community reports
- CSP configuration: MEDIUM - Verified from forum discussions and security docs, exact headers may need testing

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (Zoom SDK is relatively stable, marketplace UI changes slowly)
