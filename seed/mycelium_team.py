"""Dogfood org 'mycelium': our real team, with memory imported from the Claude Code sessions in which
we built Mycelium itself (core/importer.py -> LLM proposals -> human curation -> seed/dogfood_memories.json).

  PYTHONPATH=. uv run python -m seed.mycelium_team

"Mycelium remembers how Mycelium was built": a second tenant, built from our own (scrubbed) data.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core import memory as M
from core import org as O
from core.db import Org
from core.schema import ensure_schema

IST = timezone(timedelta(hours=5, minutes=30))
COMPONENTS = [("graph-core", "library"), ("api", "service"), ("mcp-server", "integration"), ("hooks", "integration"),
              ("fleet", "worker"), ("importer", "tool"), ("llm", "library"), ("deploy", "infra"), ("web", "client")]
DEPENDS_ON = [("api", "graph-core"), ("mcp-server", "api"), ("hooks", "api"), ("fleet", "api"), ("fleet", "llm"),
              ("web", "api"), ("importer", "graph-core"), ("importer", "llm"), ("api", "deploy")]
PROJECT = "Mycelium (Graph Hacks 2026)"
STALE, FIX = "Upload fresh builds instead of redeploying", "Railway free plan restricts to a single region"


def seed(slug: str = "mycelium", reset: bool = True) -> dict:
    org = Org(slug)
    if reset:
        org.delete()
        org = Org(slug)
    ensure_schema(org)
    for name, cat in COMPONENTS:
        O.upsert_component(org, name, "Mycelium", cat)
    for a, b in DEPENDS_ON:
        O.add_dependency(org, a, b)
    O.upsert_dev(org, "Ishika", "Mycelium", "backend + product")
    O.upsert_dev(org, "Yash", "Mycelium", "web")
    O.upsert_project(org, PROJECT, "ishikatyagi-star/mycelium", [c for c, _ in COMPONENTS],
                     started_at=int(datetime(2026, 10, 18, 3, 0, tzinfo=IST).timestamp()))
    mems = json.loads((Path(__file__).parent / "dogfood_memories.json").read_text())
    t0 = datetime(2026, 10, 18, 3, 5, tzinfo=IST)
    step = timedelta(minutes=135 / max(1, len(mems)))
    ids: dict[str, str] = {}
    for i, m in enumerate(mems):
        start = int((t0 + i * step).timestamp())
        s = M.start_session(org, "Ishika", m["task"], m["components"], PROJECT, agent="claude-code (imported)",
                            session_id=f"ses_build_{i}", started_at=start, status="done")
        supersedes = []
        if m["title"].startswith(FIX) and STALE in ids:
            M.report_outcome(org, s["session_id"], ids[STALE], worked=False,
                             error="Deploy still failed: 'Your plan can only deploy to a single region'")
            supersedes = [ids[STALE]]
        r = M.save_solution(org, M.SaveRequest(
            session_id=s["session_id"], title=m["title"], summary=m["summary"], lessons=m["lessons"],
            libraries=m.get("libraries", []), supersedes=supersedes, created_at=start + int(step.total_seconds()),
            effort_minutes=max(3, int(step.total_seconds() // 60)), solution_id=f"sol_build_{i}"))
        M.end_session(org, s["session_id"], ended_at=start + int(step.total_seconds()))
        key = next((k for k in (STALE, FIX) if m["title"].startswith(k)), m["title"])
        ids[key] = r.get("solution_id")
    return {"org": slug, "memories": len(ids)}


if __name__ == "__main__":
    print(seed())
