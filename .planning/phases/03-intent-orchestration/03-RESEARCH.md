# Phase 3: Intent Detection & Task Orchestration - Research

**Researched:** 2026-03-20
**Domain:** Multi-model LLM classification, intent extraction, Linear GraphQL API, fleet agent orchestration
**Confidence:** HIGH

## Summary

Phase 3 upgrades the existing meeting-watcher v2 sentence classification into structured intent extraction with project-aware routing and fleet agent spawning. The existing codebase at `/opt/agency-workspace/scripts/meeting-watcher.py` already implements a working multi-model fallback chain (Anthropic -> OpenAI -> Gemini -> Keywords) with model health tracking and cooldown logic. This phase wraps that proven pattern into the new FastAPI engine, adds structured intent output (not just classification labels), routes intents to correct Linear projects, and spawns fleet agents for execution-ready tasks.

The fleet infrastructure is mature: `god fleet` CLI provides agent tool execution, `repo-executor.js` handles autonomous code tasks with locking, and `task-router.js` provides keyword-based agent specialization scoring. Linear API integration already exists in `fleet_shared/tools/linear.js` with project-by-name lookup, team resolution, and label management via GraphQL. The key engineering challenge is bridging these Node.js fleet tools from a Python FastAPI engine.

**Primary recommendation:** Build a Python `IntentDetector` class that wraps the existing fallback chain pattern with a structured output prompt (returning JSON with action_type, target, urgency, project fields). Use `subprocess` to call `god fleet` CLI for agent spawning and direct HTTP calls to Linear's GraphQL API for issue creation with project routing.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-generativeai | latest | Gemini API (primary classifier) | Free tier, already working in meeting-watcher |
| anthropic | latest | Claude API (preferred when credits available) | Best structured output, highest accuracy |
| openai | latest | OpenAI fallback | Third in chain, rate-limited but functional |
| httpx | 0.27+ | Async HTTP client for Linear API | Async-native, connection pooling, timeout control |
| pydantic | 2.x | Intent data models / validation | Already in FastAPI stack, structured output parsing |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tenacity | 8.x | Retry logic with backoff | Wrap API calls with exponential backoff |
| asyncio | stdlib | Async subprocess for fleet spawning | Non-blocking agent spawn from FastAPI |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw HTTP to Gemini | google-generativeai SDK | SDK adds convenience but raw HTTP matches existing code |
| httpx for Linear | urllib (existing) | httpx is async-native, better for FastAPI; existing code uses urllib |
| subprocess for fleet | HTTP to fleet gateway (port 8080) | Fleet gateway is WebSocket-based, CLI is simpler and proven |

**Installation:**
```bash
pip install httpx pydantic tenacity google-generativeai anthropic openai
```

## Architecture Patterns

### Recommended Project Structure
```
engine/
  intent/
    __init__.py
    detector.py          # IntentDetector class with fallback chain
    models.py            # Pydantic models: Intent, ClassifiedSentence, IntentBatch
    prompts.py           # Prompt templates for each model
    fallback_chain.py    # Multi-model chain with health tracking
  routing/
    __init__.py
    linear_router.py     # Linear API: project lookup, issue creation, project creation
    project_cache.py     # In-memory cache of Linear projects (refresh every 5 min)
  orchestration/
    __init__.py
    fleet_spawner.py     # Spawn fleet agents via god CLI subprocess
    task_tracker.py      # Track spawned task status, report via WebSocket
    agent_selector.py    # Port of task-router.js logic to Python
```

### Pattern 1: Multi-Model Fallback Chain with Health Tracking
**What:** Try models in priority order, track failures, skip models in cooldown
**When to use:** Every classification request
**Example:**
```python
# Source: Adapted from meeting-watcher.py lines 278-326
from dataclasses import dataclass, field
from time import time
from typing import Optional, Callable, Awaitable

@dataclass
class ModelHealth:
    last_fail: float = 0
    consecutive_fails: int = 0
    cooldown_seconds: float = 300  # 5 min cooldown after 2+ failures

    def is_available(self) -> bool:
        if self.consecutive_fails < 2:
            return True
        return (time() - self.last_fail) > self.cooldown_seconds

    def record_failure(self):
        self.consecutive_fails += 1
        self.last_fail = time()

    def record_success(self):
        self.consecutive_fails = 0
        self.last_fail = 0

@dataclass
class ModelProvider:
    name: str
    call: Callable[[str], Awaitable[str]]
    health: ModelHealth = field(default_factory=ModelHealth)

class FallbackChain:
    def __init__(self, providers: list[ModelProvider]):
        self.providers = providers

    async def classify(self, prompt: str) -> tuple[str, str]:
        """Returns (response_text, model_name) or raises if all fail."""
        for provider in self.providers:
            if not provider.health.is_available():
                continue
            try:
                result = await provider.call(prompt)
                provider.health.record_success()
                return result, provider.name
            except Exception as e:
                provider.health.record_failure()
                continue
        # Final fallback: keywords
        return None, "keywords"
```

