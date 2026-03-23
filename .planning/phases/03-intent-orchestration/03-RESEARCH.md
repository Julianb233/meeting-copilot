# Phase 3: Intent Detection & Task Orchestration - Research

**Researched:** 2026-03-20 (updated)
**Domain:** LLM-powered intent extraction, multi-model fallback, fleet agent orchestration, Linear API routing
**Confidence:** HIGH

## Summary

Phase 3 upgrades the existing meeting-watcher v2 sentence classification (ACTION_ITEM, DECISION, FOLLOW_UP, QUESTION, INFO) into structured intent extraction with project routing and fleet agent spawning. The existing codebase already has a multi-model fallback chain (Anthropic -> OpenAI -> Gemini -> Keywords) in `scripts/meeting-watcher.py`, LiteLLM as a dependency in the engine `requirements.txt`, and a full context engine producing `UnifiedMeetingContext` with Linear projects per attendee.

The key technical decisions are: (1) Use LiteLLM Router for the fallback chain instead of hand-rolling model switching -- LiteLLM is already a dependency and provides automatic cooldown, retry, and health tracking, (2) Use Pydantic models as LiteLLM `response_format` for structured intent extraction, (3) Spawn fleet agents via `asyncio.create_subprocess_exec` calling `claude -p --print` (verified working on this VPS), (4) Extend existing `linear_client.py` with issue creation mutation using parameterized GraphQL.

**Primary recommendation:** Build the intent detector as a new `engine/intent/` module using LiteLLM Router with Gemini-primary (free) -> OpenAI -> Claude fallback order, structured Pydantic output models, and project routing based on the already-loaded `UnifiedMeetingContext.attendees[].linear_projects`. Use two-stage classification: fast batch classify first, then structured intent extraction only on actionable items.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| litellm | >=1.0.0 | Multi-model LLM calls with Router fallback | Already in requirements.txt; handles Gemini/OpenAI/Claude with one interface; Router provides automatic cooldown/retry/health |
| pydantic | >=2.0 | Intent schema models + structured output via response_format | Already used throughout engine for all models |
| httpx | >=0.28.0 | Linear GraphQL API calls (async) | Already used in linear_client.py |
| asyncio | stdlib | Subprocess spawning for fleet agents | Built-in, already used in assembler.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| uuid | stdlib | Generate unique task/intent IDs | Every intent and task creation |
| re | stdlib | Keyword fallback classifier + JSON fence stripping | When all LLM models fail, or Gemini wraps JSON in markdown |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| LiteLLM Router | Hand-rolled fallback (like meeting-watcher v2) | LiteLLM Router gives cooldown, retry, health tracking for free. Meeting-watcher v2 approach works but is 100+ lines replaced by ~20 lines of config |
| LiteLLM Router | Separate google-generativeai + anthropic + openai SDKs | Three different APIs to learn, three different response formats to handle. LiteLLM unifies them |
| asyncio subprocess for agents | god fleet CLI | `claude -p --print` is simpler and verified working. `god fleet` CLI is designed for PM2 bot tool execution, not spawning Claude Code tasks |
| Extending linear_client.py | New Linear module | linear_client.py already has the GraphQL patterns, httpx client, and error handling. Just add issue creation mutation |

**Installation:**
```bash
# No new dependencies needed -- all already in requirements.txt
pip install litellm>=1.0.0 httpx>=0.28.0 pydantic>=2.0.0
```

## Architecture Patterns

