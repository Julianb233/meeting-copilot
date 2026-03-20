"""Git activity loader — fetch recent commits from repos associated with a client."""

from __future__ import annotations

import asyncio
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

from context.models import GitCommit

logger = logging.getLogger(__name__)

WORKSPACE_DIR = Path("/opt/agency-workspace")
CLIENT_PROFILES_DIR = WORKSPACE_DIR / "client-profiles"


def resolve_repo_path(repo_name: str) -> Path | None:
    """Resolve a repo name to its workspace path. Returns None if not found."""
    candidate = WORKSPACE_DIR / repo_name.strip()
    if candidate.is_dir() and (candidate / ".git").is_dir():
        return candidate
    return None


def _find_repos_for_client(slug: str) -> list[Path]:
    """Find repos associated with a client by reading their profile markdown."""
    profile_path = CLIENT_PROFILES_DIR / f"{slug}.md"
    if not profile_path.exists():
        logger.debug("No client profile at %s", profile_path)
        return []

    content = profile_path.read_text(errors="replace")

    # Try table format: | Repo(s) | meeting-copilot, client-portal |
    match = re.search(r"\|\s*Repo\(s\)\s*\|\s*(.+?)\s*\|", content)
    if not match:
        # Try bold format: **Repo(s):** meeting-copilot
        match = re.search(r"\*\*Repo\(s\):\*\*\s*(.+)", content)

    if not match:
        logger.debug("No Repo(s) field found in %s", profile_path)
        return []

    repo_names = [name.strip() for name in match.group(1).split(",")]
    repos: list[Path] = []
    for name in repo_names:
        path = resolve_repo_path(name)
        if path:
            repos.append(path)
        else:
            logger.debug("Repo '%s' not found in workspace", name)

    return repos


async def fetch_git_activity(
    slug: str | None = None,
    repo_paths: list[Path] | None = None,
    days: int = 7,
) -> list[GitCommit]:
    """Fetch recent git commits from repos matched to a client slug.

    Args:
        slug: Client profile slug (e.g., "hafnia-financial").
        repo_paths: Explicit repo paths. If None, resolved from client profile.
        days: Number of days of history to fetch.

    Returns:
        List of GitCommit objects sorted by date descending (max 20).
    """
    if repo_paths is None:
        if slug is None:
            return []
        repo_paths = _find_repos_for_client(slug)

    if not repo_paths:
        logger.info("No repos found for slug '%s'", slug)
        return []

    all_commits: list[GitCommit] = []

    for repo_path in repo_paths:
        try:
            proc = await asyncio.create_subprocess_exec(
                "git",
                "-C",
                str(repo_path),
                "log",
                f"--since={days} days ago",
                "--format=%H|%an|%aI|%s",
                "--no-merges",
                "-n",
                "20",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=10.0
            )

            if proc.returncode != 0:
                logger.warning(
                    "git log failed for %s: %s",
                    repo_path,
                    stderr.decode().strip(),
                )
                continue

            for line in stdout.decode().strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|", 3)
                if len(parts) != 4:
                    continue
                sha, author, date_iso, message = parts
                all_commits.append(
                    GitCommit(
                        sha=sha,
                        author=author,
                        date=datetime.fromisoformat(date_iso),
                        message=message,
                        repo_name=repo_path.name,
                    )
                )

        except asyncio.TimeoutError:
            logger.warning("git log timed out for %s", repo_path)
        except Exception:
            logger.warning("Error loading git activity from %s", repo_path, exc_info=True)

    all_commits.sort(key=lambda c: c.date, reverse=True)
    result = all_commits[:20]

    logger.info(
        "Found %d commits across %d repos for slug '%s'",
        len(result),
        len(repo_paths),
        slug,
    )
    return result


if __name__ == "__main__":
    import json

    target_slug = sys.argv[1] if len(sys.argv) > 1 else "hafnia-financial"
    logging.basicConfig(level=logging.DEBUG)
    commits = asyncio.run(fetch_git_activity(target_slug))
    print(json.dumps([c.model_dump(mode="json") for c in commits], indent=2))
