# Phase 2: Context Engine - Research

**Researched:** 2026-03-20
**Domain:** Multi-source data aggregation (Google Contacts, Fireflies, Linear, Obsidian vault)
**Confidence:** HIGH

## Summary

The Context Engine loads attendee context from four data sources when a meeting starts: Google Contacts (identity), Fireflies (meeting history), Linear (projects/issues), and the local Obsidian vault + client-profiles directory (relationship context). All APIs are verified working on this server with existing credentials.

The primary challenge is **attendee-to-context mapping**: calendar events provide email addresses, but each data source uses different keys (email, name, org name, file slug). The engine must resolve an email address into identity info, then fan out parallel lookups across all sources.

**Primary recommendation:** Build an async context pipeline using `httpx.AsyncClient` that takes attendee emails, resolves identity via Google Contacts `searchContacts` (by extracted name) + local Obsidian contacts, then fans out parallel Fireflies/Linear/client-profile lookups. Use `asyncio.gather` for all independent API calls.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.28.1 (installed) | Async HTTP for Fireflies + Linear GraphQL | Already in requirements.txt, native async support |
| pydantic | 2.x (installed) | Context model validation | Already used for all models in engine |
| asyncio | stdlib | Parallel data loading | Python standard, zero dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-frontmatter | latest | Parse Obsidian YAML frontmatter | Parsing .md files with YAML headers |
| pyyaml | latest | YAML parsing (frontmatter dep) | Required by python-frontmatter |
| pathlib | stdlib | File path operations for vault | Scanning Obsidian and client-profiles dirs |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| httpx | aiohttp | httpx already installed, simpler API, sync+async in one library |
| python-frontmatter | manual YAML parsing | frontmatter handles the `---` delimiter extraction cleanly |
| subprocess for gws | httpx to Google API | gws CLI already handles OAuth tokens; httpx would need token management |

**Installation:**
```bash
pip install python-frontmatter pyyaml
```

## Architecture Patterns

### Recommended Project Structure
```
engine/
  context/
    __init__.py            # ContextEngine class (orchestrator)
    google_contacts.py     # People API via gws CLI
    fireflies.py           # Fireflies GraphQL client
    linear.py              # Linear GraphQL client
    obsidian.py            # Vault + client-profiles reader
    assembler.py           # Merge all sources into UnifiedContext
    models.py              # Pydantic models for context data
```

### Pattern 1: Async Fan-Out with Gather
**What:** After resolving attendee identity, fan out all independent data source lookups in parallel using `asyncio.gather`.
**When to use:** Every meeting start event.
**Example:**
```python
async def load_context(attendee_emails: list[str]) -> UnifiedContext:
    """Load full context for all attendees in parallel."""
    attendee_contexts = await asyncio.gather(
        *[load_single_attendee(email) for email in attendee_emails]
    )
    return assemble_context(attendee_contexts)

async def load_single_attendee(email: str) -> AttendeeContext:
    """Load all data sources for one attendee in parallel."""
    identity = await resolve_identity(email)

    # Fan out all independent lookups
    transcripts, linear_data, profile = await asyncio.gather(
        load_fireflies_history(email),
        load_linear_context(identity.org_name or identity.name),
        load_client_profile(email, identity),
    )
    return AttendeeContext(
        identity=identity,
        meeting_history=transcripts,
        linear=linear_data,
        profile=profile,
    )
```

### Pattern 2: gws CLI Subprocess for Google APIs
**What:** Use `asyncio.create_subprocess_exec` to call the `gws` CLI tool for Google Workspace APIs, since it handles OAuth token management.
**When to use:** Google Contacts (People API) lookups.
**Example:**
```python
async def search_contacts(query: str) -> list[dict]:
    """Search Google Contacts via gws CLI."""
    proc = await asyncio.create_subprocess_exec(
        "gws", "people", "people", "searchContacts",
        "--params", json.dumps({
            "query": query,
            "readMask": "names,emailAddresses,organizations,phoneNumbers,photos"
        }),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    data = json.loads(stdout)
    return data.get("results", [])
```

