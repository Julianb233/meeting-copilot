"""Linear router — creates issues routed to the correct project/team.

Takes Intent objects from the detection layer and creates Linear issues
with rich meeting context (speaker, transcript, urgency) in the correct
team based on project resolution.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

import config
from intent.models import ActionType, Intent
from routing.project_resolver import ProjectResolver

LINEAR_API_URL = "https://api.linear.app/graphql"

CREATE_ISSUE_MUTATION = """
mutation CreateIssue($input: IssueCreateInput!) {
    issueCreate(input: $input) {
        success
        issue { id identifier title url state { name } }
    }
}
"""

# Map action types to title prefixes
_ACTION_PREFIX: dict[ActionType, str] = {
    ActionType.BUILD_FEATURE: "Build",
    ActionType.FIX_BUG: "Fix",
    ActionType.RESEARCH: "Research",
    ActionType.FOLLOW_UP: "Follow up",
    ActionType.SEND_EMAIL: "Email",
}

# Map urgency to Linear priority: 1=urgent, 2=high, 3=medium, 4=low
_URGENCY_PRIORITY: dict[str, int] = {
    "now": 1,
    "soon": 3,
    "later": 4,
}


class LinearRouter:
    """Creates Linear issues routed to the correct project/team."""

    def __init__(self, resolver: ProjectResolver | None = None) -> None:
        self.resolver = resolver or ProjectResolver()
        self.logger = logging.getLogger("copilot.routing.linear")

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
    # Issue creation
    # ------------------------------------------------------------------

    async def create_linear_issue(
        self,
        intent: Intent,
        team_id: str,
        meeting_title: str | None = None,
    ) -> dict | None:
        """Create a Linear issue with rich meeting context.

        Returns the issue dict (id, identifier, title, url) on success,
        None on failure.
        """
        # Build title with action prefix
        prefix = _ACTION_PREFIX.get(intent.action_type)
        title = f"{prefix}: {intent.target}" if prefix else intent.target

        # Build description with meeting context
        description = (
            f"**From meeting:** {meeting_title or 'Unknown meeting'}\n"
            f"**Speaker:** {intent.speaker}\n"
            f"**Urgency:** {intent.urgency}\n"
            f"**Confidence:** {intent.confidence:.0%}\n"
            f"\n"
            f"**Context:**\n"
            f"> {intent.source_text}\n"
            f"\n"
            f"**Details:**\n"
            f"{intent.details}\n"
            f"\n"
            f"_Created automatically by Meeting Copilot_"
        )

        priority = _URGENCY_PRIORITY.get(intent.urgency, 3)

        if not config.LINEAR_API_KEY:
            self.logger.warning("LINEAR_API_KEY not set — cannot create issue")
            return None

        try:
            resp = await self._graphql(
                CREATE_ISSUE_MUTATION,
                {
                    "input": {
                        "title": title,
                        "description": description,
                        "teamId": team_id,
                        "priority": priority,
                    }
                },
            )

            if "errors" in resp:
                self.logger.error("Linear GraphQL error (issue create): %s", resp["errors"])
                return None

            issue_data = resp.get("data", {}).get("issueCreate", {})
            if not issue_data.get("success"):
                self.logger.error("Linear issueCreate returned success=false")
                return None

            issue = issue_data["issue"]
            self.logger.info(
                "Created Linear issue: %s -> %s",
                issue.get("identifier", "?"),
                issue.get("url", "?"),
            )
            return issue

        except Exception:
            self.logger.exception("Failed to create Linear issue")
            return None

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    async def route_intent(
        self,
        intent: Intent,
        attendee_companies: list[str] | None = None,
        meeting_title: str | None = None,
    ) -> dict | None:
        """Route an intent to the correct Linear project and create an issue.

        Returns the created issue dict or None on failure.
        """
        project = await self.resolver.resolve(intent, attendee_companies)

        # Auto-create team if intent has explicit project name but no match
        if project is None and intent.project:
            try:
                project = await self.resolver.find_or_create_team(intent.project)
            except Exception:
                self.logger.exception(
                    "Failed to auto-create team for '%s'", intent.project
                )

        # Fall back to default team
        team_id: str | None = None
        if project:
            team_id = project.id
        elif config.LINEAR_DEFAULT_TEAM_ID:
            team_id = config.LINEAR_DEFAULT_TEAM_ID
            self.logger.info("Using default team ID: %s", team_id)
        else:
            self.logger.warning(
                "No project resolved and no default team configured — skipping intent"
            )
            return None

        issue = await self.create_linear_issue(intent, team_id, meeting_title)

        # Track topic for multi-project switching
        self.resolver.track_topic(project.name if project else None)

        return issue

    async def route_batch(
        self,
        intents: list[Intent],
        attendee_companies: list[str] | None = None,
        meeting_title: str | None = None,
    ) -> list[dict]:
        """Route multiple intents in parallel, returning created issues."""
        tasks = [
            self.route_intent(intent, attendee_companies, meeting_title)
            for intent in intents
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        issues: list[dict] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(
                    "Failed to route intent %d: %s", i, result
                )
            elif result is not None:
                issues.append(result)

        return issues


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO)

    async def main() -> None:
        router = LinearRouter()
        test_intent = Intent(
            action_type=ActionType.CREATE_ISSUE,
            target="Test routing task",
            details="Created from CLI test of LinearRouter",
            confidence=0.95,
            source_text="We need to test the routing system",
            speaker="Julian",
            urgency="soon",
        )
        print(f"Test intent: {test_intent.action_type.value} -> {test_intent.target}")
        print("Would route to default team (dry run — no API call in test)")

    asyncio.run(main())
