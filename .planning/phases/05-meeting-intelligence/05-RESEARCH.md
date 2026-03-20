# Phase 5: Meeting Intelligence - Research

**Researched:** 2026-03-20
**Domain:** Meeting classification, prior context surfacing, post-meeting follow-up email generation
**Confidence:** HIGH

## Summary

Phase 5 adds three intelligence layers to the meeting copilot: (1) classify meetings as internal vs client based on attendee email domains, (2) surface prior meeting context ("Last time you discussed...") from existing Fireflies transcript data at meeting start, and (3) auto-draft and send follow-up emails with action items and decisions after meetings end.

The architecture is straightforward because all required data sources already exist. The context engine (Phase 2) already loads Fireflies transcripts with summaries, action items, and participant lists. The attendee identity resolver provides email addresses. The `gws` CLI handles email sending with OAuth. The meeting-watcher v2 already has a working follow-up email implementation that serves as a reference implementation to port into the copilot engine.

The primary integration challenge is fitting these three features into the existing assembler pipeline (models.py + assembler.py) without breaking the Phase 2/3 contracts, and hooking the post-meeting flow into either the WebSocket lifecycle or a REST endpoint that the meeting-watcher v2 bridge (Phase 6) can call.

**Primary recommendation:** Build a new `engine/intelligence/` module with `meeting_classifier.py` and `prior_context.py` that plug into the existing assembler pipeline. For follow-up emails, add a `engine/intelligence/followup_email.py` module that uses `asyncio.create_subprocess_exec` to call `gws gmail +send` (the new helper command, simpler than raw RFC 2822 encoding). Expose a POST `/api/meeting-ended` REST endpoint for triggering post-meeting flow.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | >=2.0 (installed) | MeetingType, PriorMeetingContext, FollowUpEmail models | Already used for all engine models |
| asyncio | stdlib | Subprocess calls to gws CLI for email | Already used throughout engine |
| httpx | >=0.28.0 (installed) | No new HTTP calls needed, but used by existing Fireflies client | Already in requirements.txt |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| litellm | >=1.0 (installed) | Generate context-aware follow-up email body via LLM | Upgrading raw template to LLM-drafted emails |
| enum | stdlib | MeetingType enum (INTERNAL/CLIENT/UNKNOWN) | Meeting classification |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `gws gmail +send` helper | `gws gmail users messages send` with raw RFC 2822 | +send handles encoding automatically; raw API requires base64url encoding of RFC 2822 message |
| LLM-drafted emails | Template-based (like meeting-watcher v2) | LLM drafts are context-aware (can adjust tone for internal vs client), but add latency and cost. Recommendation: LLM for client, template for internal |
| Python email.mime | gws CLI subprocess | gws already handles OAuth, MIME encoding. No benefit to raw SMTP |

**Installation:**
```bash
# No new dependencies needed -- all already in requirements.txt
```

## Architecture Patterns

### Recommended Project Structure
```
engine/
  intelligence/
    __init__.py                 # Package init
    meeting_classifier.py       # MeetingType enum, classify_meeting_type()
    prior_context.py            # PriorMeetingContext, extract_prior_context()
    followup_email.py           # FollowUpEmail model, draft_followup_email(), send_followup_email()
  context/
    models.py                   # EXTEND: add meeting_type, client_domains, prior_context fields
    assembler.py                # EXTEND: call classifier and prior_context after building attendees
  api.py                        # EXTEND: add POST /api/meeting-ended endpoint
```