### Recommended Project Structure
```
engine/
├── intent/
│   ├── __init__.py
│   ├── detector.py       # IntentDetector class - two-stage extraction from transcript
│   ├── models.py         # IntentType, Urgency, DetectedIntent, IntentExtractionResult
│   ├── router.py         # LiteLLM Router config with fallback chain
│   ├── prompts.py        # System prompts for classification and extraction
│   └── keywords.py       # Keyword fallback classifier (ported from meeting-watcher v2)
├── orchestrator/
│   ├── __init__.py
│   ├── task_orchestrator.py  # Spawn agents, track tasks, report status via WebSocket
│   ├── agent_pool.py         # Agent slot availability, assignment, status tracking
│   └── linear_router.py      # Route intents to correct Linear team + create issues
├── context/               # (existing - Phase 2)
│   ├── assembler.py
│   ├── linear_client.py   # EXTEND: add create_linear_issue(), list_teams()
│   └── models.py
├── models.py              # (existing - EXTEND with intent WebSocket event types)
├── ws_handler.py          # (existing - add intent/orchestrator event handlers)
└── main.py                # (existing)
```

### Pattern 1: LiteLLM Router for Multi-Model Fallback Chain
**What:** Configure LiteLLM Router with ordered model deployments so failover is automatic with health tracking, cooldown, and retries built in.
**When to use:** Every intent detection call.
**Example:**
```python
# Source: https://docs.litellm.ai/docs/routing
from litellm import Router
import config

def create_intent_router() -> Router:
    """Create LiteLLM Router with Gemini-primary fallback chain."""
    model_list = []

    # Gemini first -- free tier, $0 budget constraint
    if config.GEMINI_API_KEY:
        model_list.append({
            "model_name": "intent-classifier",
            "litellm_params": {
                "model": "gemini/gemini-2.0-flash",
                "api_key": config.GEMINI_API_KEY,
                "order": 1,
            },
        })

    # OpenAI second -- rate-limited but functional
    if config.OPENAI_API_KEY:
        model_list.append({
            "model_name": "intent-classifier",
            "litellm_params": {
                "model": "openai/gpt-4o-mini",
                "api_key": config.OPENAI_API_KEY,
                "order": 2,
            },
        })

    # Claude last -- zero credits currently
    if config.ANTHROPIC_API_KEY:
        model_list.append({
            "model_name": "intent-classifier",
            "litellm_params": {
                "model": "anthropic/claude-haiku-4-5-20251001",
                "api_key": config.ANTHROPIC_API_KEY,
                "order": 3,
            },
        })

    return Router(
        model_list=model_list,
        num_retries=2,
        allowed_fails=2,
        cooldown_time=60,
        enable_pre_call_checks=True,
    )
```

### Pattern 2: Structured Intent Extraction with Pydantic + LiteLLM
**What:** Use Pydantic models as LiteLLM `response_format` for type-safe intent extraction across all providers.
**When to use:** Every LLM classification call.
**Example:**
```python
# Source: https://docs.litellm.ai/docs/completion/json_mode
from pydantic import BaseModel, Field
from enum import Enum
import litellm

# Enable client-side validation as safety net for providers
# that don't natively support response_format schemas
litellm.enable_json_schema_validation = True

class IntentType(str, Enum):
    CREATE_TASK = "create_task"
    ASSIGN_WORK = "assign_work"
    MAKE_DECISION = "make_decision"
    FOLLOW_UP = "follow_up"
    RESEARCH = "research"
    DRAFT_EMAIL = "draft_email"
    SCHEDULE = "schedule"
    INFO = "info"

class Urgency(str, Enum):
    IMMEDIATE = "immediate"   # Do during meeting
    HIGH = "high"             # Today
    NORMAL = "normal"         # This week
    LOW = "low"               # Backlog

class DetectedIntent(BaseModel):
    intent_type: IntentType
    summary: str = Field(description="One-line summary of the intent")
    target_project: str | None = Field(None, description="Linear team key, e.g. ACRE")
    assignee: str | None = Field(None, description="Who should do this")
    urgency: Urgency = Urgency.NORMAL
    confidence: float = Field(ge=0, le=1, description="0-1 confidence score")
    source_text: str = Field(description="Original transcript text")
    speaker: str = Field(description="Who said it")
    requires_agent: bool = Field(False, description="Needs fleet agent to execute")

class IntentExtractionResult(BaseModel):
    intents: list[DetectedIntent]
    current_topic: str | None = Field(None, description="Current conversation project/topic")

# Usage:
response = await router.acompletion(
    model="intent-classifier",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": transcript_chunk},
    ],
    response_format=IntentExtractionResult,
)
result = IntentExtractionResult.model_validate_json(
    response.choices[0].message.content
)
```

