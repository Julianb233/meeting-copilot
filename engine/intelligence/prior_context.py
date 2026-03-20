"""Prior meeting context extractor — surfaces "Last time you discussed..." context.

Processes Fireflies TranscriptSummary objects from attendee meeting histories
to extract prior topics, open action items, and last meeting metadata.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from context.fireflies import TranscriptSummary
    from context.models import AttendeeContext

logger = logging.getLogger(__name__)


class PriorMeetingContext(BaseModel):
    """Structured prior meeting context for LLM prompt injection."""

    last_meeting_date: datetime | None = None
    last_meeting_title: str | None = None
    topics_discussed: list[str] = Field(default_factory=list)
    open_action_items: list[str] = Field(default_factory=list)
    total_prior_meetings: int = 0

    def to_prompt_text(self) -> str:
        """Generate human-readable prior context summary for LLM prompts."""
        if self.total_prior_meetings == 0:
            return "No prior meeting history found."

        lines: list[str] = []

        # Header with last meeting info
        date_str = (
            self.last_meeting_date.strftime("%Y-%m-%d")
            if self.last_meeting_date
            else "unknown date"
        )
        title = self.last_meeting_title or "a previous meeting"
        lines.append(
            f"Last meeting: {title} on {date_str} "
            f"({self.total_prior_meetings} prior meeting(s) total)"
        )

        # Topics
        if self.topics_discussed:
            lines.append(
                "Topics discussed: " + ", ".join(self.topics_discussed)
            )

        # Open action items
        if self.open_action_items:
            lines.append("Open items from previous meetings:")
            for item in self.open_action_items:
                lines.append(f"  - {item}")

        return "\n".join(lines)


def _truncate_to_sentence(text: str, max_chars: int = 120) -> str:
    """Truncate text to first sentence or max_chars, whichever is shorter."""
    # Find first sentence boundary
    for sep in (". ", "! ", "? "):
        idx = text.find(sep)
        if 0 < idx < max_chars:
            return text[: idx + 1]
    # No sentence boundary found — truncate at max_chars
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def extract_prior_context(
    attendees: list[AttendeeContext],
) -> PriorMeetingContext:
    """Extract prior meeting context from attendee Fireflies transcript histories.

    Collects all TranscriptSummary objects across attendees, deduplicates by
    transcript ID, and extracts topics + action items.
    """
    # Collect and deduplicate transcripts by ID
    seen_ids: set[str] = set()
    unique_transcripts: list[TranscriptSummary] = []

    for att in attendees:
        for ts in att.meeting_history:
            if ts.id not in seen_ids:
                seen_ids.add(ts.id)
                unique_transcripts.append(ts)

    if not unique_transcripts:
        logger.info("No prior meeting transcripts found for attendees")
        return PriorMeetingContext()

    # Sort by date descending (most recent first), None dates last
    unique_transcripts.sort(
        key=lambda t: t.date or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    # Extract topics from summary/overview fields (deduplicated)
    seen_topics: set[str] = set()
    topics: list[str] = []
    for ts in unique_transcripts:
        if ts.summary:
            topic = _truncate_to_sentence(ts.summary)
            topic_key = topic.lower().strip()
            if topic_key not in seen_topics:
                seen_topics.add(topic_key)
                topics.append(topic)

    # Extract action items (deduplicated by normalized text)
    seen_items: set[str] = set()
    action_items: list[str] = []
    for ts in unique_transcripts:
        for item in ts.action_items:
            normalized = item.lower().strip()
            if normalized and normalized not in seen_items:
                seen_items.add(normalized)
                action_items.append(item.strip())

    # Most recent transcript metadata
    most_recent = unique_transcripts[0]

    result = PriorMeetingContext(
        last_meeting_date=most_recent.date,
        last_meeting_title=most_recent.title,
        topics_discussed=topics,
        open_action_items=action_items,
        total_prior_meetings=len(unique_transcripts),
    )

    logger.info(
        "Extracted prior context: %d meetings, %d topics, %d action items",
        result.total_prior_meetings,
        len(result.topics_discussed),
        len(result.open_action_items),
    )
    return result


if __name__ == "__main__":
    from context.contacts import AttendeeIdentity
    from context.fireflies import TranscriptSummary
    from context.models import AttendeeContext

    # Mock data for testing
    ts1 = TranscriptSummary(
        id="t1",
        title="Sprint Review",
        date=datetime(2026, 3, 15, tzinfo=timezone.utc),
        summary="Discussed copilot progress and next steps",
        action_items=["Fix login bug", "Deploy staging"],
    )
    ts2 = TranscriptSummary(
        id="t2",
        title="Client Check-in",
        date=datetime(2026, 3, 10, tzinfo=timezone.utc),
        summary="Reviewed deliverables",
        action_items=["Send proposal"],
    )
    # Duplicate transcript across attendees (same id)
    ts3 = TranscriptSummary(
        id="t1",
        title="Sprint Review",
        date=datetime(2026, 3, 15, tzinfo=timezone.utc),
        summary="Discussed copilot progress and next steps",
        action_items=["Fix login bug", "Deploy staging"],
    )

    att1 = AttendeeContext(
        identity=AttendeeIdentity(email="alice@example.com"),
        meeting_history=[ts1, ts2],
    )
    att2 = AttendeeContext(
        identity=AttendeeIdentity(email="bob@example.com"),
        meeting_history=[ts3],
    )

    prior = extract_prior_context([att1, att2])

    # Verify deduplication
    assert prior.total_prior_meetings == 2, f"Expected 2, got {prior.total_prior_meetings}"
    assert prior.last_meeting_title == "Sprint Review"
    assert len(prior.open_action_items) == 3
    assert len(prior.topics_discussed) == 2

    print(prior.to_prompt_text())
    print()
    print("All assertions passed")