### Pattern 2: Structured Intent Extraction (not just classification)
**What:** LLM returns structured JSON with action_type, target, urgency, project -- not just a category label
**When to use:** For every non-INFO classified sentence batch
**Example:**
```python
# Pydantic model for intent output
from pydantic import BaseModel
from typing import Optional, Literal
from enum import Enum

class ActionType(str, Enum):
    CREATE_ISSUE = "create_issue"
    BUILD_FEATURE = "build_feature"
    FIX_BUG = "fix_bug"
    RESEARCH = "research"
    SEND_EMAIL = "send_email"
    CREATE_PROPOSAL = "create_proposal"
    SCHEDULE_MEETING = "schedule_meeting"
    CHECK_DOMAIN = "check_domain"
    DEPLOY = "deploy"
    DECISION = "decision"
    FOLLOW_UP = "follow_up"

class Intent(BaseModel):
    action_type: ActionType
    target: str                         # What to act on ("login page", "landing page")
    urgency: Literal["now", "soon", "later"] = "soon"
    project: Optional[str] = None       # Detected project name
    assignee: Optional[str] = None      # Who should do it
    details: str                        # Full context extracted
    confidence: float                   # 0-1 confidence score
    source_text: str                    # Original transcript text
    speaker: str                        # Who said it
    requires_agent: bool = False        # Whether to spawn a fleet agent
```

### Pattern 3: Two-Stage Classification
**What:** Stage 1 = fast batch classification (INFO/ACTION_ITEM/DECISION/etc). Stage 2 = structured intent extraction only on non-INFO items.
**When to use:** Always. Avoids expensive intent extraction on the 80%+ of sentences that are INFO.
**Example:**
```python
async def process_sentences(self, sentences: list[dict], context: MeetingContext):
    # Stage 1: Fast classification (batch of 8, cheap)
    classifications = await self.fallback_chain.classify(
        self.prompts.classify_batch(sentences)
    )

    # Stage 2: Intent extraction only on actionable items
    actionable = [s for s, c in zip(sentences, classifications)
                  if c != "INFO"]

    if actionable:
        intents = await self.fallback_chain.classify(
            self.prompts.extract_intents(actionable, context)
        )
        return self.parse_intents(intents)
    return []
```

### Pattern 4: Project Detection via Context Matching
**What:** Match detected intent to Linear project using meeting context (attendee, conversation topic, explicit mentions)
**When to use:** When routing an intent to a Linear project
**Example:**
```python
async def resolve_project(self, intent: Intent, context: MeetingContext) -> str:
    """Resolve which Linear project this intent belongs to."""
    # Priority 1: Explicit project name in intent
    if intent.project:
        project = await self.linear.find_project(intent.project)
        if project:
            return project.id

    # Priority 2: Current conversation topic (from context engine)
    if context.active_project:
        return context.active_project.linear_project_id

    # Priority 3: Attendee's primary project
    if context.attendee and context.attendee.primary_project:
        return context.attendee.primary_project.linear_project_id

    # Priority 4: Default team inbox
    return self.default_project_id
```

### Anti-Patterns to Avoid
- **Single-model dependency:** Never rely on one model. Anthropic has zero credits currently, OpenAI is rate-limited. Always fallback.
- **Synchronous API calls in FastAPI:** All LLM and Linear API calls must be async. Use httpx, not urllib.
- **Intent extraction on every sentence:** 80%+ are INFO. Two-stage classification saves cost and latency.
- **String interpolation in GraphQL:** Use variables (`$input: IssueCreateInput!`), not f-strings. Prevents injection and handles special characters.
- **Blocking subprocess for fleet spawning:** Use `asyncio.create_subprocess_exec`, not `subprocess.run`.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-model fallback with health | Custom retry logic | Adapt existing meeting-watcher pattern + tenacity | Health tracking, cooldown, and chain ordering already proven |
| Linear project lookup by name | Custom search | Existing `linear.js` GraphQL pattern: `projects(filter: { name: { containsIgnoreCase: $name } })` | Exact GraphQL query already working in fleet |
| Agent task routing | Custom agent selection | Port `task-router.js` AGENT_SPECIALIZATIONS map | Keyword-domain scoring with load awareness already tuned |
| Linear issue creation with project | Raw GraphQL string building | Use `IssueCreateInput` mutation with variables | Existing `linear_create` handler in fleet shows exact pattern |
| Repo task execution | Custom git+claude orchestration | `god fleet HeadDev devops.execute_repo_task` via subprocess | Handles branching, locking, PR creation, agent rotation |
| Structured LLM output parsing | Custom JSON regex extraction | Pydantic `model_validate_json` with fallback regex | Handles malformed JSON, markdown-wrapped responses |