### Pattern 3: Two-Stage Classification
**What:** Stage 1 = fast batch classification (INFO vs actionable). Stage 2 = structured intent extraction only on non-INFO items.
**When to use:** Always. Avoids expensive structured extraction on the 80%+ of sentences that are INFO.
**Example:**
```python
# Source: Adapted from meeting-watcher.py CLASSIFY_BATCH_SIZE=8 pattern
async def process_transcript_chunk(
    self,
    sentences: list[dict],
    meeting_context: UnifiedMeetingContext,
) -> list[DetectedIntent]:
    # Stage 1: Fast classification using existing CLASSIFY_PROMPT pattern
    # Returns dict[int, str] mapping index -> classification label
    classifications = await self._classify_batch(sentences)

    # Filter to actionable items only
    actionable = [
        sentences[i] for i, cls in classifications.items()
        if cls != "INFO"
    ]

    if not actionable:
        return []

    # Stage 2: Structured intent extraction on actionable items only
    context_prompt = meeting_context.to_classifier_prompt()
    projects_list = self._format_projects(meeting_context)

    result = await self._extract_intents(actionable, context_prompt, projects_list)

    # Filter low-confidence intents
    return [i for i in result.intents if i.confidence >= 0.7]
```

### Pattern 4: Project-Aware Routing via Meeting Context
**What:** Match detected intents to Linear teams using the already-loaded UnifiedMeetingContext.
**When to use:** After intent extraction, before issue creation or agent spawning.
**Example:**
```python
def route_intent_to_team(
    intent: DetectedIntent,
    meeting_context: UnifiedMeetingContext,
) -> str | None:
    """Return the Linear team ID for this intent.

    Strategy:
    1. If intent.target_project matches a team key, use it
    2. If only one attendee has projects, use their primary team
    3. If meeting title matches a team name, use it
    4. Return None -- caller decides (default team or prompt user)
    """
    # Collect all known projects from context
    all_projects: list[LinearProject] = []
    for attendee in meeting_context.attendees:
        all_projects.extend(attendee.linear_projects)

    # Direct match from LLM extraction
    if intent.target_project:
        for proj in all_projects:
            if proj.key.upper() == intent.target_project.upper():
                return proj.id

    # Single-project meeting (most common case)
    unique_projects = {p.key: p for p in all_projects}
    if len(unique_projects) == 1:
        return list(unique_projects.values())[0].id

    # Title match
    if meeting_context.meeting_title:
        title_lower = meeting_context.meeting_title.lower()
        for proj in all_projects:
            if proj.name.lower() in title_lower or proj.key.lower() in title_lower:
                return proj.id

    return None
```

### Pattern 5: Fleet Agent Spawning via Claude CLI
**What:** Spawn Claude Code as async subprocess for task execution.
**When to use:** When an execution-ready intent is detected (requires_agent=True, urgency=immediate).
**Example:**
```python
# Verified: claude -p "test" --print works on this VPS
import asyncio

async def spawn_agent_task(
    task_prompt: str,
    working_dir: str = "/opt/agency-workspace",
    timeout: int = 300,
) -> tuple[int, str, str]:
    """Spawn a Claude Code agent to execute a task.

    Uses --print mode for non-interactive output.
    Returns (return_code, stdout, stderr).
    """
    proc = await asyncio.create_subprocess_exec(
        "claude",
        "-p", task_prompt,
        "--print",
        "--model", "sonnet",
        "--allowedTools", "Bash", "Read", "Write", "Edit", "Glob", "Grep",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=working_dir,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
        return proc.returncode or 0, stdout.decode(), stderr.decode()
    except asyncio.TimeoutError:
        proc.kill()
        return -1, "", "Task timed out"
```