### Pattern 1: Email Domain Classification
**What:** Classify meetings by extracting domains from attendee emails and checking against known internal domains.
**When to use:** Every time context is assembled for a new meeting.
**Example:**
```python
# Source: Codebase analysis of existing attendee patterns
from enum import Enum

class MeetingType(str, Enum):
    INTERNAL = "internal"
    CLIENT = "client"
    UNKNOWN = "unknown"

INTERNAL_DOMAINS = {"aiacrobatics.com"}
OWNER_EMAILS = {"julianb233@gmail.com", "julian@aiacrobatics.com"}

def classify_meeting_type(attendee_emails: list[str]) -> MeetingType:
    """Classify meeting based on attendee email domains.

    Rules:
    - Filter out owner emails (always present, should not count)
    - If no attendees remain: UNKNOWN (solo or no attendees)
    - If ALL remaining domains are internal: INTERNAL
    - If ANY remaining domain is external: CLIENT
    """
    others = [e for e in attendee_emails if e.lower() not in OWNER_EMAILS]
    if not others:
        return MeetingType.UNKNOWN

    domains = {e.lower().split("@")[1] for e in others if "@" in e}
    if not domains:
        return MeetingType.UNKNOWN

    if domains.issubset(INTERNAL_DOMAINS):
        return MeetingType.INTERNAL
    return MeetingType.CLIENT
```

### Pattern 2: Prior Context Extraction from Existing Fireflies Data
**What:** Extract topics and open action items from TranscriptSummary objects already loaded by Phase 2.
**When to use:** After assembling attendee contexts, before returning UnifiedMeetingContext.
**Example:**
```python
# Source: engine/context/fireflies.py TranscriptSummary model
def extract_prior_context(attendees: list[AttendeeContext]) -> PriorMeetingContext:
    """Extract prior meeting context from already-loaded Fireflies data.

    Deduplicates transcripts by ID (same meeting appears for multiple attendees).
    """
    seen_ids: set[str] = set()
    all_transcripts: list[TranscriptSummary] = []

    for att in attendees:
        for ts in att.meeting_history:
            if ts.id not in seen_ids:
                seen_ids.add(ts.id)
                all_transcripts.append(ts)

    # Sort by date descending
    all_transcripts.sort(key=lambda t: t.date or datetime.min, reverse=True)

    topics = [ts.summary[:120] for ts in all_transcripts if ts.summary]
    action_items = list(dict.fromkeys(  # dedupe preserving order
        item.strip()
        for ts in all_transcripts
        for item in ts.action_items
        if item.strip()
    ))

    return PriorMeetingContext(
        last_meeting_date=all_transcripts[0].date if all_transcripts else None,
        last_meeting_title=all_transcripts[0].title if all_transcripts else None,
        topics_discussed=topics,
        open_action_items=action_items,
        total_prior_meetings=len(all_transcripts),
    )
```

### Pattern 3: Follow-Up Email via gws CLI
**What:** Send follow-up emails using `gws gmail +send` helper which handles RFC 2822 encoding and OAuth automatically.
**When to use:** Post-meeting, triggered by meeting-ended event.
**Example:**
```python
# Source: Verified gws gmail +send --help output (2026-03-20)
import asyncio
import logging

logger = logging.getLogger(__name__)

async def send_email_via_gws(
    to: str,
    subject: str,
    body: str,
) -> bool:
    """Send email using gws gmail +send helper.

    Args:
        to: Recipient email address (single recipient per call)
        subject: Email subject line
        body: Plain text email body

    Returns True on success, False on failure.
    """
    proc = await asyncio.create_subprocess_exec(
        "gws", "gmail", "+send",
        "--to", to,
        "--subject", subject,
        "--body", body,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "HOME": "/home/agent4"},
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode == 0:
        logger.info("Email sent to %s: %s", to, subject)
        return True
    else:
        logger.error("Email send failed to %s: %s", to, stderr.decode())
        return False
```

### Pattern 4: LLM-Drafted Follow-Up Email (Client Meetings)
**What:** Use the existing LiteLLM fallback chain to draft context-aware follow-up emails for client meetings.
**When to use:** Client meetings where tone and content matter. Internal meetings use a simpler template.
**Example:**
```python
# Source: engine/intent/fallback_chain.py pattern
from intent.fallback_chain import FallbackChain, create_default_chain

FOLLOWUP_PROMPT = """Draft a professional follow-up email for a meeting.

Meeting: {title}
Date: {date}
Meeting Type: {meeting_type}
Attendees: {attendees}

Summary: {overview}

Action Items:
{action_items}

Decisions:
{decisions}

Instructions:
- Start with a brief thank you for the meeting
- Summarize the key discussion points in 2-3 sentences
- List action items clearly with owners if known
- Note any decisions made
- End with a forward-looking closing
- Tone: {tone} ({"professional and warm" if client else "casual and direct"})
- Keep it concise (under 200 words)
- Do NOT include subject line, just the email body
- Sign off as "Julian Bradley, AI Acrobatics"
"""
```

