"""Project resolver — maps intents to Linear teams.

Given an Intent, resolves the target Linear project/team using a 4-level
priority chain: explicit project name > active topic > attendee company > default.
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys
import time

import httpx

import config
from context.linear_client import LinearProject, fetch_linear_projects
from intent.models import Intent

LINEAR_API_URL = "https://api.linear.app/graphql"

ALL_TEAMS_QUERY = """
query {
  teams {
    nodes {
      id
      name
      key
      description
    }
  }
}
"""

CREATE_TEAM_MUTATION = """
mutation CreateTeam($input: TeamCreateInput!) {
    teamCreate(input: $input) {
        success
        team { id name key }
    }
}
"""


class ProjectResolver:
    """Resolves which Linear project/team an intent should route to.

    Resolution priority:
    1. Explicit project name in the intent (LLM extracted "ACRE" from transcript)
    2. Active conversation topic (sustained mention tracking)
    3. Attendee's primary company -> matching Linear team
    4. Default team (config.LINEAR_DEFAULT_TEAM_ID or first available)
    """

    def __init__(self) -> None:
        self._project_cache: dict[str, LinearProject] = {}  # name_lower -> project
        self._cache_expiry: float = 0
        self._cache_ttl: float = 300  # 5 minutes
        self._active_project: LinearProject | None = None
        self._topic_window: list[str] = []  # last N project mentions for switching detection
        self._topic_threshold: int = 3  # consecutive mentions before switching
        self.logger = logging.getLogger("copilot.routing")

    # ------------------------------------------------------------------
    # GraphQL helper
    # ------------------------------------------------------------------

    async def _graphql(
        self, query: str, variables: dict | None = None
    ) -> dict:
        """Execute a GraphQL request against the Linear API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                LINEAR_API_URL,
                json={"query": query, "variables": variables or {}},
                headers={
                    "Authorization": config.LINEAR_API_KEY,
                    "Content-Type": "application/json",
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    async def refresh_cache(self) -> None:
        """Fetch all teams from Linear and populate the project cache.

        Only refreshes when the cache TTL has expired.
        """
        now = time.monotonic()
        if now < self._cache_expiry and self._project_cache:
            return

        if not config.LINEAR_API_KEY:
            self.logger.warning("LINEAR_API_KEY not set — cannot refresh team cache")
            return

        try:
            resp = await self._graphql(ALL_TEAMS_QUERY)
            if "errors" in resp:
                self.logger.error("Linear GraphQL error (teams): %s", resp["errors"])
                return

            nodes = resp.get("data", {}).get("teams", {}).get("nodes", [])
            self._project_cache = {
                node["name"].lower(): LinearProject(
                    id=node["id"],
                    name=node["name"],
                    key=node["key"],
                    description=node.get("description"),
                )
                for node in nodes
            }
            self._cache_expiry = now + self._cache_ttl
            self.logger.info(
                "Refreshed Linear team cache: %d teams", len(self._project_cache)
            )
        except Exception:
            self.logger.exception("Failed to refresh Linear team cache")

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    async def resolve(
        self,
        intent: Intent,
        attendee_companies: list[str] | None = None,
    ) -> LinearProject | None:
        """Resolve the target Linear project for an intent.

        Priority:
        1. Explicit project name on the intent
        2. Active conversation topic (set by topic switching)
        3. Attendee company match
        4. Returns None (caller decides: create new or use default)
        """
        await self.refresh_cache()

        # 1. Explicit project name
        if intent.project:
            project = self._fuzzy_cache_lookup(intent.project)
            if project:
                return project
            # Not in cache — try fresh Linear API search
            results = await fetch_linear_projects(intent.project)
            if results:
                # Add to cache for next time
                for p in results:
                    self._project_cache[p.name.lower()] = p
                return results[0]

        # 2. Active topic
        if self._active_project:
            return self._active_project

        # 3. Attendee company match
        if attendee_companies:
            for company in attendee_companies:
                project = self._fuzzy_cache_lookup(company)
                if project:
                    return project

        # 4. No match
        return None

    def _fuzzy_cache_lookup(self, name: str) -> LinearProject | None:
        """Search cache for a project whose name contains *name* (case-insensitive)."""
        needle = name.lower()
        # Exact match first
        if needle in self._project_cache:
            return self._project_cache[needle]
        # Substring match
        for key, project in self._project_cache.items():
            if needle in key or key in needle:
                return project
        return None

    # ------------------------------------------------------------------
    # Topic switching
    # ------------------------------------------------------------------

    def track_topic(self, project_name: str | None) -> LinearProject | None:
        """Track project mentions for multi-project switching detection.

        Returns the new active project if a switch occurred, else None.
        """
        if project_name is None:
            self._topic_window.clear()
            return None

        self._topic_window.append(project_name.lower())
        # Keep last 10 entries
        if len(self._topic_window) > 10:
            self._topic_window = self._topic_window[-10:]

        # Check if last N entries are all the same project
        if len(self._topic_window) >= self._topic_threshold:
            recent = self._topic_window[-self._topic_threshold :]
            if len(set(recent)) == 1:
                new_name = recent[0]
                new_project = self._project_cache.get(new_name)
                old_name = self._active_project.name if self._active_project else None
                if new_project and (old_name is None or old_name.lower() != new_name):
                    self.logger.info(
                        "Topic switch detected: %s -> %s", old_name, new_project.name
                    )
                    self._active_project = new_project
                    return new_project

        return None

    # ------------------------------------------------------------------
    # Team creation
    # ------------------------------------------------------------------

    async def find_or_create_team(self, name: str) -> LinearProject:
        """Find an existing team or create a new one in Linear.

        Returns the LinearProject for the team.
        """
        # Try to find existing
        dummy_intent = Intent(
            action_type="general_task",
            target="lookup",
            details="",
            confidence=1.0,
            source_text="",
            speaker="system",
            project=name,
        )
        existing = await self.resolve(dummy_intent)
        if existing:
            return existing

        # Create new team
        key = re.sub(r"[^A-Za-z0-9]", "", name)[:4].upper()
        if not key:
            key = "NEW"

        if not config.LINEAR_API_KEY:
            raise RuntimeError("LINEAR_API_KEY not set — cannot create team")

        resp = await self._graphql(
            CREATE_TEAM_MUTATION,
            {"input": {"name": name, "key": key}},
        )

        if "errors" in resp:
            raise RuntimeError(f"Failed to create Linear team '{name}': {resp['errors']}")

        team_data = resp.get("data", {}).get("teamCreate", {})
        if not team_data.get("success"):
            raise RuntimeError(f"Linear teamCreate returned success=false for '{name}'")

        team = team_data["team"]
        project = LinearProject(
            id=team["id"],
            name=team["name"],
            key=team["key"],
        )

        # Add to cache
        self._project_cache[project.name.lower()] = project
        self.logger.info("Created new Linear team: %s (%s)", project.name, project.key)
        return project


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO)

    async def main() -> None:
        resolver = ProjectResolver()
        await resolver.refresh_cache()
        projects = list(resolver._project_cache.values())
        print(f"Cached {len(projects)} teams:")
        print(json.dumps([p.model_dump(mode="json") for p in projects], indent=2))

    asyncio.run(main())
