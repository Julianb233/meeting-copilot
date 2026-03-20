"""Fireflies GraphQL API loader — fetches past meeting transcripts for attendees."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import BaseModel, Field

from .. import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TranscriptSummary(BaseModel):
    """Summary of a single Fireflies transcript."""

    id: str
    title: str
    date: datetime | None = None
    duration: float | None = None  # minutes
    summary: str | None = None
    action_items: list[str] = Field(default_factory=list)
    participants: list[str] = Field(default_factory=list)
    transcript_url: str | None = None


# ---------------------------------------------------------------------------
# GraphQL query
# ---------------------------------------------------------------------------

_TRANSCRIPTS_QUERY = """
query RecentTranscripts($limit: Int) {
  transcripts(limit: $limit) {
    id
    title
    date
    duration
    summary {
      overview
      action_items
    }
    participants
    transcript_url
  }
}
"""

FIREFLIES_ENDPOINT = "https://api.fireflies.dev/graphql"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_action_items(raw: Any) -> list[str]:
    """Parse action_items which may be a string (newline-delimited) or list."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, str):
        return [line.strip() for line in raw.splitlines() if line.strip()]
    return []


def _participant_matches(participants: list[str], email: str) -> bool:
    """Check if any participant string matches the given email (case-insensitive)."""
    email_lower = email.lower()
    for p in participants:
        if email_lower in p.lower():
            return True
    return False


def _parse_transcript(raw: dict[str, Any]) -> TranscriptSummary:
    """Convert a raw Fireflies transcript dict into a TranscriptSummary."""
    # date: Unix timestamp in milliseconds -> datetime
    date_val = raw.get("date")
    parsed_date: datetime | None = None
    if date_val is not None:
        try:
            parsed_date = datetime.fromtimestamp(int(date_val) / 1000, tz=timezone.utc)
        except (ValueError, TypeError, OSError):
            parsed_date = None

    # duration: seconds -> minutes
    duration_val = raw.get("duration")
    parsed_duration: float | None = None
    if duration_val is not None:
        try:
            parsed_duration = round(float(duration_val) / 60, 2)
        except (ValueError, TypeError):
            parsed_duration = None

    # summary fields
    summary_obj = raw.get("summary") or {}
    overview = summary_obj.get("overview") if isinstance(summary_obj, dict) else None
    action_items_raw = summary_obj.get("action_items") if isinstance(summary_obj, dict) else None

    return TranscriptSummary(
        id=raw.get("id", ""),
        title=raw.get("title", "Untitled"),
        date=parsed_date,
        duration=parsed_duration,
        summary=overview,
        action_items=_parse_action_items(action_items_raw),
        participants=raw.get("participants") or [],
        transcript_url=raw.get("transcript_url"),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def fetch_meeting_history(
    email: str,
    limit: int = 3,
) -> list[TranscriptSummary]:
    """Fetch the last *limit* Fireflies transcripts involving *email*.

    Returns an empty list (never raises) when the API key is missing,
    the API is unreachable, or any other error occurs.
    """
    api_key = config.FIREFLIES_API_KEY
    if not api_key:
        logger.warning("FIREFLIES_API_KEY not set — skipping transcript fetch")
        return []

    # Fetch more than we need so we can filter client-side
    fetch_limit = max(limit * 7, 20)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": _TRANSCRIPTS_QUERY,
        "variables": {"limit": fetch_limit},
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(FIREFLIES_ENDPOINT, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

    except httpx.TimeoutException:
        logger.error("Fireflies API request timed out for %s", email)
        return []
    except httpx.HTTPStatusError as exc:
        logger.error("Fireflies API HTTP error %s for %s", exc.response.status_code, email)
        return []
    except Exception:
        logger.exception("Unexpected error fetching Fireflies transcripts for %s", email)
        return []

    # Check for GraphQL-level errors
    if "errors" in data:
        logger.error("Fireflies GraphQL errors: %s", data["errors"])
        return []

    raw_transcripts: list[dict[str, Any]] = (data.get("data") or {}).get("transcripts") or []

    # Filter to transcripts where the email appears in participants
    matched: list[TranscriptSummary] = []
    for raw in raw_transcripts:
        participants = raw.get("participants") or []
        if _participant_matches(participants, email):
            matched.append(_parse_transcript(raw))
            if len(matched) >= limit:
                break

    if matched:
        logger.info("Found %d transcripts for %s", len(matched), email)
    else:
        logger.info("No transcripts found for %s", email)

    return matched


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    target_email = sys.argv[1] if len(sys.argv) > 1 else "test@example.com"
    results = asyncio.run(fetch_meeting_history(target_email))
    print(json.dumps([r.model_dump(mode="json") for r in results], indent=2, default=str))