### Pattern 5: Post-Meeting REST Endpoint
**What:** A POST endpoint that the meeting-watcher v2 bridge (Phase 6) or manual trigger can call to initiate post-meeting flow.
**When to use:** When a meeting ends. The watcher detects meeting end and calls this endpoint.
**Example:**
```python
# Add to engine/api.py
class MeetingEndedRequest(PydanticBaseModel):
    meeting_id: str | None = None
    title: str
    attendee_emails: list[str]
    fireflies_meeting_id: str | None = None
    send_followup: bool = True  # Set to False for draft-only mode

@router.post("/meeting-ended")
async def meeting_ended(body: MeetingEndedRequest) -> dict:
    """Trigger post-meeting flow: summary upgrade + follow-up email."""
    # 1. Assemble context (get meeting type, prior context)
    ctx = await assemble_meeting_context(body.attendee_emails, body.title)

    # 2. Draft follow-up email
    email = await draft_followup_email(ctx, body.title)

    # 3. Optionally send
    if body.send_followup and email:
        results = await send_followup_to_attendees(email, body.attendee_emails)
        return {"status": "sent", "email": email.model_dump(), "results": results}

    return {"status": "drafted", "email": email.model_dump() if email else None}
```

### Anti-Patterns to Avoid
- **Sending email to all attendees including yourself:** Filter out owner emails (julianb233@gmail.com, julian@aiacrobatics.com) from the recipient list.
- **Using the raw `gws gmail users messages send` API:** The `gws gmail +send` helper handles RFC 2822 encoding and base64url automatically. The meeting-watcher v2 uses the raw API with manual `_encode_email` -- do not replicate that complexity.
- **Sending follow-up emails without confirmation for client meetings:** Auto-send for internal meetings is fine. Client meeting emails should ideally be drafted and require confirmation (via iMessage notification or panel button). Start with auto-send for both but add a `send_followup` flag.
- **Making new Fireflies API calls for prior context:** The context assembler already loads Fireflies transcripts in Phase 2. Extract prior context from the already-loaded data, do not make additional API calls.
- **Hardcoding email templates for both meeting types:** Internal meetings can use a simple template. Client meetings benefit from LLM-drafted emails that incorporate the client's communication style from their profile.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| RFC 2822 email encoding | `_encode_email()` base64 function (meeting-watcher v2 pattern) | `gws gmail +send` helper | Helper handles encoding, authentication, formatting automatically |
| Email domain extraction | Complex regex or email parsing library | `email.lower().split("@")[1]` | Attendee emails from Google Calendar are already valid |
| Transcript deduplication | Fuzzy matching algorithms | Set of transcript IDs | Fireflies transcript IDs are unique; same meeting has same ID for all participants |
| Action item deduplication | NLP similarity scoring | `dict.fromkeys()` after lowercasing/stripping | Fireflies action items are deterministic for a given transcript |
| Follow-up email drafting | Custom template engine | LiteLLM (already installed) with prompt template | LLM drafts are context-aware and can vary tone |
| OAuth for Gmail | Token refresh logic | `gws` CLI (handles it) | Same pattern as Google Contacts in Phase 2 |

**Key insight:** The meeting-watcher v2 (`scripts/meeting-watcher.py` lines 544-592) is the reference implementation for follow-up emails. It uses the raw Gmail API with manual RFC 2822 encoding. The copilot engine should use `gws gmail +send` instead, which is simpler and was verified working on this server.

## Common Pitfalls

