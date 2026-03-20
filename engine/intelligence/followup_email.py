"""Post-meeting follow-up email drafter and sender.

Drafts tone-appropriate follow-up emails (internal vs client) and sends
them via the gws CLI tool (Google Workspace).
"""

from __future__ import annotations

import asyncio
import logging

from pydantic import BaseModel

logger = logging.getLogger(__name__)

GWS_BIN = "/usr/local/bin/gws"
SUBPROCESS_TIMEOUT = 30  # seconds

# Owner emails — always filtered from recipients.
OWNER_EMAILS: set[str] = {
    "julianb233@gmail.com",
    "julian@aiacrobatics.com",
}


class FollowupEmail(BaseModel):
    """A drafted follow-up email ready to send."""

    to: list[str]
    subject: str
    body: str
    meeting_title: str
    meeting_type: str  # "internal" or "client"


def _get_first_name(email: str, attendee_names: dict[str, str] | None = None) -> str:
    """Extract first name from attendee_names dict or email username."""
    if attendee_names and email in attendee_names:
        full_name = attendee_names[email]
        return full_name.split()[0] if full_name else email.split("@")[0]
    return email.split("@")[0]


def draft_followup_email(
    meeting_title: str,
    meeting_type: str,
    attendee_emails: list[str],
    action_items: list[str],
    decisions: list[str],
    next_steps: list[str],
    attendee_names: dict[str, str] | None = None,
) -> FollowupEmail:
    """Draft a follow-up email with tone adjusted for meeting type.

    Args:
        meeting_title: Title of the meeting.
        meeting_type: "internal" or "client".
        attendee_emails: All attendee emails (Julian filtered out).
        action_items: List of action item strings.
        decisions: List of decision strings.
        next_steps: List of next step strings.
        attendee_names: Optional mapping of email -> display name.

    Returns:
        FollowupEmail ready to send.
    """
    # Filter out Julian's emails
    recipients = [
        e.strip().lower()
        for e in attendee_emails
        if e.strip().lower() not in OWNER_EMAILS
    ]

    # Build first names for greeting
    first_names = [_get_first_name(e, attendee_names) for e in recipients]
    greeting_names = ", ".join(first_names) if first_names else "team"

    if meeting_type == "client":
        subject = f"Follow-up: {meeting_title}"
        body = _build_client_body(meeting_title, greeting_names, action_items, decisions, next_steps)
    else:
        subject = f"Notes: {meeting_title}"
        body = _build_internal_body(meeting_title, greeting_names, action_items, decisions, next_steps)

    return FollowupEmail(
        to=recipients,
        subject=subject,
        body=body,
        meeting_title=meeting_title,
        meeting_type=meeting_type,
    )


def _build_client_body(
    meeting_title: str,
    greeting_names: str,
    action_items: list[str],
    decisions: list[str],
    next_steps: list[str],
) -> str:
    """Build professional-tone email body for client meetings."""
    lines = [f"Hi {greeting_names},", "", "Thank you for meeting today. Here's a summary of what we covered:"]

    if action_items:
        lines.append("")
        lines.append("Action Items:")
        for item in action_items:
            lines.append(f"- {item}")

    if decisions:
        lines.append("")
        lines.append("Decisions Made:")
        for decision in decisions:
            lines.append(f"- {decision}")

    if next_steps:
        lines.append("")
        lines.append("Next Steps:")
        for step in next_steps:
            lines.append(f"- {step}")

    lines.append("")
    lines.append("Please let me know if I missed anything or if you have any questions.")
    lines.append("")
    lines.append("Best,")
    lines.append("Julian")

    return "\n".join(lines)


def _build_internal_body(
    meeting_title: str,
    greeting_names: str,
    action_items: list[str],
    decisions: list[str],
    next_steps: list[str],
) -> str:
    """Build casual-tone email body for internal meetings."""
    lines = [f"Hey {greeting_names},", "", f"Quick recap from {meeting_title}:"]

    if action_items:
        lines.append("")
        lines.append("Action items:")
        for item in action_items:
            lines.append(f"- {item}")

    if decisions:
        lines.append("")
        lines.append("Decisions:")
        for decision in decisions:
            lines.append(f"- {decision}")

    if next_steps:
        lines.append("")
        lines.append("Next:")
        for step in next_steps:
            lines.append(f"- {step}")

    lines.append("")
    lines.append("— Julian")

    return "\n".join(lines)


async def send_followup_email(email: FollowupEmail) -> dict:
    """Send a follow-up email via gws CLI.

    Args:
        email: The drafted FollowupEmail to send.

    Returns:
        Dict with status ("sent" or "failed") and details.
    """
    if not email.to:
        logger.warning("No recipients for follow-up email — skipping send")
        return {"status": "skipped", "reason": "no recipients"}

    to_str = ",".join(email.to)
    try:
        proc = await asyncio.create_subprocess_exec(
            GWS_BIN, "gmail", "send",
            "--to", to_str,
            "--subject", email.subject,
            "--body", email.body,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=SUBPROCESS_TIMEOUT
        )

        if proc.returncode == 0:
            logger.info(
                "Follow-up email sent to %s (subject: %s)",
                to_str, email.subject,
            )
            return {
                "status": "sent",
                "to": email.to,
                "subject": email.subject,
            }
        else:
            error_msg = stderr.decode().strip() or stdout.decode().strip()
            logger.error("gws gmail send failed (rc=%d): %s", proc.returncode, error_msg)
            return {"status": "failed", "error": error_msg}

    except asyncio.TimeoutError:
        logger.error("gws gmail send timed out after %ds", SUBPROCESS_TIMEOUT)
        return {"status": "failed", "error": f"timeout after {SUBPROCESS_TIMEOUT}s"}
    except FileNotFoundError:
        logger.error("gws binary not found at %s", GWS_BIN)
        return {"status": "failed", "error": f"gws binary not found at {GWS_BIN}"}
    except Exception as exc:
        logger.error("Unexpected error sending follow-up email: %s", exc)
        return {"status": "failed", "error": str(exc)}


if __name__ == "__main__":
    # Quick smoke test — drafts sample emails without sending.
    print("=== Client Email ===")
    client = draft_followup_email(
        meeting_title="ACRE Project Review",
        meeting_type="client",
        attendee_emails=["julian@aiacrobatics.com", "sean@hafniafin.com"],
        action_items=["Fix login page", "Deploy to staging"],
        decisions=["Use Stripe for payments"],
        next_steps=["Review mockups by Friday"],
        attendee_names={"sean@hafniafin.com": "Sean"},
    )
    print(f"To: {client.to}")
    print(f"Subject: {client.subject}")
    print(f"Body:\n{client.body}")

    print("\n=== Internal Email ===")
    internal = draft_followup_email(
        meeting_title="Standup",
        meeting_type="internal",
        attendee_emails=["julian@aiacrobatics.com", "hitesh@aiacrobatics.com"],
        action_items=["Ship copilot v1"],
        decisions=[],
        next_steps=["Demo on Friday"],
    )
    print(f"To: {internal.to}")
    print(f"Subject: {internal.subject}")
    print(f"Body:\n{internal.body}")
