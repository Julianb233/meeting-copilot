"""Prompt templates for classification and intent extraction."""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Stage 1: Batch classification prompt
# ---------------------------------------------------------------------------

CLASSIFY_BATCH_PROMPT = """\
You are a meeting transcript classifier. Classify each sentence into EXACTLY one category:

- ACTION_ITEM: Tasks, things to build/create/fix/deploy, assignments
- DECISION: Agreements, choices made, plans confirmed
- FOLLOW_UP: Follow-up actions, reach-out tasks, emails to send
- QUESTION: Direct questions (contains '?')
- INFO: General conversation, filler, context, opinions

Return a JSON array of objects with "index" and "classification" keys.
Example: [{"index": 0, "classification": "ACTION_ITEM"}, {"index": 1, "classification": "INFO"}]

Return ONLY valid JSON, no markdown formatting.

Sentences:
{sentences}"""


def format_classify_prompt(sentences: list[dict]) -> str:
    """Format sentences for batch classification.

    Each dict must have "text" and "speaker" (or "speaker_name").
    """
    lines: list[str] = []
    for i, s in enumerate(sentences):
        speaker = s.get("speaker_name", s.get("speaker", "Unknown"))
        lines.append(f'[{i}] {speaker}: {s["text"]}')
    return CLASSIFY_BATCH_PROMPT.format(sentences="\n".join(lines))


# ---------------------------------------------------------------------------
# Stage 2: Structured intent extraction prompt
# ---------------------------------------------------------------------------

EXTRACT_INTENTS_PROMPT = """\
You are an intent extraction engine for a live meeting transcript.
Given actionable transcript lines, extract structured intents.

Known projects: {known_projects}
Attendees: {attendee_names}

Available action_type values:
  create_issue, build_feature, fix_bug, research, send_email,
  create_proposal, schedule_meeting, check_domain, deploy,
  decision, follow_up, general_task

Urgency rules:
- "now": speaker says immediately, right now, ASAP, during this call
- "later": explicitly deferred, backlog, next sprint, someday
- "soon": everything else (default)

requires_agent rules:
- true for: build_feature, fix_bug, research, deploy, check_domain, create_proposal
- false for: create_issue, decision, follow_up, send_email, schedule_meeting, general_task

Return a JSON array of intent objects. Each object has:
  action_type, target, urgency, project (from known projects or null),
  assignee (from attendees or null), details, confidence (0.0-1.0),
  source_text, speaker, requires_agent

Only extract genuine intents. Be precise with action_type selection.

Return ONLY valid JSON array, no markdown formatting.

Transcript lines:
{sentences}"""


def format_extract_prompt(
    sentences: list[dict],
    known_projects: list[str],
    attendee_names: list[str],
) -> str:
    """Format actionable sentences for structured intent extraction."""
    lines: list[str] = []
    for s in sentences:
        speaker = s.get("speaker_name", s.get("speaker", "Unknown"))
        lines.append(f'{speaker}: {s["text"]}')

    projects_str = ", ".join(known_projects) if known_projects else "none"
    attendees_str = ", ".join(attendee_names) if attendee_names else "none"

    return EXTRACT_INTENTS_PROMPT.format(
        known_projects=projects_str,
        attendee_names=attendees_str,
        sentences="\n".join(lines),
    )


# ---------------------------------------------------------------------------
# Keyword fallback classifier (ported from meeting-watcher.py lines 335-361)
# ---------------------------------------------------------------------------

_ACTION_KW = [
    "we need to", "let's build", "let's create", "let's set up",
    "i'll handle", "make sure to", "action item", "task:",
    "set up a", "schedule a", "please create", "implement this", "deploy",
]
_DECISION_KW = [
    "we decided", "let's go with", "the plan is", "agreed on",
    "going forward", "we're going to",
]
_FOLLOWUP_KW = [
    "follow up with", "send them", "email them",
    "reach out to", "get back to", "circle back",
]
_QUESTION_KW = ["?"]


def classify_keywords(text: str) -> str:
    """Classify a single sentence using keyword matching.

    Ported from meeting-watcher.py — same keyword lists, same logic.
    """
    t = text.lower().strip()
    if not t or len(t) < 10:
        return "INFO"

    for kw in _ACTION_KW:
        if kw in t:
            return "ACTION_ITEM"
    for kw in _DECISION_KW:
        if kw in t:
            return "DECISION"
    for kw in _FOLLOWUP_KW:
        if kw in t:
            return "FOLLOW_UP"
    for kw in _QUESTION_KW:
        if kw in t:
            return "QUESTION"
    return "INFO"