### Anti-Patterns to Avoid
- **Using separate google-generativeai, anthropic, openai SDKs:** LiteLLM is already a dependency and wraps all three with a unified API. Do not install or use provider-specific SDKs.
- **Hand-rolling fallback chain with try/except:** LiteLLM Router handles this automatically with cooldown, health tracking, and retries. The meeting-watcher v2 pattern of `_call_anthropic`, `_call_openai`, `_call_gemini` is exactly what LiteLLM replaces.
- **Calling LLM APIs with raw httpx/urllib:** Use LiteLLM. It handles auth, format differences, rate limit retries.
- **Blocking subprocess calls in FastAPI:** Use `asyncio.create_subprocess_exec`, never `subprocess.run`. The engine is async.
- **Hardcoded Linear team IDs:** The meeting-watcher v2 uses `LINEAR_TEAM_ID = '9a9d11aa-...'`. Phase 3 must dynamically route based on meeting context.
- **Classifying single sentences:** Batch 5-8 sentences with surrounding context. Meeting-watcher v2 already does CLASSIFY_BATCH_SIZE = 8.
- **Fire-and-forget agent spawning:** Track subprocess PID, set timeouts, report status via WebSocket.
- **String interpolation in GraphQL:** Use parameterized `variables` dict (like linear_client.py does), not f-strings (like meeting-watcher v2 does).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-model fallback chain | Custom try/except per model (like meeting-watcher v2) | LiteLLM Router with ordered deployments | Handles cooldown, retry, health tracking, rate limits. ~20 lines replaces ~100 lines |
| JSON parsing from LLM | Regex extraction of JSON from text | LiteLLM `response_format=PydanticModel` | Automatic validation, type safety, provider-specific format handling |
| Model capability checks | Manual tracking of which models support structured output | `litellm.supports_response_schema(model)` | LiteLLM knows provider capabilities and versions |
| API key validation at startup | Checking env vars manually | LiteLLM Router `enable_pre_call_checks=True` | Skips models without valid keys automatically |
| Linear issue creation GraphQL | String interpolation (like meeting-watcher v2 line 450-459) | Parameterized GraphQL with `variables` dict | Prevents injection bugs, handles quotes/newlines in titles |
| Agent subprocess management | Raw subprocess tracking | AgentPool class with slots + timeouts | Prevents zombie processes, limits concurrency to 4 agents |

**Key insight:** The meeting-watcher v2 (`scripts/meeting-watcher.py`) is 750 lines of manually orchestrated API calls. LiteLLM Router replaces the entire fallback chain (~100 lines) with ~20 lines of config. The existing `linear_client.py` already uses proper parameterized GraphQL -- extend it rather than duplicating meeting-watcher v2's unsafe string interpolation approach.

## Common Pitfalls

### Pitfall 1: Anthropic API Has Zero Credits
**What goes wrong:** Code defaults to Claude as primary, fails silently or throws on every request.
**Why it happens:** ANTHROPIC_API_KEY exists in env but account has no credits.
**How to avoid:** Order the LiteLLM Router: Gemini first (free, order=1), OpenAI second (order=2), Claude last (order=3). Set `enable_pre_call_checks=True`. Consider checking at startup if Anthropic key works.
**Warning signs:** All classifications falling through to keyword fallback because errors cascade.

### Pitfall 2: Gemini JSON Output Wrapping
**What goes wrong:** Gemini wraps JSON responses in markdown code fences (```json ... ```).
**Why it happens:** Gemini's default behavior when asked for JSON.
**How to avoid:** Enable `litellm.enable_json_schema_validation = True` as client-side safety net. Also strip markdown fences before parsing as a fallback. Meeting-watcher v2 already handles this with `re.search(r'\[.*\]', text, re.DOTALL)`.
**Warning signs:** JSON parse errors on otherwise valid Gemini responses.