### Pattern 3: GraphQL Client with httpx
**What:** Use `httpx.AsyncClient` for Fireflies and Linear GraphQL endpoints.
**When to use:** All Fireflies and Linear API calls.
**Example:**
```python
class FirefliesClient:
    BASE_URL = "https://api.fireflies.ai/graphql"

    def __init__(self, api_key: str):
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=15.0,
        )

    async def get_transcripts_for_participant(
        self, email: str, limit: int = 3
    ) -> list[dict]:
        query = """
        query($participants: [String!], $limit: Int) {
            transcripts(participants: $participants, limit: $limit) {
                id title date duration
                organizer_email participants
                meeting_attendees { displayName email name }
                summary { overview action_items short_summary }
            }
        }
        """
        resp = await self.client.post(
            self.BASE_URL,
            json={"query": query, "variables": {"participants": [email], "limit": limit}},
        )
        data = resp.json()
        return data.get("data", {}).get("transcripts", [])
```

### Anti-Patterns to Avoid
- **Sequential API calls:** Never call Fireflies, then Linear, then Obsidian in sequence. Always use `asyncio.gather`.
- **Blocking subprocess for gws:** Use `asyncio.create_subprocess_exec`, never `subprocess.run`.
- **Parsing Obsidian YAML by hand:** Use `python-frontmatter` library; manual YAML extraction is fragile.
- **Hardcoding project-to-client mapping:** Build a lookup system from client profiles (which contain Linear project references) rather than a static dictionary.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML frontmatter parsing | Regex-based `---` splitter | `python-frontmatter` | Handles edge cases (empty frontmatter, special chars) |
| Google OAuth tokens | Custom token refresh flow | `gws` CLI (already handles it) | Token management is complex, gws already works |
| GraphQL query building | String formatting with f-strings | Parameterized queries with `variables` | Avoids injection, handles escaping |
| Email domain extraction | Manual string splitting | `email.split("@")[1]` or `email_address` field | Simple but standardize it once |
| Parallel execution | Manual threading | `asyncio.gather` | Built-in, clean error handling |

**Key insight:** The meeting-watcher v2 (`/opt/agency-workspace/scripts/meeting-watcher.py`) already has working Fireflies and Linear API patterns using raw `urllib`. Port those patterns to async `httpx` rather than inventing from scratch.

## Common Pitfalls

### Pitfall 1: Google Contacts searchContacts Does NOT Match Email Addresses
**What goes wrong:** `searchContacts` with an email like `sean@hafniafin.com` returns empty `{}`. It only matches against names, nicknames, and organizations -- not email addresses directly.
**Why it happens:** Google's People API `searchContacts` does prefix matching on names/nicknames/organizations, not on email fields. This is verified behavior on this workspace.
**How to avoid:** Use a two-step strategy:
1. Extract the display name from the calendar event attendee data (Google Calendar provides `displayName` for attendees)
2. Search by display name via `searchContacts`
3. If no display name available, try searching the local part of the email (e.g., "jan.gleisner" from "jan@hafniafin.com")
4. Fallback: search Obsidian contacts directory by email (frontmatter has `email:` field)
**Warning signs:** Empty results from `searchContacts` when you know the contact exists.

