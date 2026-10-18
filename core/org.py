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


# ---------------------------------------------------------------- onboarding: create a whole org from a spec

MAX_TEAMS, MAX_COMPONENTS, MAX_PEOPLE, MAX_DEPS = 50, 500, 1000, 2000


class OrgSpecError(ValueError):
    """The spec is invalid. `problems` lists every issue found, not just the first."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def validate_spec(teams: list[dict], dependencies: list[dict], projects: list[dict]) -> list[str]:
    problems: list[str] = []
    comps: dict[str, str] = {}
    people: dict[str, str] = {}
    team_names: set[str] = set()
    for t in teams:
        if t["name"] in team_names:
            problems.append(f"duplicate team {t['name']!r}")
        team_names.add(t["name"])
        for c in t.get("services", []):
            if c["name"] in comps:
                problems.append(f"service {c['name']!r} is listed under both {comps[c['name']]!r} and {t['name']!r}")
            comps[c["name"]] = t["name"]
        for p in t.get("people", []):
            if p["name"] in people:
                problems.append(f"person {p['name']!r} is in both {people[p['name']]!r} and {t['name']!r}")
            people[p["name"]] = t["name"]
    if not teams:
        problems.append("at least one team is required")
    if len(teams) > MAX_TEAMS or len(comps) > MAX_COMPONENTS or len(people) > MAX_PEOPLE or len(dependencies) > MAX_DEPS:
        problems.append(f"too large: max {MAX_TEAMS} teams, {MAX_COMPONENTS} services, {MAX_PEOPLE} people, {MAX_DEPS} dependencies")
    for d in dependencies:
        for end in ("service", "depends_on"):
            if d[end] not in comps:
                problems.append(f"dependency {d['service']!r} -> {d['depends_on']!r}: unknown service {d[end]!r}")
        if d["service"] == d["depends_on"]:
            problems.append(f"service {d['service']!r} can't depend on itself")
    for p in projects:
        for c in p.get("services", []):
            if c not in comps:
                problems.append(f"project {p['name']!r}: unknown service {c!r}")
    return problems


def create_org(org: Org, teams: list[dict], dependencies: list[dict], projects: list[dict]) -> dict:
    """Write a validated spec in a handful of batched (UNWIND) queries. Assumes the graph is new."""
    problems = validate_spec(teams, dependencies, projects)
    if problems:
        raise OrgSpecError(problems)
    org.write("onboard.teams", "UNWIND $teams AS t MERGE (:Team {name:t})", {"teams": [t["name"] for t in teams]})
    org.write("onboard.services",
              """UNWIND $rows AS r MATCH (t:Team {name:r.team})
                 MERGE (c:Component {name:r.name}) SET c.category = r.category
                 MERGE (t)-[:OWNS]->(c)""",
              {"rows": [{"team": t["name"], "name": c["name"], "category": c.get("category", "")}
                        for t in teams for c in t.get("services", [])]})
    org.write("onboard.people",
              """UNWIND $rows AS r MATCH (t:Team {name:r.team})
                 MERGE (d:Dev {name:r.name}) SET d.role = r.role
                 MERGE (d)-[:MEMBER_OF]->(t)""",
              {"rows": [{"team": t["name"], "name": p["name"], "role": p.get("role", "")}
                        for t in teams for p in t.get("people", [])]})
    if dependencies:
        org.write("onboard.dependencies",
                  """UNWIND $rows AS r MATCH (a:Component {name:r.a}), (b:Component {name:r.b})
                     MERGE (a)-[:DEPENDS_ON]->(b)""",
                  {"rows": [{"a": d["service"], "b": d["depends_on"]} for d in dependencies]})
    for p in projects:
        upsert_project(org, p["name"], p.get("repo", ""), p.get("services", []))
    return overview(org)