**Key insight:** The fleet already has Linear integration (`linear.js`, `linear-client.js`), agent task routing (`task-router.js`), and repo execution (`repo-executor.js`). The copilot engine should call these existing tools rather than reimplementing them in Python.

## Common Pitfalls

### Pitfall 1: Anthropic API Has Zero Credits
**What goes wrong:** Code defaults to Claude as primary, fails silently or throws on every request
**Why it happens:** Anthropic billing is separate from fleet budget, currently at $0
**How to avoid:** Make Gemini the actual first provider in the chain (not Claude). Check API key existence AND make a test call on startup to verify credits.
**Warning signs:** All classifications falling through to keywords

### Pitfall 2: Gemini JSON Output Wrapping
**What goes wrong:** Gemini wraps JSON in markdown code fences (```json ... ```)
**Why it happens:** Gemini's default behavior adds formatting to structured output
**How to avoid:** Strip markdown code fences before JSON parsing. The existing `_parse_classifications` in meeting-watcher already handles this with regex: `re.search(r'\[.*\]', text, re.DOTALL)`
**Warning signs:** JSON parse errors on otherwise valid responses

### Pitfall 3: Linear Project ID vs Team ID Confusion
**What goes wrong:** Issues created in wrong project or team, or creation fails
**Why it happens:** Linear has teams (organizational) and projects (work tracking). Issues belong to a team but can be linked to a project. The existing code hardcodes `LINEAR_TEAM_ID`.
**How to avoid:** Always resolve team first, then optionally attach projectId. Use the `containsIgnoreCase` filter for fuzzy project matching.
**Warning signs:** Issues appearing in wrong project, or `issueCreate` returning team validation errors

### Pitfall 4: Multi-Project Switching Detection False Positives
**What goes wrong:** Every mention of a project name triggers a topic switch
**Why it happens:** Conversations naturally reference multiple projects without switching context
**How to avoid:** Require sustained topic change (3+ consecutive sentences about a different project) before switching active project. Use a sliding window, not per-sentence detection.
**Warning signs:** Intent routing flip-flopping between projects every few sentences

### Pitfall 5: Fleet Agent Spawning During Meeting Blocks Event Loop
**What goes wrong:** `subprocess.run` blocks the FastAPI event loop, websocket messages stall
**Why it happens:** `god fleet` CLI calls can take 2-30 seconds depending on the operation
**How to avoid:** Use `asyncio.create_subprocess_exec` for all `god` CLI calls. Fire-and-forget for spawning, poll for status.
**Warning signs:** WebSocket heartbeat timeouts, panel showing stale data

### Pitfall 6: Rate Limiting Cascade
**What goes wrong:** When one model rate-limits, all traffic shifts to next model which also rate-limits
**Why it happens:** Burst of classification requests after a quiet period
**How to avoid:** Batch sentences (existing CLASSIFY_BATCH_SIZE=8 is good). Add request-level rate limiting per model (e.g., max 10 req/min for OpenAI). Increase cooldown time on rate limit errors specifically.
**Warning signs:** All three models in cooldown simultaneously, everything falling to keywords

## Code Examples

### Linear GraphQL: List Projects
```python
# Source: Adapted from fleet_shared/tools/linear.js lines 69-81
FIND_PROJECT_QUERY = """
query FindProject($name: String!) {
    projects(filter: { name: { containsIgnoreCase: $name } }, first: 5) {
        nodes { id name state }
    }
}
"""

async def find_project(self, name: str) -> Optional[dict]:
    data = await self.graphql(FIND_PROJECT_QUERY, {"name": name})
    nodes = data.get("projects", {}).get("nodes", [])
    # Prefer exact match, then first fuzzy match
    for node in nodes:
        if node["name"].lower() == name.lower():
            return node
    return nodes[0] if nodes else None
```

