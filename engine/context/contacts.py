"""Google Contacts attendee identity resolver.

Resolves attendee emails to full identity profiles (name, company, title,
phone, photo) by shelling out to the `gws` CLI tool which handles OAuth
authentication for the Google People API.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys

from pydantic import BaseModel

logger = logging.getLogger(__name__)

GWS_BIN = "/usr/local/bin/gws"
SUBPROCESS_TIMEOUT = 10  # seconds
READ_MASK = "names,emailAddresses,organizations,phoneNumbers,photos"


class AttendeeIdentity(BaseModel):
    """Identity profile for a meeting attendee."""

    email: str
    name: str | None = None
    company: str | None = None
    title: str | None = None
    phone: str | None = None
    photo_url: str | None = None
    source: str = "google_contacts"  # or "email_only" if not found


def _extract_identity(email: str, data: dict) -> AttendeeIdentity:
    """Extract an AttendeeIdentity from gws searchContacts response JSON.

    Iterates results and finds the person whose emailAddresses contain
    the queried email (case-insensitive match).  Returns email_only
    fallback if no match is confirmed.
    """
    results = data.get("results", [])
    for result in results:
        person = result.get("person", {})
        addresses = person.get("emailAddresses", [])
        matched = any(
            addr.get("value", "").lower() == email.lower() for addr in addresses
        )
        if not matched:
            continue

        # Confirmed email match — extract fields
        name = None
        names = person.get("names", [])
        if names:
            name = names[0].get("displayName")

        company = None
        title = None
        orgs = person.get("organizations", [])
        if orgs:
            company = orgs[0].get("name")
            title = orgs[0].get("title")

        phone = None
        phones = person.get("phoneNumbers", [])
        if phones:
            phone = phones[0].get("value")

        photo_url = None
        photos = person.get("photos", [])
        if photos:
            # Skip default silhouette photos
            if not photos[0].get("default", False):
                photo_url = photos[0].get("url")

        return AttendeeIdentity(
            email=email,
            name=name,
            company=company,
            title=title,
            phone=phone,
            photo_url=photo_url,
            source="google_contacts",
        )

    # No confirmed email match in results
    return AttendeeIdentity(email=email, source="email_only")


async def resolve_attendee(email: str) -> AttendeeIdentity:
    """Resolve a single attendee email to an identity via Google Contacts.

    Shells out to ``gws people people searchContacts`` and parses the
    JSON response.  Returns an email_only fallback on any error or
    timeout.
    """
    params_json = json.dumps({
        "query": email,
        "readMask": READ_MASK,
    })

    try:
        proc = await asyncio.create_subprocess_exec(
            GWS_BIN,
            "people",
            "people",
            "searchContacts",
            "--params",
            params_json,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=SUBPROCESS_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.warning("gws searchContacts timed out for %s", email)
        return AttendeeIdentity(email=email, source="email_only")
    except OSError as exc:
        logger.error("Failed to run gws CLI: %s", exc)
        return AttendeeIdentity(email=email, source="email_only")

    if proc.returncode != 0:
        logger.warning(
            "gws searchContacts failed for %s (rc=%d): %s",
            email,
            proc.returncode,
            stderr.decode(errors="replace").strip(),
        )
        return AttendeeIdentity(email=email, source="email_only")

    raw = stdout.decode(errors="replace").strip()
    if not raw:
        logger.info("No contacts found for %s", email)
        return AttendeeIdentity(email=email, source="email_only")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse gws output for %s: %s", email, exc)
        return AttendeeIdentity(email=email, source="email_only")

    identity = _extract_identity(email, data)
    logger.info(
        "Resolved %s -> %s (source=%s)",
        email,
        identity.name or "(unknown)",
        identity.source,
    )
    return identity


async def resolve_attendees(emails: list[str]) -> list[AttendeeIdentity]:
    """Resolve multiple attendee emails in parallel.

    Returns results in the same order as the input email list.
    """
    if not emails:
        return []
    return list(await asyncio.gather(*[resolve_attendee(e) for e in emails]))


class ContactsLoader:
    """Convenience wrapper for use by the context engine pipeline.

    Provides a class-based interface around the module-level async
    functions for callers that prefer object-oriented usage.
    """

    async def resolve(self, email: str) -> AttendeeIdentity:
        """Resolve a single attendee email."""
        return await resolve_attendee(email)

    async def resolve_many(self, emails: list[str]) -> list[AttendeeIdentity]:
        """Resolve multiple attendee emails in parallel."""
        return await resolve_attendees(emails)


# ---------------------------------------------------------------------------
# CLI entry point for manual testing
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    test_email = sys.argv[1] if len(sys.argv) > 1 else "julianb233@gmail.com"

    async def _main() -> None:
        print(f"\n--- resolve_attendee({test_email!r}) ---")
        result = await resolve_attendee(test_email)
        print(result.model_dump_json(indent=2))

        unknown = "unknown-test-12345@nowhere.com"
        print(f"\n--- resolve_attendees([{test_email!r}, {unknown!r}]) ---")
        results = await resolve_attendees([test_email, unknown])
        for r in results:
            print(r.model_dump_json(indent=2))

    asyncio.run(_main())
