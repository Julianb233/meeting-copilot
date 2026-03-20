"""Context assembler — merges all data sources into a unified meeting context.

Orchestrates all 4 data loaders (contacts, fireflies, linear, profiles) in a
two-phase parallel fan-out and returns a single UnifiedMeetingContext object
ready for LLM consumption.

Phase A (parallel): identity resolution + Fireflies history
Phase B (parallel, after A): Linear projects + client profiles (needs company from A)
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from context.contacts import AttendeeIdentity, resolve_attendees
from context.fireflies import TranscriptSummary, fetch_meeting_history
from context.linear_client import LinearIssue, LinearProject, fetch_linear_projects
from context.profiles import ClientProfile, load_client_profile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Unified context models
# ---------------------------------------------------------------------------


class AttendeeContext(BaseModel):
    """Complete context for a single meeting attendee."""

    identity: AttendeeIdentity
    meeting_history: list[TranscriptSummary] = Field(default_factory=list)
    linear_projects: list[LinearProject] = Field(default_factory=list)
    client_profile: ClientProfile | None = None


class UnifiedMeetingContext(BaseModel):
    """Full assembled context for a meeting, ready for LLM consumption."""

    meeting_title: str | None = None
    assembled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    load_time_seconds: float = 0.0
    attendees: list[AttendeeContext] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    def to_classifier_prompt(self) -> str:
        """Produce readable text summary for LLM context injection."""
        lines: list[str] = []
        if self.meeting_title:
            lines.append(f"Meeting: {self.meeting_title}")
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

            lines.append("")

        if self.errors:
            lines.append(f"Context errors ({len(self.errors)}):")
            for err in self.errors:
                lines.append(f"  - {err}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Assembly function
# ---------------------------------------------------------------------------


async def assemble_meeting_context(
    emails: list[str],
    meeting_title: str | None = None,
    display_names: dict[str, str] | None = None,
) -> UnifiedMeetingContext:
    """Assemble unified context for all meeting attendees.

    Two-phase parallel fan-out:
      Phase A: resolve identities + fetch Fireflies history (parallel)
      Phase B: fetch Linear projects + load client profiles (parallel, needs company from A)

    Any individual loader failure is captured in errors, not raised.
    """
    start = time.monotonic()
    errors: list[str] = []

    # ------------------------------------------------------------------
    # Phase A: identity resolution + Fireflies history in parallel
    # ------------------------------------------------------------------
    identity_coro = resolve_attendees(emails)
    history_coros = [fetch_meeting_history(e) for e in emails]

    phase_a_results = await asyncio.gather(
        identity_coro, *history_coros, return_exceptions=True
    )

    # Parse Phase A results
    raw_identities = phase_a_results[0]
    raw_histories = phase_a_results[1:]

    # Handle identity resolution failure
    if isinstance(raw_identities, BaseException):
        errors.append(f"Identity resolution failed: {raw_identities}")
        logger.error("Identity resolution failed: %s", raw_identities)
        identities = [
            AttendeeIdentity(email=e, source="email_only") for e in emails
        ]
    else:
        identities = raw_identities

    # Handle individual history failures
    histories: list[list[TranscriptSummary]] = []
    for i, result in enumerate(raw_histories):
        if isinstance(result, BaseException):
            errors.append(f"Fireflies history failed for {emails[i]}: {result}")
            logger.error("Fireflies history failed for %s: %s", emails[i], result)
            histories.append([])
        else:
            histories.append(result)

    # ------------------------------------------------------------------
    # Phase B: Linear projects + client profiles (needs company from A)
    # ------------------------------------------------------------------
    phase_b_coros: list = []
    for email, identity in zip(emails, identities):
        company = identity.company or ""
        # Linear: search by company name
        phase_b_coros.append(
            fetch_linear_projects(company) if company else _empty_linear()
        )
        # Profile: search by email and company
        phase_b_coros.append(
            load_client_profile(email=email, company=company or None)
        )

    phase_b_results = await asyncio.gather(*phase_b_coros, return_exceptions=True)

    # ------------------------------------------------------------------
    # Assemble per-attendee context
    # ------------------------------------------------------------------
    attendee_contexts: list[AttendeeContext] = []
    for i, (email, identity) in enumerate(zip(emails, identities)):
        # Phase B results: every 2 entries = (linear, profile) per attendee
        linear_idx = i * 2
        profile_idx = i * 2 + 1

        # Linear projects
        raw_linear = phase_b_results[linear_idx]
        if isinstance(raw_linear, BaseException):
            errors.append(f"Linear lookup failed for {email}: {raw_linear}")
            logger.error("Linear lookup failed for %s: %s", email, raw_linear)
            linear_projects: list[LinearProject] = []
        else:
            linear_projects = raw_linear

        # Client profile
        raw_profile = phase_b_results[profile_idx]
        if isinstance(raw_profile, BaseException):
            errors.append(f"Profile lookup failed for {email}: {raw_profile}")
            logger.error("Profile lookup failed for %s: %s", email, raw_profile)
            client_profile = None
        else:
            client_profile = raw_profile

        attendee_contexts.append(
            AttendeeContext(
                identity=identity,
                meeting_history=histories[i],
                linear_projects=linear_projects,
                client_profile=client_profile,
            )
        )

    load_time = time.monotonic() - start
    logger.info(
        "Context assembled for %d attendees in %.1fs (%d errors)",
        len(attendee_contexts),
        load_time,
        len(errors),
    )

    return UnifiedMeetingContext(
        meeting_title=meeting_title,
        load_time_seconds=round(load_time, 2),
        attendees=attendee_contexts,
        errors=errors,
    )


async def _empty_linear() -> list[LinearProject]:
    """Return empty list for attendees without a known company."""
    return []


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    test_emails = sys.argv[1:] if len(sys.argv) > 1 else ["sean@hafniafin.com"]

    async def _main() -> None:
        ctx = await assemble_meeting_context(test_emails, meeting_title="Test Meeting")
        print(ctx.model_dump_json(indent=2))
        print("\n" + "=" * 60)
        print("CLASSIFIER PROMPT:")
        print("=" * 60)
        print(ctx.to_classifier_prompt())

    asyncio.run(_main())