### Pitfall 2: Fireflies Rate Limits (50/day on Standard Plan)
**What goes wrong:** Exceeding 50 API calls per day causes failures.
**Why it happens:** Each attendee lookup = 1 API call. A meeting with 5 attendees = 5 calls. 10 meetings/day = 50 calls.
**How to avoid:**
1. Cache Fireflies responses with a TTL (transcripts don't change once complete)
2. Batch attendee lookups where possible
3. Use the `participants` array filter to query multiple emails in one call if needed
4. Track daily API call count
**Warning signs:** 429 or error responses from Fireflies.

### Pitfall 3: Linear Project-to-Client Mapping is Manual
**What goes wrong:** No automatic way to map an attendee email domain to a Linear project.
**Why it happens:** Linear projects don't have external email associations. Project names sometimes contain client names (e.g., "Acre Partners -- Content Engine", "hafnia-financial") but this is convention, not API data.
**How to avoid:** Build a mapping from client-profiles and Obsidian contacts:
1. Client profiles contain `slug:` (e.g., "hafnia-financial") and contact emails
2. Linear projects can be searched by `searchProjects(term: slug)`
3. Build an email-domain-to-project lookup at startup
**Warning signs:** Linear returns no results for a known client.

### Pitfall 4: Obsidian Vault Has Multiple Contact Locations
**What goes wrong:** Missing contacts because they're in a different directory.
**Why it happens:** Contacts are spread across:
- `/opt/agency-workspace/obsidian-vault/Contacts/` (individual contacts with frontmatter)
- `/opt/agency-workspace/obsidian-vault/People/Key-Circle/` and `People/Inner-Circle/`
- `/opt/agency-workspace/client-profiles/*.md` (client NLP profiles with detailed communication context)
**How to avoid:** Search ALL locations in order of priority:
1. `client-profiles/*.md` -- richest data (communication style, NLP profile, project context)
2. `obsidian-vault/Contacts/*.md` -- individual contacts with email, company, role
3. `obsidian-vault/People/*/` -- people with relationship context
Match by email field in frontmatter, then by name fuzzy match.
**Warning signs:** Attendee marked as "unknown" when a profile exists.

### Pitfall 5: Fireflies Date Field is Unix Milliseconds
**What goes wrong:** Date comparisons fail or produce wrong results.
**Why it happens:** Fireflies returns `date` as Unix timestamp in milliseconds (e.g., `1774026000000`), not seconds.
**How to avoid:** Divide by 1000 before converting: `datetime.fromtimestamp(date / 1000)`.
**Warning signs:** Dates in year 58000+.

## Code Examples

### Verified: Fireflies Transcript Query by Participant Email
```python
# Source: Verified on live Fireflies API (2026-03-20)
# Confirmed: participants filter works, returns transcripts where email is a participant
QUERY = """
query($participants: [String!], $limit: Int) {
    transcripts(participants: $participants, limit: $limit) {
        id
        title
        date
        duration
        organizer_email
        participants
        meeting_attendees {
            displayName
            email
            name
        }
        summary {
            overview
            action_items
            short_summary
        }
    }
}
"""
# Usage: variables={"participants": ["jan@hafniafin.com"], "limit": 3}
# Returns: list of transcripts where that email appears in participants
```

### Verified: Linear Project Search
```python
# Source: Verified on live Linear API (2026-03-20)
# searchProjects accepts a term and does fuzzy matching on project name
PROJECT_SEARCH_QUERY = """
query($term: String!, $first: Int) {
    searchProjects(term: $term, first: $first) {
        nodes {
            id
            name
            slugId
            description
            state
        }
    }
}
"""
# Usage: variables={"term": "hafnia", "first": 5}
```

### Verified: Linear Open Issues by Project Name
```python
# Source: Verified on live Linear API (2026-03-20)
# Filter issues by project name (containsIgnoreCase) and exclude completed/canceled
OPEN_ISSUES_QUERY = """
query($projectName: String!, $first: Int) {
    issues(
        filter: {
            project: { name: { containsIgnoreCase: $projectName } }
            state: { type: { nin: ["completed", "canceled"] } }
        }
        first: $first
    ) {
        nodes {
            id
            identifier
            title
            state { name type }
            priority
            priorityLabel
        }
    }
}
"""
# Usage: variables={"projectName": "hafnia", "first": 10}
```

### Verified: Google Contacts Search via gws CLI
```python
# Source: Verified on live gws CLI (2026-03-20)
# searchContacts matches by name prefix, NOT by email address
# Returns: names, emailAddresses, organizations, phoneNumbers, photos
import asyncio
import json

async def search_google_contacts(name_query: str) -> list[dict]:
    proc = await asyncio.create_subprocess_exec(
        "gws", "people", "people", "searchContacts",
        "--params", json.dumps({
            "query": name_query,
            "readMask": "names,emailAddresses,organizations,phoneNumbers,photos"
        }),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    if proc.returncode != 0:
        return []
    data = json.loads(stdout)
    return [r["person"] for r in data.get("results", [])]
```

### Verified: Obsidian Contact File Parsing
```python
# Source: Verified file structure (2026-03-20)
# Obsidian contacts use YAML frontmatter with key fields
import frontmatter
from pathlib import Path

OBSIDIAN_CONTACTS = Path("/opt/agency-workspace/obsidian-vault/Contacts")
CLIENT_PROFILES = Path("/opt/agency-workspace/client-profiles")

def load_contact_by_email(email: str) -> dict | None:
    """Search all contact sources for a matching email."""
    # 1. Check client profiles (richest data)
    for f in CLIENT_PROFILES.glob("*.md"):
        if f.name.startswith(("README", "CLIENT-PORTAL")):
            continue
        post = frontmatter.load(f)
        # Client profiles have contact emails in body, not always frontmatter
        if email in post.content:
            return {"source": "client-profile", "path": str(f), "metadata": dict(post.metadata), "content": post.content}

    # 2. Check obsidian contacts
    for f in OBSIDIAN_CONTACTS.glob("*.md"):
        post = frontmatter.load(f)
        if post.metadata.get("email") == email:
            return {"source": "obsidian-contact", "path": str(f), "metadata": dict(post.metadata), "content": post.content}

    return None
```

### Unified Context Model
```python
# Recommended Pydantic model for assembled context
from pydantic import BaseModel
from datetime import datetime

class AttendeeIdentity(BaseModel):
    email: str
    display_name: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    organization: str | None = None
    phone: str | None = None
    photo_url: str | None = None
    source: str = "unknown"  # "google_contacts" | "obsidian" | "calendar" | "fireflies"

class MeetingHistoryEntry(BaseModel):
    transcript_id: str
    title: str
    date: datetime
    duration_minutes: float
    summary: str | None = None
    action_items: str | None = None
    short_summary: str | None = None

class LinearProjectContext(BaseModel):
    project_id: str
    project_name: str
    state: str
    description: str | None = None

class LinearIssueContext(BaseModel):
    identifier: str
    title: str
    state: str
    priority_label: str | None = None

class ClientProfile(BaseModel):
    slug: str
    status: str
    communication_style: str | None = None
    formality: str | None = None
    tone: str | None = None
    tech_understanding: str | None = None
    disc_type: str | None = None
    safe_terms: list[str] = []
    avoid_terms: list[str] = []
    raw_content: str  # Full markdown for classifier prompt

class AttendeeContext(BaseModel):
    identity: AttendeeIdentity
    meeting_history: list[MeetingHistoryEntry] = []
    linear_projects: list[LinearProjectContext] = []
    linear_open_issues: list[LinearIssueContext] = []
    client_profile: ClientProfile | None = None

class UnifiedMeetingContext(BaseModel):
    meeting_id: str
    meeting_title: str
    started_at: datetime
    attendees: list[AttendeeContext]

    def to_classifier_prompt(self) -> str:
        """Format context for the LLM classifier."""
        sections = [f"# Meeting: {self.meeting_title}"]
        for att in self.attendees:
            sections.append(f"\n## Attendee: {att.identity.display_name or att.identity.email}")
            if att.identity.organization:
                sections.append(f"**Organization:** {att.identity.organization}")
            if att.client_profile:
                sections.append(f"**Communication Style:** {att.client_profile.communication_style}")
                sections.append(f"**Formality:** {att.client_profile.formality}")
            if att.meeting_history:
                sections.append(f"\n### Last {len(att.meeting_history)} meetings:")
                for mh in att.meeting_history:
                    sections.append(f"- {mh.title} ({mh.date.strftime('%Y-%m-%d')}): {mh.short_summary or 'No summary'}")
            if att.linear_open_issues:
                sections.append(f"\n### Open Linear issues ({len(att.linear_open_issues)}):")
                for issue in att.linear_open_issues[:5]:
                    sections.append(f"- [{issue.identifier}] {issue.title} ({issue.state})")
        return "\n".join(sections)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fireflies `participant_email` (single) | `participants` (array) | 2024 | Can filter by multiple emails in one query |
| Google Contacts API v1 `contacts.get` | People API `people.searchContacts` | 2019 | Must use People API, Contacts API deprecated |
| Linear REST API | Linear GraphQL API only | Always | No REST endpoint exists; GraphQL is the only option |

**Deprecated/outdated:**
- Fireflies `participant_email` field: deprecated, use `participants` array instead
- Fireflies `date` filter: deprecated, use `fromDate`/`toDate` instead
- Google Contacts API: fully deprecated, People API is the replacement

## Identity Resolution Strategy

The core challenge is mapping an email address to a person across all systems. Recommended resolution order:

```
Email address (from calendar event)
  |
  +--> 1. Obsidian Contacts (by email frontmatter field) --> name, company, role
  |         /opt/agency-workspace/obsidian-vault/Contacts/*.md
  |
  +--> 2. Client Profiles (by email in content) --> NLP profile, communication style
  |         /opt/agency-workspace/client-profiles/*.md
  |
  +--> 3. Google Contacts (by name from step 1, or by calendar displayName)
  |         gws people people searchContacts
  |         --> phone, photo, organization
  |
  +--> 4. Fireflies meeting_attendees (by email) --> displayName from past meetings
           Already returned in transcript queries

Email domain --> Client slug mapping:
  hafniafin.com  --> hafnia-financial
  acrepartner.com --> acre-partner
  Build this map from client-profiles frontmatter at startup.
```

## Linear Project Mapping Strategy

Since Linear projects don't store external client emails, build the mapping from local data:

1. **At startup:** Load all client profiles, extract `slug` field and associated email domains
2. **At query time:** Map attendee email domain to client slug
3. **Search Linear:** `searchProjects(term: slug)` to find matching projects
4. **Load issues:** Filter open issues by project name

Known client-to-project mappings (from client-profiles):
| Email Domain | Client Slug | Linear Project Name |
|-------------|-------------|---------------------|
| hafniafin.com | hafnia-financial | "hafnia-financial" |
| acrepartner.com | acre-partner | "Acre Partners -- Content Engine" |
| brandonlehmanbiz@gmail.com | brandon-lehman | "Brandon Lehman - AI Detection SaaS" |

## API Authentication Summary

| API | Auth Method | Credential Location | Header Format |
|-----|------------|---------------------|---------------|
| Google People | OAuth2 (via gws CLI) | Managed by gws | N/A (gws handles it) |
| Fireflies | Bearer token | `$FIREFLIES_API_KEY` env var | `Authorization: Bearer {key}` |
| Linear | API key | `$LINEAR_API_KEY` env var | `Authorization: {key}` (no Bearer prefix) |
| Obsidian | Local filesystem | N/A | N/A |

**IMPORTANT:** Linear auth does NOT use "Bearer" prefix. The meeting-watcher code confirms: `'Authorization': LINEAR_API_KEY` (raw key value).

## Rate Limit Summary

| API | Limit | Scope | Strategy |
|-----|-------|-------|----------|
| Fireflies | 50 req/day (standard) | Per API key | Cache transcript responses; they don't change once complete |
| Linear | ~50 req/min (estimated) | Per API key | Generous; batch where possible but not critical |
| Google People | Unknown but generous | Per OAuth user | gws handles rate limiting |
| Obsidian | Filesystem I/O | N/A | Cache file reads at startup |

## Open Questions

1. **Calendar attendee displayName availability**
   - What we know: Google Calendar events include `attendees[].email` and sometimes `attendees[].displayName`
   - What's unclear: Whether displayName is reliably populated for all attendees
   - Recommendation: Always try displayName first, fall back to Obsidian contact lookup by email, then try email local part for Google Contacts search

2. **Fireflies plan tier and actual rate limit**
   - What we know: Standard plans get 50/day, Business/Enterprise get 60/min
   - What's unclear: Which tier is active on this account
   - Recommendation: Implement caching regardless; monitor for 429 errors and log daily usage

3. **Git activity requirement (CTX-06)**
   - What we know: Requirement says "Load recent git activity for matched projects"
   - What's unclear: Which repos to check, how to map client to repo
   - Recommendation: Client profiles have `Repo(s)` field in template. Could use `git log --since=7d --oneline` on matched repos. Defer to plan for specifics.

## Sources

### Primary (HIGH confidence)
- Live API testing on this server (2026-03-20) - Fireflies transcripts query, Linear projects/issues, Google Contacts searchContacts
- `/opt/agency-workspace/scripts/meeting-watcher.py` - Working Fireflies and Linear integration patterns
- `/opt/agency-workspace/obsidian-vault/Contacts/` - Verified file structure with YAML frontmatter
- `/opt/agency-workspace/client-profiles/` - Verified profile structure with NLP data
- `gws` CLI help output - People API methods and parameters

### Secondary (MEDIUM confidence)
- [Fireflies API docs](https://docs.fireflies.ai/graphql-api/query/transcripts) - transcripts query schema
- [Linear developers](https://linear.app/developers) - GraphQL API, authentication, pagination
- [Google People API searchContacts](https://developers.google.com/people/api/rest/v1/people/searchContacts) - search behavior and readMask fields

### Tertiary (LOW confidence)
- Fireflies rate limits (50/day vs 60/min) - from docs, not verified on this account

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries verified installed, APIs tested live
- Architecture: HIGH - async fan-out pattern proven, API schemas verified
- Pitfalls: HIGH - discovered via live testing (searchContacts email limitation, Fireflies date format)
- Identity resolution: MEDIUM - strategy designed from observed behavior, needs real-meeting validation
- Rate limits: MEDIUM - documented but plan tier unknown

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (APIs stable, local infrastructure unlikely to change)