### Pitfall 1: gws gmail +send Only Accepts One Recipient
**What goes wrong:** Trying to send to multiple comma-separated emails in a single `--to` argument may fail.
**Why it happens:** The `+send` helper takes a single `--to` email. The meeting-watcher v2 joins emails with commas for the raw API, but the helper may not support this.
**How to avoid:** Send one email per recipient using `asyncio.gather` for parallelism. Filter out owner emails first. Cap at 5 recipients maximum (matching meeting-watcher v2's limit).
**Warning signs:** Error from gws about invalid email format.

### Pitfall 2: Fireflies Summary Not Available Immediately
**What goes wrong:** Meeting ends, but Fireflies hasn't finished processing the transcript yet.
**Why it happens:** Fireflies takes 5-15 minutes to generate summaries after a meeting ends.
**How to avoid:** The context engine already loads transcripts during the meeting (Phase 2), so prior context from EARLIER meetings is available immediately. For the CURRENT meeting's post-meeting summary, the meeting-ended endpoint may need to accept pre-computed data from the meeting-watcher v2 (which polls Fireflies) or retry with backoff.
**Warning signs:** `get_fireflies_summary` returning empty summary object.

### Pitfall 3: Internal Team Members Using Personal Emails
**What goes wrong:** Julian's `julianb233@gmail.com` domain (gmail.com) triggers CLIENT classification.
**Why it happens:** Gmail.com is not in INTERNAL_DOMAINS, and Julian sometimes uses his personal email.
**How to avoid:** Maintain an OWNER_EMAILS set (`julianb233@gmail.com`, `julian@aiacrobatics.com`) that is filtered out before classification. These emails should never count toward internal/client determination since the owner is always present.
**Warning signs:** Solo meetings classified as CLIENT.

### Pitfall 4: Sending Follow-Up Emails to Internal Team
**What goes wrong:** Hitesh gets a formal "Thanks for the meeting" email after a standup.
**Why it happens:** Same email template used for internal and client meetings.
**How to avoid:** Check meeting_type. For INTERNAL: skip email entirely, or send a very brief "Notes from standup: [action items]" format. For CLIENT: use the full professional follow-up template. Consider making internal follow-ups opt-in via config flag.
**Warning signs:** Confused internal team members getting formal emails.

### Pitfall 5: Duplicate Follow-Up Emails
**What goes wrong:** Both meeting-watcher v2 AND the copilot engine try to send follow-up emails.
**Why it happens:** Phase 6 bridges the watcher to the copilot engine, but if both systems are running, both may trigger on meeting end.
**How to avoid:** Design the copilot's meeting-ended endpoint as the single source of truth. In Phase 6, the watcher should call the copilot's `/api/meeting-ended` endpoint instead of sending emails directly. For now (Phase 5), the copilot endpoint works standalone and the watcher continues to work independently.
**Warning signs:** Attendees receiving two follow-up emails.

### Pitfall 6: Prior Context Shows Julian's Internal Meetings to Client
**What goes wrong:** "Last time you discussed" shows topics from internal standups when meeting with a client.
**Why it happens:** TranscriptSummary objects include ALL meetings the attendee was in, not just meetings with the current attendees.
**How to avoid:** Filter prior meetings to only those where the current attendees overlap. When meeting with Sean from Hafnia, only show prior meetings where Sean (or someone from Hafnia) was also present. Use participant email matching with domain awareness.
**Warning signs:** Client sees reference to unrelated internal discussions.

## Code Examples

### Verified: gws gmail +send CLI Interface
```python
# Source: Verified gws gmail +send --help (2026-03-20)
# Usage: gws gmail +send --to <EMAIL> --subject <SUBJECT> --body <TEXT>
# Handles RFC 2822 formatting and base64 encoding automatically.
# For HTML bodies, attachments, or CC/BCC, use the raw API instead.

async def send_email(to: str, subject: str, body: str) -> bool:
    """Send a plain text email via gws CLI."""
    proc = await asyncio.create_subprocess_exec(
        "gws", "gmail", "+send",
        "--to", to,
        "--subject", subject,
        "--body", body,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "HOME": "/home/agent4"},
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode == 0
```

### Reference: Meeting-Watcher v2 Follow-Up Email Template
```python
# Source: scripts/meeting-watcher.py lines 558-572
# This is the existing template — port to copilot engine with meeting-type awareness

# For CLIENT meetings (professional):
body_client = f"""Hi,

Thanks for the meeting today -- "{title}".

Here's a quick summary:

{overview}

Action Items:
{items_text}
Let me know if I missed anything.

Best,
Julian Bradley
AI Acrobatics"""

# For INTERNAL meetings (casual, if sending at all):
body_internal = f"""Hey team,

Quick notes from "{title}":

{overview}

Action items:
{items_text}
-- J"""
```

### Existing TranscriptSummary Model (Prior Context Source)
```python
# Source: engine/context/fireflies.py (verified)
class TranscriptSummary(BaseModel):
    id: str
    title: str
    date: datetime | None = None
    duration: float | None = None  # minutes
    summary: str | None = None
    action_items: list[str] = Field(default_factory=list)
    participants: list[str] = Field(default_factory=list)
    transcript_url: str | None = None
```

### Existing UnifiedMeetingContext Fields to Extend
```python
# Source: engine/context/models.py (verified)
# Current fields — Phase 5 adds meeting_type, client_domains, prior_context
class UnifiedMeetingContext(BaseModel):
    meeting_title: str | None = None
    assembled_at: datetime
    load_time_seconds: float = 0.0
    attendees: list[AttendeeContext] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    # Phase 5 additions:
    # meeting_type: str = "unknown"  # "internal" | "client" | "unknown"
    # client_domains: list[str] = Field(default_factory=list)
    # prior_context: dict | None = None  # PriorMeetingContext.model_dump()
```

### WebSocket Event for Prior Context at Meeting Start
```python
# New message type for engine -> panel
class EngineMeetingContext(BaseModel):
    type: str = "meeting_context"
    meeting_type: str  # "internal" | "client" | "unknown"
    prior_context: dict | None  # PriorMeetingContext data
    attendee_count: int
    client_domains: list[str]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Raw `gws gmail users messages send` with manual RFC 2822 | `gws gmail +send` helper | Available in current gws version | No more manual base64url encoding of email messages |
| Template-only follow-up emails | LLM-drafted with tone from client profile | This phase | Emails match client communication preferences |
| No meeting type awareness | Internal vs client classification | This phase | Tone, scope, and routing differ by meeting type |
| Prior context = raw Fireflies list | Structured extraction with dedup | This phase | "Last time you discussed..." surfaces actionable context |

**Deprecated/outdated:**
- Manual RFC 2822 `_encode_email()` function from meeting-watcher v2: replaced by `gws gmail +send`
- Sending to comma-separated list: `gws gmail +send` takes single `--to`, send per-recipient

## Integration Points

### How Phase 5 Connects to Existing Architecture

```
Meeting Start:
  Calendar event detected (meeting-watcher v2 or future Zoom hook)
    -> POST /api/context with attendee emails
    -> assembler.py loads all context (Phase 2)
    -> NEW: classify_meeting_type() determines INTERNAL/CLIENT
    -> NEW: extract_prior_context() extracts "last time you discussed..."
    -> UnifiedMeetingContext returned with new fields
    -> WebSocket broadcasts meeting_context event to panel
    -> Panel shows prior context card and meeting type badge

Meeting During:
  Intent detection (Phase 3) uses meeting_type to:
    -> Scope project routing (internal: all projects, client: their project only)
    -> Adjust urgency thresholds
    -> Include/exclude certain projects from LLM context

Meeting End:
  Meeting-watcher v2 detects meeting ended
    -> POST /api/meeting-ended with title, attendees, optional fireflies_id
    -> NEW: draft_followup_email() generates email using meeting context
    -> NEW: send via gws gmail +send (one email per attendee)
    -> Returns draft for review or confirmation of send
```

### Files Modified by Phase 5

| File | Modification | Plan |
|------|-------------|------|
| `engine/intelligence/__init__.py` | New package | 05-01 |
| `engine/intelligence/meeting_classifier.py` | New file | 05-01 |
| `engine/intelligence/prior_context.py` | New file | 05-02 |
| `engine/intelligence/followup_email.py` | New file | 05-03 |
| `engine/context/models.py` | Add meeting_type, client_domains, prior_context | 05-01, 05-02 |
| `engine/context/assembler.py` | Call classifier and prior_context extractor | 05-01, 05-02 |
| `engine/api.py` | Add POST /api/meeting-ended | 05-03 |
| `engine/models.py` | Add EngineMeetingContext WS message | 05-03 |

## Open Questions

1. **gws gmail +send with multiple recipients**
   - What we know: The `--to` flag takes `<EMAIL>` (singular). Meeting-watcher v2 joins with commas for the raw API.
   - What's unclear: Whether `+send` supports comma-separated or multiple `--to` flags.
   - Recommendation: Send one email per recipient using `asyncio.gather`. This is safer and allows per-recipient error handling. Cap at 5 recipients.

2. **Follow-up email confirmation flow**
   - What we know: Requirement says "auto-drafted but optionally require confirmation before sending."
   - What's unclear: What the confirmation UX looks like (iMessage approval? Panel button? REST API hold?)
   - Recommendation: For Phase 5, implement with a `send_followup: bool` flag on the endpoint. Default to `True` for now. Phase 6 can add iMessage confirmation ("Reply YES to send follow-up to [attendees]").

3. **Prior context scoping for client meetings**
   - What we know: Fireflies returns ALL meetings an email participated in, not filtered by co-participants.
   - What's unclear: Whether filtering by attendee overlap is needed (Pitfall 6) or if showing all past meetings with that person is acceptable.
   - Recommendation: Filter by attendee overlap. When meeting with Sean@hafnia, only show meetings where someone from hafniafin.com was also a participant. This prevents leaking internal discussion topics to client context.

4. **Post-meeting summary upgrade (PST-02)**
   - What we know: Meeting-watcher v2 already writes Obsidian notes with summaries. PST-02 says "upgrade existing."
   - What's unclear: What "upgrade" means specifically -- better formatting? Project-aware context? LLM re-summarization?
   - Recommendation: The upgrade is: include project context (which Linear project, which client profile) in the Obsidian summary. Add meeting_type and prior_context references. This happens naturally when the follow-up email endpoint assembles full context.

## Sources

### Primary (HIGH confidence)
- Engine source code: `engine/context/models.py`, `engine/context/assembler.py`, `engine/context/fireflies.py` -- verified current models and pipeline
- Engine source code: `engine/intent/detector.py`, `engine/intent/models.py` -- verified intent pipeline structure
- Engine source code: `engine/ws_handler.py`, `engine/api.py`, `engine/models.py` -- verified WebSocket and REST patterns
- `gws gmail +send --help` output -- verified CLI interface (2026-03-20)
- `scripts/meeting-watcher.py` lines 489-592 -- verified post-meeting and follow-up email implementation

### Secondary (MEDIUM confidence)
- Phase 2 research (`02-RESEARCH.md`) -- Fireflies API patterns, Google Contacts behavior, rate limits
- Phase 3 research (`03-RESEARCH.md`) -- LiteLLM patterns, fallback chain, agent spawning

### Tertiary (LOW confidence)
- `gws gmail +send` behavior with multiple recipients (needs testing)
- Fireflies transcript processing delay after meeting end (estimated 5-15 min based on observation)

## Metadata

**Confidence breakdown:**
- Meeting classification (05-01): HIGH -- Simple domain matching against known emails, no API calls needed
- Prior context surfacing (05-02): HIGH -- Extracts from data already loaded by Phase 2, no new API calls
- Follow-up email (05-03): HIGH for drafting, MEDIUM for sending (gws +send needs multi-recipient testing)
- Integration with assembler: HIGH -- Clear extension points in models.py and assembler.py
- Integration with meeting-watcher v2: MEDIUM -- Bridge is Phase 6; Phase 5 works standalone via REST endpoint

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (30 days -- stack is stable, gws CLI and engine architecture unlikely to change)
