"""Linear GraphQL project and issue loader.

Given an attendee's company name, searches Linear for matching teams (projects)
and loads their open issues with title, status, assignee, and priority.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime

import httpx
from pydantic import BaseModel, Field

import config

logger = logging.getLogger(__name__)

LINEAR_API_URL = "https://api.linear.app/graphql"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class LinearIssue(BaseModel):
    id: str
    identifier: str  # e.g., "ACRE-42"
    title: str
    status: str  # e.g., "In Progress", "Todo"
    priority: int = 0  # 0=none, 1=urgent, 2=high, 3=medium, 4=low
    assignee: str | None = None
    url: str | None = None
    created_at: datetime | None = None


class LinearProject(BaseModel):
    id: str
    name: str  # team name, e.g., "ACRE Partner"
    key: str  # team key, e.g., "ACRE"
    description: str | None = None
    open_issues: list[LinearIssue] = Field(default_factory=list)
    issue_count: int = 0


# ---------------------------------------------------------------------------
# GraphQL helpers
# ---------------------------------------------------------------------------

TEAMS_QUERY = """
query($name: String!) {
  teams(filter: { name: { containsIgnoreCase: $name } }) {
    nodes {
      id
      name
      key
      description
    }
  }
}
"""

ISSUES_QUERY = """
query($teamId: String!) {
  issues(
    filter: {
      team: { id: { eq: $teamId } }
      state: { type: { in: ["started", "unstarted", "backlog"] } }
    }
    first: 10
    orderBy: priority
  ) {
    nodes {
      id
      identifier
      title
      priority
      url
      createdAt
      state { name }
      assignee { name }
    }
  }
}
"""


async def _graphql_request(
    client: httpx.AsyncClient,
    query: str,
    variables: dict | None = None,
) -> dict:
    """Execute a GraphQL request against the Linear API."""
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def fetch_linear_projects(company_name: str) -> list[LinearProject]:
    """Search Linear for teams matching *company_name* and load open issues.

    Returns an empty list (never raises) when:
    - LINEAR_API_KEY is not configured
    - The API returns an error or times out
    - No teams match the search
    """
    if not config.LINEAR_API_KEY:
        logger.warning("LINEAR_API_KEY not set — skipping Linear lookup")
        return []

    try:
        async with httpx.AsyncClient() as client:
            # 1. Find matching teams
            teams_resp = await _graphql_request(
                client, TEAMS_QUERY, {"name": company_name}
            )

            if "errors" in teams_resp:
                logger.error("Linear GraphQL error (teams): %s", teams_resp["errors"])
                return []

            team_nodes = teams_resp.get("data", {}).get("teams", {}).get("nodes", [])
            if not team_nodes:
                logger.info("Found 0 Linear projects for '%s'", company_name)
                return []

            # 2. For each team, load open issues
            projects: list[LinearProject] = []
            for team in team_nodes:
                issues_resp = await _graphql_request(
                    client, ISSUES_QUERY, {"teamId": team["id"]}
                )

                if "errors" in issues_resp:
                    logger.error(
                        "Linear GraphQL error (issues for %s): %s",
                        team["key"],
                        issues_resp["errors"],
                    )
                    issues = []
                else:
                    issue_nodes = (
                        issues_resp.get("data", {})
                        .get("issues", {})
                        .get("nodes", [])
                    )
                    issues = [
                        LinearIssue(
                            id=node["id"],
                            identifier=node["identifier"],
                            title=node["title"],
                            status=node.get("state", {}).get("name", "Unknown"),
                            priority=node.get("priority", 0),
                            assignee=(node.get("assignee") or {}).get("name"),
                            url=node.get("url"),
                            created_at=node.get("createdAt"),
                        )
                        for node in issue_nodes
                    ]

                projects.append(
                    LinearProject(
                        id=team["id"],
                        name=team["name"],
                        key=team["key"],
                        description=team.get("description"),
                        open_issues=issues,
                        issue_count=len(issues),
                    )
                )

            logger.info(
                "Found %d Linear project(s) for '%s'", len(projects), company_name
            )
            return projects

    except httpx.TimeoutException:
        logger.error("Linear API timeout for '%s'", company_name)
        return []
    except Exception:
        logger.exception("Unexpected error fetching Linear projects for '%s'", company_name)
        return []


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO)
    name = sys.argv[1] if len(sys.argv) > 1 else "acre"
    results = asyncio.run(fetch_linear_projects(name))
    print(json.dumps([p.model_dump(mode="json") for p in results], indent=2))
