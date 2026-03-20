"""Project-aware meeting summary generator.

Extracts action items, decisions, and next steps from detected intents
and assembles them with attendee/project context into a structured summary.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from pydantic import BaseModel, Field

try:
    from context.models import UnifiedMeetingContext
    from intent.models import ActionType, Intent
except ImportError:
    from engine.context.models import UnifiedMeetingContext
    from engine.intent.models import ActionType, Intent

logger = logging.getLogger(__name__)

# Action types that represent action items.
ACTION_ITEM_TYPES: set[ActionType] = {
    ActionType.GENERAL_TASK,
    ActionType.BUILD_FEATURE,
    ActionType.FIX_BUG,
    ActionType.FOLLOW_UP,
    ActionType.CREATE_ISSUE,
}


class MeetingSummary(BaseModel):
    """Structured summary of a completed meeting."""

    meeting_title: str = ""
    meeting_type: str = "unknown"
    date: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    attendees: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    project_context: str | None = None
    summary_text: str = ""


def generate_meeting_summary(
    context: UnifiedMeetingContext,
    intents: list[Intent],
    active_project: str | None = None,
) -> MeetingSummary:
    """Generate a project-aware meeting summary from context and intents.

    Args:
        context: Unified meeting context with attendee info.
        intents: List of detected Intent objects from the meeting.
        active_project: Currently active project name (if any).

    Returns:
        MeetingSummary with extracted action items, decisions, topics, etc.
    """
    # Extract action items
    action_items: list[str] = []
    for intent in intents:
        if intent.action_type in ACTION_ITEM_TYPES and intent.target:
            action_items.append(intent.target)

    # Extract decisions
    decisions: list[str] = []
    for intent in intents:
        if intent.action_type == ActionType.DECISION and intent.target:
            decisions.append(intent.target)

    # Next steps: urgent intents requiring agent work
    next_steps: list[str] = []
    for intent in intents:
        if intent.urgency in ("now", "soon") and intent.requires_agent and intent.target:
            next_steps.append(intent.target)

    # Topics: unique project names from intents + active_project
    topic_set: set[str] = set()
    for intent in intents:
        if intent.project:
            topic_set.add(intent.project)
    if active_project:
        topic_set.add(active_project)
    topics = sorted(topic_set)

    # Project context from attendee Linear projects
    linear_projects: set[str] = set()
    for att in context.attendees:
        for proj in att.linear_projects:
            linear_projects.add(proj.name)
    project_context = ", ".join(sorted(linear_projects)) if linear_projects else None

    # Attendees: names or emails
    attendees: list[str] = []
    for att in context.attendees:
        name = att.identity.name or att.identity.email
        attendees.append(name)

    # Meeting metadata
    meeting_title = context.meeting_title or "Untitled Meeting"
    meeting_type = context.meeting_type or "unknown"

    # Build narrative summary text
    summary_lines = [
        f"Meeting: {meeting_title}",
        f"Type: {meeting_type}",
        f"Attendees: {', '.join(attendees) if attendees else 'N/A'}",
        f"Projects: {', '.join(topics) if topics else 'N/A'}",
    ]

    if action_items:
        summary_lines.append("")
        summary_lines.append("Action Items:")
        for item in action_items:
            summary_lines.append(f"- {item}")

    if decisions:
        summary_lines.append("")
        summary_lines.append("Decisions:")
        for decision in decisions:
            summary_lines.append(f"- {decision}")

    if next_steps:
        summary_lines.append("")
        summary_lines.append("Next Steps:")
        for step in next_steps:
            summary_lines.append(f"- {step}")

    summary_text = "\n".join(summary_lines)

    return MeetingSummary(
        meeting_title=meeting_title,
        meeting_type=meeting_type,
        attendees=attendees,
        action_items=action_items,
        decisions=decisions,
        next_steps=next_steps,
        topics=topics,
        project_context=project_context,
        summary_text=summary_text,
    )