### Linear GraphQL: Create Issue with Project Routing
```python
# Source: Adapted from fleet_shared/tools/linear.js lines 100-108
CREATE_ISSUE_MUTATION = """
mutation CreateIssue($input: IssueCreateInput!) {
    issueCreate(input: $input) {
        success
        issue { id identifier title url state { name } }
    }
}
"""

async def create_issue(self, title: str, description: str, team_id: str,
                       project_id: Optional[str] = None,
                       priority: int = 3,
                       labels: Optional[list[str]] = None) -> dict:
    input_data = {
        "teamId": team_id,
        "title": title[:200],
        "description": description,
        "priority": priority,
    }
    if project_id:
        input_data["projectId"] = project_id
    if labels:
        label_ids = [await self.ensure_label(team_id, l) for l in labels]
        input_data["labelIds"] = label_ids

    data = await self.graphql(CREATE_ISSUE_MUTATION, {"input": input_data})
    return data["issueCreate"]["issue"]
```

### Linear GraphQL: Create Project (for new clients)
```python
CREATE_PROJECT_MUTATION = """
mutation CreateProject($input: ProjectCreateInput!) {
    projectCreate(input: $input) {
        success
        project { id name url }
    }
}
"""

async def create_project(self, name: str, description: str = "",
                         team_ids: Optional[list[str]] = None) -> dict:
    input_data = {
        "name": name,
        "description": description or f"Auto-created from meeting copilot",
    }
    if team_ids:
        input_data["teamIds"] = team_ids

    data = await self.graphql(CREATE_PROJECT_MUTATION, {"input": input_data})
    return data["projectCreate"]["project"]
```

### Fleet Agent Spawning via god CLI
```python
# Source: Verified from god CLI help and fleet_shared/tools/repo-executor.js
import asyncio
import json

async def spawn_fleet_task(self, agent: str, command: str,
                           params: dict) -> dict:
    """Spawn a fleet agent task via god CLI."""
    args = ["god", "fleet", agent, command]

    # god fleet expects JSON params as positional args
    params_json = json.dumps(params)
    args.append(params_json)

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode == 0:
        try:
            return json.loads(stdout.decode())
        except json.JSONDecodeError:
            return {"success": True, "output": stdout.decode()}
    else:
        return {"success": False, "error": stderr.decode()}

# Example: Spawn Bob to build a feature
result = await spawn_fleet_task(
    agent="HeadDev",
    command="devops.execute_repo_task",
    params={
        "repo": "better-together-live",
        "task_description": "Add a booking calendar widget to the landing page",
    }
)
```

### Intent Extraction Prompt
```python
INTENT_EXTRACTION_PROMPT = """You are an intent extraction engine for a live meeting transcript.
Given the meeting context and actionable transcript lines, extract structured intents.

Meeting Context:
- Attendees: {attendees}
- Active Project: {active_project}
- Known Projects: {known_projects}

Return a JSON array of intents. Each intent has:
- action_type: one of [create_issue, build_feature, fix_bug, research, send_email,
                       create_proposal, schedule_meeting, check_domain, deploy,
                       decision, follow_up]
- target: what to act on (the noun/object)
- urgency: "now" (do it during meeting), "soon" (today/tomorrow), "later" (backlog)
- project: which project this belongs to (from known projects list, or null)
- details: full context of what's needed
- confidence: 0.0-1.0
- requires_agent: true if this needs a fleet agent to execute code/build something

Only extract genuine intents. Most conversation is not actionable.

Transcript lines:
{lines}

Return ONLY valid JSON array, no markdown formatting."""
```