### Pitfall 3: Over-Classification (False Positives)
**What goes wrong:** LLM marks too many sentences as actionable, flooding Linear with garbage issues.
**Why it happens:** Without strong guidance, LLMs err on the side of classifying everything as important.
**How to avoid:** Keep the meeting-watcher v2 prompt principle: "Be selective. Most lines are INFO. Only flag clear, actionable items." Add confidence threshold (ignore intents with confidence < 0.7). Use two-stage classification so only genuinely actionable items reach intent extraction.
**Warning signs:** More than 20% of transcript lines classified as non-INFO.

### Pitfall 4: Agent Subprocess Zombies
**What goes wrong:** Spawned Claude processes hang, consuming VPS resources (48-core, 252GB RAM).
**Why it happens:** No timeout set, agent gets stuck in a loop or waiting for input.
**How to avoid:** Always use `asyncio.wait_for` with timeout (300s max). Track active processes in AgentPool. Kill orphaned processes on meeting end. Limit concurrent agents to 4 (matching agent1-4 slots in MeetingState).
**Warning signs:** VPS memory climbing during meetings, `ps aux | grep claude` showing stale processes.

### Pitfall 5: Multi-Project Topic Switching Races
**What goes wrong:** When meeting switches from Project A to Project B, intents still route to Project A.
**Why it happens:** Intent detection processes batches (8 sentences), topic context is stale.
**How to avoid:** Include `current_topic` field in the IntentExtractionResult. The system prompt should list ALL known projects. Track topic state per meeting. Require 3+ consecutive mentions before switching active project. Include surrounding context window (like meeting-watcher v2's `get_context_window`).
**Warning signs:** Issues created in wrong projects when meeting covers multiple clients.

### Pitfall 6: Linear Team vs Project Confusion
**What goes wrong:** Routing to wrong Linear entity.
**Why it happens:** Linear has Teams (organizational units with keys like ACRE-42) and Projects (cross-team work groupings). The existing `linear_client.py` searches Teams by name and calls them "LinearProject" in the Pydantic model.
**How to avoid:** Continue using Teams as the routing target (they have issue keys like ACRE, HAFN). Use `teamId` in `issueCreate`, not `projectId`. The `LinearProject` model in the codebase actually maps to Linear Teams -- maintain this mapping.
**Warning signs:** Issues appearing in wrong boards, or `issueCreate` validation errors.

### Pitfall 7: Rate Limiting Cascade
**What goes wrong:** When Gemini rate-limits, all traffic shifts to OpenAI which also rate-limits.
**Why it happens:** Burst of classification requests after a quiet period in meeting.
**How to avoid:** Batch sentences (CLASSIFY_BATCH_SIZE=8). LiteLLM Router handles cooldown automatically (`cooldown_time=60`). Do not retry faster than the batch interval.
**Warning signs:** All models in cooldown simultaneously, everything falling to keywords.

## Code Examples

### Keyword Fallback Classifier (Port from Meeting-Watcher v2)
```python
# Source: meeting-watcher.py lines 328-361
def classify_keywords(text: str) -> str:
    """Final fallback when all LLM models are unavailable."""
    t = text.lower().strip()
    if not t or len(t) < 10:
        return "INFO"

    action_kw = [
        "we need to", "let's build", "let's create", "let's set up",
        "i'll handle", "make sure to", "action item", "task:",
        "set up a", "schedule a", "please create", "implement this", "deploy",
    ]
    decision_kw = [
        "we decided", "let's go with", "the plan is", "agreed on",
        "going forward", "we're going to",
    ]
    followup_kw = [
        "follow up with", "send them", "email them",
        "reach out to", "get back to", "circle back",
    ]
    question_kw = ["?"]

    for kw in action_kw:
        if kw in t:
            return "ACTION_ITEM"
    for kw in decision_kw:
        if kw in t:
            return "DECISION"
    for kw in followup_kw:
        if kw in t:
            return "FOLLOW_UP"
    for kw in question_kw:
        if kw in t:
            return "QUESTION"
    return "INFO"
```

### Extending linear_client.py for Issue Creation
```python
# Add to engine/context/linear_client.py
ISSUE_CREATE_MUTATION = """
mutation IssueCreate($input: IssueCreateInput!) {
    issueCreate(input: $input) {
        success
        issue {
            id
            identifier
            title
            url
        }
    }
}
"""

async def create_linear_issue(
    team_id: str,
    title: str,
    description: str | None = None,
    priority: int = 0,
    label_ids: list[str] | None = None,
) -> dict | None:
    """Create a Linear issue in the specified team.

    Uses parameterized GraphQL (not string interpolation).
    Returns issue dict with id, identifier, title, url or None on failure.
    """
    if not config.LINEAR_API_KEY:
        logger.warning("LINEAR_API_KEY not set")
        return None

    variables = {
        "input": {
            "title": title[:200],
            "teamId": team_id,
            "priority": priority,
        }
    }
    if description:
        variables["input"]["description"] = description
    if label_ids:
        variables["input"]["labelIds"] = label_ids

    try:
        async with httpx.AsyncClient() as client:
            result = await _graphql_request(client, ISSUE_CREATE_MUTATION, variables)
            if "errors" in result:
                logger.error("Linear issue creation failed: %s", result["errors"])
                return None
            issue_data = result.get("data", {}).get("issueCreate", {})
            if issue_data.get("success"):
                issue = issue_data.get("issue")
                logger.info("Created Linear issue: %s -> %s", issue.get("identifier"), issue.get("url"))
                return issue
            return None
    except Exception:
        logger.exception("Failed to create Linear issue")
        return None
```

### Agent Pool Manager
```python
# engine/orchestrator/agent_pool.py
import asyncio
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class AgentSlot:
    name: str
    busy: bool = False
    current_task_id: str | None = None
    process: asyncio.subprocess.Process | None = None
    started_at: datetime | None = None

class AgentPool:
    """Manages fleet agent slots for concurrent task execution."""

    def __init__(self, agent_names: list[str] | None = None):
        names = agent_names or ["agent1", "agent2", "agent3", "agent4"]
        self.slots = {name: AgentSlot(name=name) for name in names}

    def get_available(self) -> AgentSlot | None:
        for slot in self.slots.values():
            if not slot.busy:
                return slot
        return None

    def mark_busy(self, name: str, task_id: str, proc: asyncio.subprocess.Process):
        slot = self.slots[name]
        slot.busy = True
        slot.current_task_id = task_id
        slot.process = proc
        slot.started_at = datetime.utcnow()

    def mark_free(self, name: str):
        slot = self.slots[name]
        slot.busy = False
        slot.current_task_id = None
        slot.process = None
        slot.started_at = None

    async def kill_all(self):
        """Kill all active agent processes (call on meeting end)."""
        for slot in self.slots.values():
            if slot.process and slot.process.returncode is None:
                slot.process.kill()
            self.mark_free(slot.name)
```

### Intent Extraction System Prompt
```python
INTENT_SYSTEM_PROMPT = """You analyze meeting transcript excerpts and extract structured intents.

CONTEXT:
{context_prompt}

AVAILABLE LINEAR PROJECTS (use these keys for target_project):
{projects_list}

RULES:
1. Most transcript lines are casual conversation. Be HIGHLY selective.
2. Only extract intents for CLEAR, ACTIONABLE statements.
3. "We should...", "Let's...", "Can you..." = intents. "That's interesting" = not an intent.
4. Match intents to the correct project key based on conversation context.
5. Set urgency=immediate ONLY if the speaker says "right now" or "during this meeting".
6. Set requires_agent=true only for tasks that need code execution (build, deploy, research).
7. Include original text in source_text for traceability.
8. confidence < 0.7 items will be discarded, so only include clear intents.

Return a JSON object matching the IntentExtractionResult schema."""
```

### Multi-Project Topic Switching Detection
```python
class TopicTracker:
    """Track which project the meeting is discussing using a sliding window."""

    def __init__(self, known_projects: list[str], switch_threshold: int = 3):
        self.known_projects = [p.lower() for p in known_projects]
        self.project_keys = known_projects  # original case
        self.switch_threshold = switch_threshold
        self.recent_mentions: list[str] = []
        self.active_project: str | None = None

    def update(self, sentence: str) -> str | None:
        """Returns new active project key if topic switch detected."""
        sentence_lower = sentence.lower()

        for i, proj_lower in enumerate(self.known_projects):
            if proj_lower in sentence_lower:
                self.recent_mentions.append(self.project_keys[i])
                break

        self.recent_mentions = self.recent_mentions[-10:]

        if len(self.recent_mentions) >= self.switch_threshold:
            recent = self.recent_mentions[-self.switch_threshold:]
            if len(set(recent)) == 1 and recent[0] != self.active_project:
                self.active_project = recent[0]
                return self.active_project

        return None
```

### WebSocket Event Broadcasting
```python
# Extend engine/ws_handler.py
async def broadcast_intent_detected(self, intent: DetectedIntent, task_id: str | None = None):
    """Broadcast detected intent to all connected panels."""
    await self.broadcast({
        "type": "intent_detected",
        "intent": intent.model_dump(mode="json"),
        "task_id": task_id,
    })

async def broadcast_agent_update(self, agent_name: str, status: str, task_id: str | None = None):
    """Broadcast agent status change to panels."""
    await self.broadcast({
        "type": "agent_status",
        "agent": agent_name,
        "status": status,
        "task_id": task_id,
    })
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Keyword matching classification | LLM batch classification | Already in meeting-watcher v2 | 10x better accuracy for nuanced action items |
| Separate provider SDKs (anthropic, openai, google-generativeai) | LiteLLM unified API with Router | 2024-2025 | One interface, automatic fallback, provider-agnostic |
| Free-text LLM output with regex parsing | Pydantic response_format structured output | 2024-2025 | Type-safe, validated, works across providers via LiteLLM |
| Flat classification labels (ACTION_ITEM, DECISION, etc.) | Structured intent extraction (type, target, urgency, project, confidence) | This phase | Enables routing, agent spawning, project awareness |
| Hardcoded LINEAR_TEAM_ID | Project-aware routing via UnifiedMeetingContext | This phase | Issues go to correct project, not generic inbox |
| Manual task creation after meeting | Real-time fleet agent spawning during meeting | This phase | Work begins during the meeting |

**Deprecated/outdated:**
- `urllib.request` for API calls (meeting-watcher v2): Use httpx or LiteLLM
- Hardcoded `LINEAR_TEAM_ID = '9a9d11aa-...'`: Must be replaced with dynamic team resolution from context
- String-interpolated GraphQL mutations: Use parameterized variables dict
- Separate provider SDK imports: Use LiteLLM as the unified interface

## Open Questions

1. **Claude CLI authentication for spawned agent tasks**
   - What we know: `claude -p "prompt" --print` works on agent4 (current account, verified). Agent accounts agent1-4 exist at `/home/agent{N}/`. `sudo -u agent1` requires password. SSH to localhost failed.
   - What's unclear: Whether all spawned tasks should run as agent4 or as separate user accounts. Running all as agent4 is simpler but provides no isolation.
   - Recommendation: Run all spawned agents as the current user (agent4) with different `--cwd` directories. Use the `--add-dir` flag for cross-project access. The AgentPool "slots" are logical, not physical user accounts.

2. **Gemini structured output reliability with Pydantic models**
   - What we know: LiteLLM docs confirm Gemini 2.0+ supports `responseJsonSchema`. `litellm.supports_response_schema()` can check. Client-side validation available via `litellm.enable_json_schema_validation = True`.
   - What's unclear: How reliably Gemini 2.0 Flash follows complex nested Pydantic schemas (enums, optional fields, nested lists) on the free tier.
   - Recommendation: Enable client-side validation. Have a regex JSON extraction fallback. Test with actual Pydantic schema during implementation.

3. **RTE-02: Auto-create Linear team for new clients**
   - What we know: Linear API supports team creation. The existing `linear_client.py` can search teams by name.
   - What's unclear: Whether auto-creating teams is desirable (risk of garbage teams from misdetection). What API key permissions are needed.
   - Recommendation: Implement as a "suggest new project" flow: detect the gap, log intent, but require human confirmation before creating. Add a "pending_project_creation" state to the WebSocket events.

4. **Live transcript feed into copilot engine**
   - What we know: Meeting-watcher v2 polls `get_live_transcript(meeting_id)` every 30 seconds. The copilot engine currently has no direct Fireflies integration for live transcripts.
   - What's unclear: How transcript data flows from Fireflies to the copilot engine for Phase 3. Phase 6 bridges meeting-watcher v2 to copilot engine.
   - Recommendation: For Phase 3, build the intent detector to accept transcript chunks via a POST endpoint (`/api/transcript`) or WebSocket message. This decouples intent detection from the transcript source. In Phase 6, the bridge wires meeting-watcher v2's polling to this endpoint.

5. **LiteLLM Router behavior when model_list is empty**
   - What we know: If no API keys are configured, the model_list would be empty.
   - What's unclear: Whether Router raises on construction or on first call with empty list.
   - Recommendation: Check that at least one model is configured at startup. Fall through to keyword classifier if Router has no models.

## Sources

### Primary (HIGH confidence)
- LiteLLM structured outputs docs: https://docs.litellm.ai/docs/completion/json_mode -- Pydantic response_format, JSON mode, provider differences
- LiteLLM Router docs: https://docs.litellm.ai/docs/routing -- Router constructor, model_list, order, fallbacks, cooldown
- LiteLLM function calling docs: https://docs.litellm.ai/docs/completion/function_call -- tool definitions, provider support checks
- Existing codebase: `engine/context/linear_client.py` -- Linear GraphQL patterns with parameterized variables
- Existing codebase: `engine/context/models.py` -- UnifiedMeetingContext with to_classifier_prompt() method
- Existing codebase: `engine/models.py` -- MeetingState, AgentStatus, TaskStatus, WebSocket event models
- Existing codebase: `engine/ws_handler.py` -- ConnectionManager with broadcast pattern
- Existing codebase: `engine/requirements.txt` -- litellm already listed as dependency
- Existing codebase: `scripts/meeting-watcher.py` -- Full working classification chain, keyword fallback, Linear issue creation
- God CLI reference: `/opt/agency-workspace/god-mcp/GOD-CLI-REFERENCE.md` -- fleet commands, agent listing
- Verified: `claude -p "test" --print` works on VPS (exit code 0, returns response)

### Secondary (MEDIUM confidence)
- Linear GraphQL API: https://linear.app/developers/graphql -- issueCreate mutation with teamId, projectId, priority, labelIds
- Fleet roster: `/opt/agency-workspace/fleet-shared/context/fleet-roster.md` -- SDK agents at /home/agent{N}/, PM2 fleet architecture
- LiteLLM Router architecture: https://docs.litellm.ai/docs/router_architecture -- retry and fallback flow

### Tertiary (LOW confidence)
- Gemini 2.0 Flash structured output reliability with complex Pydantic schemas (needs testing)
- Cross-user agent spawning on VPS (sudo/ssh did not work in testing)
- Linear API permissions for team/project creation (needs API key permission check)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- LiteLLM already in requirements.txt, all patterns verified in official docs
- Architecture: HIGH -- Follows existing codebase patterns (Pydantic, async, httpx, WebSocket broadcast)
- Intent schema: HIGH -- Based on meeting-watcher v2 categories upgraded with structured fields
- LiteLLM Router: HIGH -- Official docs provide exact configuration patterns
- Fleet agent spawning: MEDIUM -- Claude CLI verified working, but multi-user isolation untested
- Linear routing: HIGH -- Existing linear_client.py provides proven parameterized GraphQL patterns
- Pitfalls: HIGH -- Derived from actual codebase analysis and known constraints ($0 budget, zero Anthropic credits)

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (30 days -- stack is stable, LiteLLM API unlikely to change significantly)
