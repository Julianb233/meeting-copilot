"""Unified context models — single source of truth for all context Pydantic models.

This module re-exports loader-specific models and defines the aggregate models
(AttendeeContext, UnifiedMeetingContext) used by the assembler and API layer.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from context.contacts import AttendeeIdentity
from context.fireflies import TranscriptSummary
from context.linear_client import LinearIssue, LinearProject
from context.profiles import ClientProfile


class GitCommit(BaseModel):
    """A single git commit from a project repo."""

    sha: str
    author: str
    date: datetime
    message: str
    repo_name: str


class AttendeeContext(BaseModel):
    """Complete context for a single meeting attendee."""

    identity: AttendeeIdentity
    meeting_history: list[TranscriptSummary] = Field(default_factory=list)
    linear_projects: list[LinearProject] = Field(default_factory=list)
    client_profile: ClientProfile | None = None
    git_activity: list[GitCommit] = Field(default_factory=list)


class UnifiedMeetingContext(BaseModel):
    """Full assembled context for a meeting, ready for LLM consumption."""

    meeting_title: str | None = None
    meeting_type: str = "unknown"
    client_domains: list[str] = Field(default_factory=list)
    assembled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    load_time_seconds: float = 0.0
    attendees: list[AttendeeContext] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    def to_classifier_prompt(self) -> str:
        """Produce readable text summary for LLM context injection."""
        lines: list[str] = []
        if self.meeting_title:
            lines.append(f"Meeting: {self.meeting_title}")
        domain_info = ", ".join(self.client_domains) if self.client_domains else "N/A"
        lines.append(f"Meeting type: {self.meeting_type} ({domain_info})")
        lines.append(f"Attendees: {len(self.attendees)}")
        lines.append("")

        for att in self.attendees:
            ident = att.identity
            name = ident.name or ident.email
            lines.append(f"--- {name} ---")
            lines.append(f"  Email: {ident.email}")
            if ident.company:
                lines.append(f"  Company: {ident.company}")
            if ident.title:
                lines.append(f"  Title: {ident.title}")

            if att.meeting_history:
                lines.append(f"  Past meetings: {len(att.meeting_history)}")
                for hist in att.meeting_history[:3]:
                    date_str = hist.date.strftime("%Y-%m-%d") if hist.date else "unknown"
                    lines.append(f"    - {hist.title} ({date_str})")
                    if hist.summary:
                        lines.append(f"      Summary: {hist.summary[:120]}...")
                    if hist.action_items:
                        for item in hist.action_items[:3]:
                            lines.append(f"      Action: {item[:100]}")

            if att.linear_projects:
                lines.append(f"  Linear projects: {len(att.linear_projects)}")
                for proj in att.linear_projects:
                    lines.append(
                        f"    - {proj.name} ({proj.key}): "
                        f"{proj.issue_count} open issues"
                    )
                    for issue in proj.open_issues[:5]:
                        lines.append(
                            f"      [{issue.identifier}] {issue.title} "
                            f"({issue.status})"
                        )

            if att.client_profile:
                prof = att.client_profile
                lines.append(f"  Client profile: {prof.name}")
                if prof.communication_style:
                    lines.append(f"    Communication: {prof.communication_style}")
                if prof.formality:
                    lines.append(f"    Formality: {prof.formality}")
                if prof.relationship:
                    lines.append(f"    Relationship: {prof.relationship}")

            if att.git_activity:
                lines.append(
                    f"  Recent git activity "
                    f"({len(att.git_activity)} commits, last 7 days):"
                )
                for commit in att.git_activity[:5]:
                    date_str = commit.date.strftime("%Y-%m-%d")
                    lines.append(
                        f"    - {date_str} ({commit.repo_name}): "
                        f"{commit.message[:80]}"
                    )

            lines.append("")

        if self.errors:
            lines.append(f"Context errors ({len(self.errors)}):")
            for err in self.errors:
                lines.append(f"  - {err}")

        return "\n".join(lines)