### Multi-Project Switching Detection
```python
class TopicTracker:
    """Track which project the conversation is about using a sliding window."""

    def __init__(self, known_projects: list[str], switch_threshold: int = 3):
        self.known_projects = known_projects
        self.switch_threshold = switch_threshold
        self.recent_mentions = []  # list of (project_name, sentence_index)
        self.active_project: Optional[str] = None

    def update(self, sentence: str, index: int) -> Optional[str]:
        """Check if sentence mentions a project. Returns new active project
        if topic switch detected, None otherwise."""
        sentence_lower = sentence.lower()

        for project in self.known_projects:
            if project.lower() in sentence_lower:
                self.recent_mentions.append((project, index))
                break

        # Keep only last 10 mentions
        self.recent_mentions = self.recent_mentions[-10:]

        # Check if last N mentions are all the same project (and different from active)
        if len(self.recent_mentions) >= self.switch_threshold:
            recent = [m[0] for m in self.recent_mentions[-self.switch_threshold:]]
            if len(set(recent)) == 1 and recent[0] != self.active_project:
                self.active_project = recent[0]
                return self.active_project

        return None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Keyword matching classification | LLM batch classification | Already in meeting-watcher v2 | 10x better accuracy, catches nuanced action items |
| Single model API calls | Multi-model fallback chain | Already in meeting-watcher v2 | Resilience against billing/rate limits |
| Flat classification labels | Structured intent extraction with Pydantic | This phase (new) | Enables routing, agent spawning, project awareness |
| Hardcoded LINEAR_TEAM_ID | Project-aware routing via context | This phase (new) | Issues go to correct project, not generic inbox |
| Manual task creation after meeting | Real-time fleet agent spawning | This phase (new) | Work begins during the meeting |

**Deprecated/outdated:**
- `urllib.request` for API calls: Replace with `httpx` for async in FastAPI context
- Hardcoded `LINEAR_TEAM_ID = '9a9d11aa-...'`: Must be replaced with dynamic team+project resolution
- Synchronous classification loop: Must be async for WebSocket-driven architecture

## Open Questions

Things that could not be fully resolved:

1. **god fleet CLI parameter passing format**
   - What we know: `god fleet <agent> <category.action>` is the CLI pattern. Fleet gateway routes to tool handlers.
   - What's unclear: Exact format for passing JSON params via CLI (positional arg? stdin? --params flag?). The gateway test files may clarify this.
   - Recommendation: Test with a simple `god fleet HeadDev tasks.check_my_tasks` call first, then try `devops.execute_repo_task` with a dry-run repo.

2. **Linear projectCreate input schema completeness**
   - What we know: `ProjectCreateInput` exists with name, description, teamIds fields.
   - What's unclear: Whether teamIds is required or optional, what other fields are available (color, icon, etc).
   - Recommendation: Use GraphQL introspection query against Linear API to get full input type: `{ __type(name: "ProjectCreateInput") { inputFields { name type { name } } } }`

3. **Fleet agent status reporting mechanism**
   - What we know: Fleet gateway has `updateAgentStatus(agentName, status, task)` and broadcasts typed events via WebSocket. The gateway runs on port 8080.
   - What's unclear: How the copilot engine should subscribe to fleet gateway WebSocket events to track spawned task completion.
   - Recommendation: Connect copilot engine to fleet gateway WebSocket at `ws://localhost:8080` and listen for `task_complete` typed events.

4. **Gemini structured output mode**
   - What we know: Gemini 2.0 Flash supports `response_mime_type: "application/json"` with `response_schema` parameter for guaranteed JSON output.
   - What's unclear: Whether the free tier supports this mode or if it requires paid API access.
   - Recommendation: Try setting `generationConfig.responseMimeType` in the Gemini API call. Fall back to regex JSON extraction if not supported.

## Sources

### Primary (HIGH confidence)
- `/opt/agency-workspace/scripts/meeting-watcher.py` - Full existing classification code, fallback chain, Linear issue creation
- `/home/dev/ai-acrobatics-fleet/fleet_shared/tools/linear.js` - Linear GraphQL patterns for issue creation with project routing
- `/home/dev/ai-acrobatics-fleet/fleet_shared/tools/linear-client.js` - Shared Linear GraphQL client with team resolution
- `/home/dev/ai-acrobatics-fleet/fleet_shared/tools/repo-executor.js` - Fleet task execution with repo locking, branch management
- `/home/dev/ai-acrobatics-fleet/fleet_shared/tools/task-router.js` - Agent specialization scoring and routing logic
- `/home/dev/ai-acrobatics-fleet/fleet_shared/tools/spawn-doug-task.js` - Task delegation pattern (Supabase + fleet message + Linear)
- `/home/dev/ai-acrobatics-fleet/fleet_gateway.cjs` - Fleet gateway WebSocket with agent status tracking
- `god fleet HeadDev --list-tools` output - Available fleet tools and categories

### Secondary (MEDIUM confidence)
- [Linear GraphQL API docs](https://linear.app/developers/graphql) - issueCreate, projectCreate mutations, project filter queries
- [How to Create Issues with Linear API in Python](https://endgrate.com/blog/how-to-create-or-update-issues-with-the-linear-api-in-python) - Python examples
- [Linear API GraphOS Studio](https://studio.apollographql.com/public/Linear-API/variant/current/schema/reference/objects/Mutation) - Schema reference

### Tertiary (LOW confidence)
- Gemini 2.0 Flash structured output mode (response_mime_type) - Not verified on free tier

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Based on existing working code in meeting-watcher and fleet tools
- Architecture: HIGH - Patterns directly adapted from production code (meeting-watcher, fleet gateway)
- Linear API: HIGH - Working GraphQL patterns found in fleet_shared/tools/linear.js and linear-client.js
- Fleet spawning: MEDIUM - god CLI interface confirmed, exact param passing format needs testing
- Pitfalls: HIGH - Derived from real issues documented in meeting-watcher code (zero credits, rate limits, Gemini JSON wrapping)

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable domain, fleet tools change slowly)
