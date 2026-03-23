"""Meeting classifier — determines internal vs client meetings from attendee emails.

Meetings with only @aiacrobatics.com attendees are internal (can reference all
projects, casual tone). Meetings with external domains are client meetings
(scoped to their project, professional tone).
"""

from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger(__name__)

# Domains considered "internal" to the agency.
INTERNAL_DOMAINS: set[str] = {"aiacrobatics.com"}

# Owner emails — always present, should not influence classification.
OWNER_EMAILS: set[str] = {
    "julianb233@gmail.com",
    "julian@aiacrobatics.com",
}


class MeetingType(str, Enum):
    """Classification of a meeting based on attendee composition."""

    INTERNAL = "internal"
    CLIENT = "client"
    UNKNOWN = "unknown"


def classify_meeting_type(attendee_emails: list[str]) -> MeetingType:
    """Classify a meeting as internal, client, or unknown.

    Logic:
      - Filter out owner emails (Julian is always present).
      - If no attendees remain: UNKNOWN (solo or empty).
      - If ALL remaining domains are internal: INTERNAL.
      - If ANY remaining domain is external: CLIENT.
    """
    if not attendee_emails:
        return MeetingType.UNKNOWN

    # Normalise and filter out owner
    remaining = [
        e.strip().lower()
        for e in attendee_emails
        if e.strip().lower() not in OWNER_EMAILS
    ]

    if not remaining:
        logger.debug("No non-owner attendees — classifying as UNKNOWN")
        return MeetingType.UNKNOWN

    # Extract domains
    domains = set()
    for email in remaining:
        parts = email.split("@")
        if len(parts) == 2:
            domains.add(parts[1])
        else:
            logger.warning("Malformed email skipped: %s", email)

    if not domains:
        return MeetingType.UNKNOWN

    # Check if all domains are internal
    if domains <= INTERNAL_DOMAINS:
        logger.debug("All domains internal %s — INTERNAL", domains)
        return MeetingType.INTERNAL

    logger.debug("External domains found %s — CLIENT", domains - INTERNAL_DOMAINS)
    return MeetingType.CLIENT


def get_client_domains(attendee_emails: list[str]) -> set[str]:
    """Return the set of non-internal, non-owner domains from attendee emails.

    Useful downstream for scoping context to the client's company.
    """
    result: set[str] = set()
    for email in attendee_emails:
        normed = email.strip().lower()
        if normed in OWNER_EMAILS:
            continue
        parts = normed.split("@")
        if len(parts) == 2:
            domain = parts[1]
            if domain not in INTERNAL_DOMAINS:
                result.add(domain)
    return result


if __name__ == "__main__":
    # Quick smoke test
    samples = [
        (["julian@aiacrobatics.com", "hitesh@aiacrobatics.com"], "INTERNAL"),
        (["julian@aiacrobatics.com", "sean@hafniafin.com"], "CLIENT"),
        (["julian@aiacrobatics.com"], "UNKNOWN (solo)"),
        ([], "UNKNOWN (empty)"),
        (
            ["julianb233@gmail.com", "julian@aiacrobatics.com", "bob@external.co"],
            "CLIENT",
        ),
    ]
    for emails, label in samples:
        result = classify_meeting_type(emails)
        client = get_client_domains(emails)
        print(f"{label:20s} => {result.value:8s}  client_domains={client}  emails={emails}")
