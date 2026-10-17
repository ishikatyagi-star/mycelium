"""Org structure: teams, components (+ dependencies), devs, projects.

Names are the identity. Anything an agent or LLM mentions is *resolved against
the graph* before use, so agents cannot invent teams, people or components.
"""
from __future__ import annotations

from .db import Org


def upsert_team(org: Org, name: str) -> None:
    org.write("org.team", "MERGE (:Team {name:$name})", {"name": name})


def upsert_component(org: Org, name: str, team: str, category: str = "") -> None:
    org.write("org.component",
              """MERGE (t:Team {name:$team})
                 MERGE (c:Component {name:$name}) SET c.category = $category
                 MERGE (t)-[:OWNS]->(c)""",
              {"name": name, "team": team, "category": category})


def add_dependency(org: Org, component: str, depends_on: str) -> None:
    org.write("org.depends_on",
              """MATCH (a:Component {name:$a}), (b:Component {name:$b})
                 MERGE (a)-[:DEPENDS_ON]->(b)""", {"a": component, "b": depends_on})


def upsert_dev(org: Org, name: str, team: str, role: str = "") -> None:
    org.write("org.dev",
              """MERGE (t:Team {name:$team})
                 MERGE (d:Dev {name:$name}) SET d.role = $role
                 MERGE (d)-[:MEMBER_OF]->(t)""", {"name": name, "team": team, "role": role})


def upsert_project(org: Org, name: str, repo: str = "", components: list[str] | None = None,
                   started_at: int | None = None) -> None:
    org.write("org.project",
              """MERGE (p:Project {name:$name}) SET p.repo = $repo, p.started_at = $started_at
                 WITH p UNWIND $components AS cn
                 MATCH (c:Component {name:cn}) MERGE (p)-[:INCLUDES]->(c)""",
              {"name": name, "repo": repo, "components": components or [], "started_at": started_at})


def dev_info(org: Org, name: str) -> dict | None:
    rows = org.read("org.dev_info",
                    "MATCH (d:Dev {name:$name})-[:MEMBER_OF]->(t:Team) RETURN d.name AS name, t.name AS team",
                    {"name": name})
    return rows[0] if rows else None


def resolve_components(org: Org, names: list[str]) -> tuple[list[str], list[str]]:
    """Case-insensitive match against existing components. Returns (known, unknown)."""
    if not names:
        return [], []
    rows = org.read("org.resolve_components",
                    """UNWIND $names AS n
                       OPTIONAL MATCH (c:Component) WHERE toLower(c.name) = toLower(n)
                       RETURN n AS asked, c.name AS name""", {"names": names})
    known = sorted({r["name"] for r in rows if r["name"]})
    unknown = [r["asked"] for r in rows if not r["name"]]
    return known, unknown


def overview(org: Org) -> dict:
    teams = org.read("org.overview_teams",
                     """MATCH (t:Team)
                        OPTIONAL MATCH (t)-[:OWNS]->(c:Component)
                        WITH t, collect(DISTINCT c.name) AS components
                        OPTIONAL MATCH (d:Dev)-[:MEMBER_OF]->(t)
                        RETURN t.name AS name, components, collect(DISTINCT d.name) AS devs
                        ORDER BY name""")
    projects = org.read("org.overview_projects",
                        """MATCH (p:Project) OPTIONAL MATCH (p)-[:INCLUDES]->(c:Component)
                           RETURN p.name AS name, p.repo AS repo, p.started_at AS started_at,
                                  collect(c.name) AS components ORDER BY started_at""")
    counts = org.read("org.overview_counts",
                      """OPTIONAL MATCH (s:Session) WITH count(s) AS sessions
                         OPTIONAL MATCH (l:Session {status:'live'}) WITH sessions, count(l) AS live_sessions
                         OPTIONAL MATCH (m:Solution) WITH sessions, live_sessions, count(m) AS solutions
                         OPTIONAL MATCH (q:Question) WITH sessions, live_sessions, solutions, count(q) AS questions
                         OPTIONAL MATCH ()-[r:REUSED]->()
                         RETURN sessions, live_sessions, solutions, questions,
                                coalesce(sum(r.tokens_saved), 0) AS tokens_saved""")
    return {"teams": teams, "projects": projects, "counts": counts[0] if counts else {}}
