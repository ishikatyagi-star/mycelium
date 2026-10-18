"""Playground: explain, step by step, how an agent's question becomes a credited fix.

`staged_recall` runs the real hybrid recall and returns it as an ordered list of steps (each with the exact
Cypher it ran, timing and the data it produced) so the UI can animate the memory fetch. It also returns what
the same problem cost the first time ("from scratch"), taken from the graph's effort properties.
"""
from __future__ import annotations

import json
import time

from . import llm
from . import memory as M
from .db import Org, current_trace, start_trace
from .embed import DIM, embed


def scenarios(org: Org) -> list[dict]:
    rows = org.read("playground.list",
                    """MATCH (d:Dev)-[:RAN]->(s:Session {scenario:true})-[:IN_PROJECT]->(p:Project)
                       MATCH (d)-[:MEMBER_OF]->(t:Team)
                       OPTIONAL MATCH (s)-[:TOUCHES]->(c:Component)
                       RETURN s.id AS session_id, s.title AS title, s.problem AS problem, s.query AS query,
                              s.transcript AS transcript, s.started_at AS started_at, d.name AS dev, d.role AS role,
                              t.name AS team, p.name AS project, collect(c.name) AS components
                       ORDER BY started_at DESC""")
    for r in rows:
        r["dev"] = {"name": r.pop("dev"), "team": r.pop("team"), "role": r.pop("role")}
        r["transcript"] = json.loads(r["transcript"] or "[]")
    return rows


def _scenario(org: Org, sid: str) -> dict:
    s = next((x for x in scenarios(org) if x["session_id"] == sid), None)
    if not s:
        raise ValueError("unknown playground scenario")
    return s


def staged_recall(org: Org, sid: str) -> dict:
    s = _scenario(org, sid)
    viewer = s["dev"]["name"]
    t0 = time.perf_counter()
    emb = embed(s["query"])
    embed_ms = (time.perf_counter() - t0) * 1000

    start_trace()
    cands = M._candidates(org, emb, viewer, n=20)
    cand_trace = current_trace()
    start_trace()
    results = M.recall(org, s["query"], viewer, k=3)
    trace = current_trace()
    by_name = {t["name"]: t for t in trace}

    ids = list({c["solution_id"] for c in cands})
    titles = {r["id"]: r for r in org.read("playground.cand_titles",
              """UNWIND $ids AS i MATCH (s:Solution {id:i})<-[:PRODUCED]-(:Session)<-[:RAN]-(d:Dev)-[:MEMBER_OF]->(t:Team)
                 RETURN s.id AS id, s.title AS title, d.name AS dev, t.name AS team""", {"ids": ids})}
    seen, candidates = set(), []
    for c in cands:
        if c["solution_id"] in seen:
            continue
        seen.add(c["solution_id"])
        info = titles.get(c["solution_id"], {})
        candidates.append({"task": c["task_text"], "similarity": round(c["sim"], 3), "solution_id": c["solution_id"],
                           "title": info.get("title"), "status": c["status"],
                           "author": {"name": info.get("dev"), "team": info.get("team")}})
        if len(candidates) == 5:
            break

    top = results[0] if results else None
    steps = [
        {"key": "embed", "title": "Understand the problem",
         "detail": f"The agent's problem is turned into a {DIM}-dimensional vector (bge-small, computed locally).",
         "ms": round(embed_ms, 1), "data": {"query": s["query"]}},
        {"key": "vector", "title": "Find similar past problems",
         "detail": "FalkorDB's vector index searches every Task any agent in the org has ever worked on, and the same query "
                   "enforces visibility (private / team / org) through MEMBER_OF.",
         "cypher": cand_trace[0]["cypher"] if cand_trace else None, "ms": cand_trace[0]["ms"] if cand_trace else None,
         "data": {"candidates": candidates}},
        {"key": "walk", "title": "Walk the graph past stale fixes",
         "detail": "For each candidate, follow SUPERSEDES to the newest fix. Fixes that later broke (FAILED_WITH) are skipped, "
                   "and their failure becomes a warning.",
         "cypher": by_name.get("recall.supersede_walk", {}).get("cypher"), "ms": by_name.get("recall.supersede_walk", {}).get("ms"),
         "data": {"skipped": top["skipped"] if top else []}},
        {"key": "expand", "title": "Bring back the context",
         "detail": "Attach who solved it, in which project and team, how hard it was, the lessons and dead ends, and what it builds on.",
         "cypher": by_name.get("recall.expand", {}).get("cypher"), "ms": by_name.get("recall.expand", {}).get("ms"),
         "data": {"lessons": top["lessons"] if top else [], "author": top["author"] if top else None,
                  "project": top["project"] if top else None}},
        {"key": "rank", "title": "Rank and credit",
         "detail": "Score = similarity × status × effort (hard-won first) × proven reuse. The author gets credit when it's reused.",
         "data": {"score": top["score"] if top else None, "similarity": top["similarity"] if top else None}},
    ]
    scratch = None
    if top:
        sol = top["solution"]
        dead = [sk["title"] + f" ({sk['reason']})" for sk in top["skipped"]] + \
               [l["text"] for l in top["lessons"] if l["kind"] == "dead_end"]
        scratch = {"effort_minutes": sol["effort_minutes"], "attempts": sol["attempts"], "tokens": sol["tokens_spent"],
                   "dead_ends": dead, "author": top["author"]}
    return {"scenario": s, "steps": steps, "memory": top, "also": results[1:], "scratch": scratch,
            "trace": cand_trace + trace}


def implement(org: Org, sid: str, solution_id: str) -> dict:
    s = _scenario(org, sid)
    mem = M._expand(org, [solution_id]).get(solution_id)
    if not mem:
        raise ValueError("unknown solution")
    chat = "\n".join(f"{m['role']}: {m['text']}" for m in s["transcript"][-4:])
    lessons = "\n".join(f"- {l['kind']}: {l['text']}" for l in mem["lessons"])
    out = llm.chat(
        f"You are the AI coding agent of {s['dev']['name']} ({s['dev']['team']} team at Graph HQ). Your developer "
        "asked you to implement the fix now, using the org memory below. Reply in markdown: one short paragraph "
        "saying what you'll do and why the naive approach fails, then ONE compact code block adapted to this "
        f"codebase, then a final line crediting {mem['author']} ({mem['team']}) and the project it came from. "
        "Keep it under 220 words.",
        f"Conversation so far:\n{chat}\n\nOrg memory: '{mem['title']}' by {mem['author']} ({mem['team']}), project "
        f"{mem.get('project')}.\nSummary: {mem['summary']}\nLessons:\n{lessons}\nReference code:\n{mem.get('code') or '(none)'}",
        max_tokens=700)
    if not out:
        out = (f"Reusing **{mem['title']}** from {mem['author']} ({mem['team']}, {mem.get('project')}).\n\n"
               f"{mem['summary']}\n\n" + (f"```\n{mem['code']}\n```\n\n" if mem.get("code") else "")
               + f"_Credit: {mem['author']} ({mem['team']})._")
    return {"text": out, "solution_id": solution_id, "author": {"name": mem["author"], "team": mem["team"]}}
