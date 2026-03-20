"""Client profile loader from Obsidian vault and client-profiles directory.

Searches two filesystem locations to find rich context about meeting attendees:
1. /opt/agency-workspace/client-profiles/ — detailed communication profiles
2. /opt/agency-workspace/obsidian-vault/Contacts/ — Obsidian contact notes

Returns a ClientProfile with communication style, preferences, and raw markdown
content for LLM context injection.
"""

from __future__ import annotations

import asyncio
import glob
import logging
import sys
from pathlib import Path

import yaml
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# --- Constants ---

CLIENT_PROFILES_DIR = "/opt/agency-workspace/client-profiles"
OBSIDIAN_CONTACTS_DIR = "/opt/agency-workspace/obsidian-vault/Contacts"

# Files to skip in client-profiles directory
_SKIP_FILES = {"README.md", "CLIENT-PORTAL-V2-PLAN.md"}
_SKIP_DIRS = {"templates", "clients"}

# Max raw content length to keep context manageable for LLM
_MAX_RAW_CONTENT = 2000


# --- Model ---

class ClientProfile(BaseModel):
    """Rich client profile for meeting context."""

    slug: str  # filename without .md
    name: str
    email: str | None = None
    company: str | None = None
    role: str | None = None
    relationship: str | None = None  # "Client", "Partner", etc.
    communication_style: str | None = None
    formality: str | None = None
    status: str | None = None  # "active", etc.
    raw_content: str = ""  # full markdown for LLM context
    source: str = "client_profiles"  # or "obsidian_contacts"


# --- Internal helpers ---

def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown text.

    Returns (frontmatter_dict, body_text). If no frontmatter found,
    returns ({}, full_text).
    """
    stripped = text.strip()
    if not stripped.startswith("---"):
        return {}, text

    # Find the closing ---
    end_idx = stripped.find("---", 3)
    if end_idx == -1:
        return {}, text

    yaml_block = stripped[3:end_idx].strip()
    body = stripped[end_idx + 3:].strip()

    try:
        frontmatter = yaml.safe_load(yaml_block)
        if not isinstance(frontmatter, dict):
            return {}, text
        return frontmatter, body
    except yaml.YAMLError:
        logger.warning("Failed to parse YAML frontmatter")
        return {}, text


def _match_email_in_text(text: str, email: str) -> bool:
    """Case-insensitive email search in full text content."""
    return email.lower() in text.lower()


def _match_company(frontmatter: dict, body: str, company: str) -> bool:
    """Match company name against frontmatter fields and body content."""
    company_lower = company.lower()

    # Check frontmatter fields: client, company, name
    for key in ("client", "company", "name"):
        val = frontmatter.get(key)
        if val and company_lower in str(val).lower():
            return True

    # Check the slug field
    slug = frontmatter.get("slug", "")
    if slug and company_lower.replace(" ", "-").lower() in slug.lower():
        return True

    return False


def _profile_from_client_profiles(
    filepath: Path, frontmatter: dict, body: str
) -> ClientProfile:
    """Build ClientProfile from a client-profiles/*.md file."""
    slug = frontmatter.get("slug", filepath.stem)
    name = frontmatter.get("client", slug)

    # Extract email from body content (look for email pattern in Contact section)
    email = None
    for line in body.split("\n"):
        if "@" in line and "**Primary:**" in line:
            # Extract email from "**Primary:** Name (email@domain.com)"
            start = line.find("(")
            end = line.find(")")
            if start != -1 and end != -1:
                email = line[start + 1 : end].strip()
                break

    # Extract communication style from the table
    comm_style = None
    formality = None
    for line in body.split("\n"):
        line_stripped = line.strip()
        if "| Tone |" in line_stripped:
            parts = line_stripped.split("|")
            if len(parts) >= 3:
                comm_style = parts[2].strip()
        elif "| Formality |" in line_stripped:
            parts = line_stripped.split("|")
            if len(parts) >= 3:
                formality = parts[2].strip()

    return ClientProfile(
        slug=slug,
        name=name,
        email=email,
        company=name,  # client field is effectively the company/client name
        role=None,
        relationship="Client" if frontmatter.get("status") == "active" else None,
        communication_style=comm_style,
        formality=formality,
        status=frontmatter.get("status"),
        raw_content=body[:_MAX_RAW_CONTENT],
        source="client_profiles",
    )


def _profile_from_obsidian(
    filepath: Path, frontmatter: dict, body: str
) -> ClientProfile:
    """Build ClientProfile from an Obsidian vault contact file."""
    return ClientProfile(
        slug=filepath.stem.lower().replace(" ", "-"),
        name=frontmatter.get("name", filepath.stem),
        email=frontmatter.get("email"),
        company=frontmatter.get("company"),
        role=frontmatter.get("role"),
        relationship=frontmatter.get("relationship"),
        communication_style=frontmatter.get("communication_style"),
        formality=frontmatter.get("formality"),
        status="active" if frontmatter.get("is_client") else None,
        raw_content=body[:_MAX_RAW_CONTENT],
        source="obsidian_contacts",
    )


# --- Search functions ---

def _search_client_profiles(
    email: str | None = None, company: str | None = None
) -> ClientProfile | None:
    """Search /opt/agency-workspace/client-profiles/ for a match."""
    profiles_dir = Path(CLIENT_PROFILES_DIR)
    if not profiles_dir.is_dir():
        logger.debug("Client profiles directory not found: %s", CLIENT_PROFILES_DIR)
        return None

    for filepath in sorted(profiles_dir.glob("*.md")):
        # Skip non-profile files
        if filepath.name in _SKIP_FILES:
            continue
        if any(skip in filepath.parts for skip in _SKIP_DIRS):
            continue

        try:
            text = filepath.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Failed to read %s: %s", filepath, exc)
            continue

        frontmatter, body = _parse_frontmatter(text)

        # Match by email
        if email and _match_email_in_text(text, email):
            profile = _profile_from_client_profiles(filepath, frontmatter, body)
            logger.info(
                "Loaded client profile for %s from client_profiles", profile.name
            )
            return profile

        # Match by company
        if company and _match_company(frontmatter, body, company):
            profile = _profile_from_client_profiles(filepath, frontmatter, body)
            logger.info(
                "Loaded client profile for %s from client_profiles", profile.name
            )
            return profile

    return None


def _search_obsidian_contacts(
    email: str | None = None, company: str | None = None
) -> ClientProfile | None:
    """Search /opt/agency-workspace/obsidian-vault/Contacts/ for a match."""
    contacts_dir = Path(OBSIDIAN_CONTACTS_DIR)
    if not contacts_dir.is_dir():
        logger.debug("Obsidian contacts directory not found: %s", OBSIDIAN_CONTACTS_DIR)
        return None

    for filepath in sorted(contacts_dir.glob("*.md")):
        try:
            text = filepath.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Failed to read %s: %s", filepath, exc)
            continue

        frontmatter, body = _parse_frontmatter(text)

        # Match by email (frontmatter field, case-insensitive)
        if email:
            fm_email = frontmatter.get("email", "")
            if fm_email and fm_email.lower() == email.lower():
                profile = _profile_from_obsidian(filepath, frontmatter, body)
                logger.info(
                    "Loaded client profile for %s from obsidian_contacts",
                    profile.name,
                )
                return profile

        # Match by company
        if company:
            fm_company = frontmatter.get("company", "")
            if fm_company and company.lower() in fm_company.lower():
                profile = _profile_from_obsidian(filepath, frontmatter, body)
                logger.info(
                    "Loaded client profile for %s from obsidian_contacts",
                    profile.name,
                )
                return profile

    return None


# --- Public API ---

async def load_client_profile(
    email: str | None = None, company: str | None = None
) -> ClientProfile | None:
    """Load a client profile by email or company name.

    Searches client-profiles directory first (richer data), then falls back
    to Obsidian vault contacts. Returns None if no match found.

    Args:
        email: Email address to search for (case-insensitive).
        company: Company name to search for (partial match).

    Returns:
        ClientProfile if found, None otherwise.
    """
    if not email and not company:
        logger.warning("load_client_profile called with no email or company")
        return None

    # Search client-profiles first (richer data)
    result = await asyncio.to_thread(_search_client_profiles, email, company)
    if result:
        return result

    # Fall back to Obsidian contacts
    result = await asyncio.to_thread(_search_obsidian_contacts, email, company)
    if result:
        return result

    logger.info(
        "No client profile found for email=%s company=%s", email, company
    )
    return None


# --- CLI entry point ---

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    _email: str | None = None
    _company: str | None = None

    args = sys.argv[1:]
    if "--company" in args:
        idx = args.index("--company")
        if idx + 1 < len(args):
            _company = args[idx + 1]
            args = args[:idx] + args[idx + 2 :]

    if args:
        _email = args[0]

    # Default for quick testing
    if not _email and not _company:
        _email = "brendan@acrepartner.com"

    profile = asyncio.run(load_client_profile(email=_email, company=_company))

    if profile:
        print(profile.model_dump_json(indent=2))
    else:
        print("None found")
