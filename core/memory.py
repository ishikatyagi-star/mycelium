"""Memory across time: sessions, tasks, solutions, recall, reuse, outcomes, lineage.

Recall is *hybrid*: a vector index finds similar past problems, then the graph
decides what is actually worth handing to the agent:
  * walks SUPERSEDES to the newest fix, skipping stale or broken versions,
  * attaches lessons, dead ends and errors,
  * enforces visibility (private / team / org),
  * ranks by similarity x status x effort (hard-won fixes first) x proven reuse,
  * returns credit (author, team, project, session) and the path it walked.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .db import Org, now
from .embed import embed
from .ids import new_id, nid
from .org import dev_info, resolve_components

TASK_MERGE_SIM = 0.93     # a new task this close to an existing one IS that task
RECALL_MIN_SIM = 0.55     # below this, a hit is noise
VISIBILITIES = ("private", "team", "org")
LESSON_KINDS = ("pitfall", "tip", "dead_end")


# ---------------------------------------------------------------- tasks

def resolve_task(org: Org, text: str, emb: list[float] | None = None) -> tuple[str, bool, float]:
    """Return (task_id, merged_into_existing, similarity)."""
    emb = emb or embed(text)
    rows = org.read("task.nearest",
                    """CALL db.idx.vector.queryNodes('Task','embedding',1,vecf32($emb))
                       YIELD node, score RETURN node.id AS id, 1 - score AS sim""", {"emb": emb})
    if rows and rows[0]["sim"] >= TASK_MERGE_SIM:
        return rows[0]["id"], True, rows[0]["sim"]
    tid = new_id("task")
    org.write("task.create",
              "CREATE (:Task {id:$id, text:$text, embedding:vecf32($emb), created_at:$at})",
              {"id": tid, "text": text, "emb": emb, "at": now()})
    return tid, False, rows[0]["sim"] if rows else 0.0


# ---------------------------------------------------------------- sessions

def start_session(org: Org, dev: str, task: str, components: list[str] | None = None,
                  project: str | None = None, agent: str = "claude-code",
                  session_id: str | None = None, started_at: int | None = None,
                  status: str = "live") -> dict:
    if not dev_info(org, dev):
        raise ValueError(f"unknown dev {dev!r}: devs must exist in the org graph")
    known, unknown = resolve_components(org, components or [])
    sid = session_id or new_id("ses")
    at = started_at or now()
    task_id, merged, _ = resolve_task(org, task)
    org.write("session.start",
              """MATCH (d:Dev {name:$dev}), (t:Task {id:$task_id})
                 MERGE (s:Session {id:$sid})
                 SET s.agent=$agent, s.status=$status, s.started_at=$at, s.last_seen=$at,
                     s.task=$task, s.attempts=coalesce(s.attempts,0), s.tokens=coalesce(s.tokens,0)
                 MERGE (d)-[:RAN]->(s)
                 MERGE (s)-[:WORKED_ON]->(t)
                 WITH s UNWIND $components AS cn
                 MATCH (c:Component {name:cn}) MERGE (s)-[:TOUCHES]->(c)""",
              {"dev": dev, "task_id": task_id, "sid": sid, "agent": agent, "status": status,
               "at": at, "task": task, "components": known})
    if project:
        org.write("session.project",
                  """MATCH (s:Session {id:$sid}) MERGE (p:Project {name:$project})
                     MERGE (s)-[:IN_PROJECT]->(p)""", {"sid": sid, "project": project})
    return {"session_id": sid, "task_id": task_id, "task_merged": merged,
            "components": known, "unknown_components": unknown}


def touch_session(org: Org, session_id: str, components: list[str] | None = None,
                  attempts: int | None = None, tokens: int | None = None) -> list[str]:
    known, _ = resolve_components(org, components or [])
    org.write("session.heartbeat",
              """MATCH (s:Session {id:$sid})
                 SET s.last_seen=$at, s.status='live',
                     s.attempts=coalesce($attempts, s.attempts), s.tokens=coalesce($tokens, s.tokens)
                 WITH s UNWIND $components AS cn
                 MATCH (c:Component {name:cn}) MERGE (s)-[:TOUCHES]->(c)""",
              {"sid": session_id, "at": now(), "components": known, "attempts": attempts, "tokens": tokens})
    return known


def end_session(org: Org, session_id: str, ended_at: int | None = None) -> None:
    org.write("session.end",
              """MATCH (s:Session {id:$sid}) SET s.status='done', s.ended_at=$at
                 WITH s OPTIONAL MATCH (s)-[c:CLAIMS]->() DELETE c""",
              {"sid": session_id, "at": ended_at or now()})


# ---------------------------------------------------------------- saving (write gate)

@dataclass
class SaveRequest:
    session_id: str
    title: str
    summary: str
    code: str = ""
    libraries: list[dict] = field(default_factory=list)   # [{name, version?}]
    lessons: list[dict] = field(default_factory=list)     # [{text, kind}]
    errors: list[str] = field(default_factory=list)       # error signatures seen on the way
    visibility: str = "org"
    builds_on: list[str] = field(default_factory=list)    # solution ids this extends
    supersedes: list[str] = field(default_factory=list)   # solution ids this replaces
    effort_minutes: int | None = None
    attempts: int | None = None
    tokens_spent: int | None = None
    created_at: int | None = None
    solution_id: str | None = None


def gate(org: Org, req: SaveRequest) -> tuple[bool, list[str], dict]:
    """The write gate: an LLM may *propose* memory; plain code decides what is stored."""
    reasons: list[str] = []
    title, summary = req.title.strip(), req.summary.strip()
    if not (3 <= len(title) <= 160):
        reasons.append("title must be 3-160 chars")
    if len(summary) < 20:
        reasons.append("summary too short to be useful (<20 chars)")
    if req.visibility not in VISIBILITIES:
        reasons.append(f"visibility must be one of {VISIBILITIES}")
    lessons = []
    for l in req.lessons:
        kind = l.get("kind", "tip")
        text = (l.get("text") or "").strip()
        if kind not in LESSON_KINDS or len(text) < 8:
            reasons.append(f"dropped invalid lesson: {text[:40]!r}")
            continue
        lessons.append({"text": text, "kind": kind})
    sess = org.read("gate.session",
                    """MATCH (d:Dev)-[:RAN]->(s:Session {id:$sid})
                       RETURN s.started_at AS started_at, s.ended_at AS ended_at,
                              s.attempts AS attempts, s.tokens AS tokens, d.name AS dev""",
                    {"sid": req.session_id})
    if not sess:
        return False, ["unknown session: start_session first"], {}
    refs = req.builds_on + req.supersedes
    if refs:
        found = {r["id"] for r in org.read("gate.refs",
                 "UNWIND $ids AS i MATCH (s:Solution {id:i}) RETURN s.id AS id", {"ids": refs})}
        missing = [r for r in refs if r not in found]
        if missing:
            reasons.append(f"ignored unknown solution refs: {missing}")
            req.builds_on = [r for r in req.builds_on if r in found]
            req.supersedes = [r for r in req.supersedes if r in found]
    fatal = [r for r in reasons if not r.startswith(("dropped", "ignored"))]
    s = sess[0]
    end = s["ended_at"] or req.created_at or now()
    clean = {"title": title, "summary": summary, "lessons": lessons,
             "effort_minutes": req.effort_minutes if req.effort_minutes is not None
             else max(1, int((end - (s["started_at"] or end)) / 60)),
             "attempts": req.attempts if req.attempts is not None else (s["attempts"] or 0),
             "tokens_spent": req.tokens_spent if req.tokens_spent is not None else (s["tokens"] or 0)}
    return not fatal, reasons, clean


def save_solution(org: Org, req: SaveRequest) -> dict:
    ok, reasons, clean = gate(org, req)
    at = req.created_at or now()
    if not ok:
        org.write("gate.reject_receipt",
                  """MATCH (s:Session {id:$sid})
                     CREATE (s)-[:WROTE]->(:Receipt {at:$at, decision:'REJECT', reasons:$reasons})""",
                  {"sid": req.session_id, "at": at, "reasons": reasons})
        return {"decision": "REJECT", "reasons": reasons}
    sol_id = req.solution_id or new_id("sol")
    org.write("memory.save_solution",
              """MATCH (se:Session {id:$sid})-[:WORKED_ON]->(t:Task)
                 MERGE (s:Solution {id:$id})
                 SET s.title=$title, s.summary=$summary, s.code=$code, s.status='active',
                     s.visibility=$vis, s.effort_minutes=$effort, s.attempts=$attempts,
                     s.tokens_spent=$tokens, s.created_at=$at
                 MERGE (se)-[:PRODUCED]->(s)
                 MERGE (s)-[:SOLVES]->(t)
                 CREATE (se)-[:WROTE]->(:Receipt {at:$at, decision:'ACCEPT', reasons:$reasons, solution:$id})""",
              {"sid": req.session_id, "id": sol_id, "title": clean["title"], "summary": clean["summary"],
               "code": req.code, "vis": req.visibility, "effort": clean["effort_minutes"],
               "attempts": clean["attempts"], "tokens": clean["tokens_spent"], "at": at, "reasons": reasons})
    if req.libraries:
        org.write("memory.libraries",
                  """MATCH (s:Solution {id:$id}) UNWIND $libs AS lib
                     MERGE (l:Library {name:toLower(lib.name)})
                     MERGE (s)-[u:USES]->(l) SET u.version = lib.version""",
                  {"id": sol_id, "libs": [{"name": l["name"], "version": l.get("version", "")}
                                          for l in req.libraries if l.get("name")]})
    if clean["lessons"]:
        org.write("memory.lessons",
                  """MATCH (s:Solution {id:$id}) UNWIND $lessons AS les
                     MERGE (l:Lesson {text:les.text}) SET l.kind = les.kind
                     MERGE (s)-[:TAUGHT]->(l)""", {"id": sol_id, "lessons": clean["lessons"]})
    if req.errors:
        org.write("memory.errors",
                  """MATCH (s:Solution {id:$id}) UNWIND $errs AS e
                     MERGE (er:Error {signature:e}) MERGE (s)-[:HIT]->(er)""",
                  {"id": sol_id, "errs": req.errors})
    if req.builds_on:
        org.write("memory.builds_on",
                  """MATCH (s:Solution {id:$id}) UNWIND $refs AS r
                     MATCH (o:Solution {id:r}) MERGE (s)-[:BUILDS_ON]->(o)""",
                  {"id": sol_id, "refs": req.builds_on})
    if req.supersedes:
        org.write("memory.supersedes",
                  """MATCH (s:Solution {id:$id}) UNWIND $refs AS r
                     MATCH (o:Solution {id:r}) MERGE (s)-[:SUPERSEDES]->(o)
                     SET o.status = 'superseded'""", {"id": sol_id, "refs": req.supersedes})
    return {"decision": "ACCEPT", "solution_id": sol_id, "reasons": reasons}


# ---------------------------------------------------------------- outcomes and reuse

def record_reuse(org: Org, session_id: str, solution_id: str, outcome: str = "reused",
                 at: int | None = None) -> dict:
    """Credit the author: REUSED edge (+ estimated tokens saved) and a Dev->Dev CREDITS edge
    that feeds PageRank for 'who knows'."""
    rows = org.write("memory.reuse",
                     """MATCH (se:Session {id:$sid})<-[:RAN]-(me:Dev), (s:Solution {id:$sol})
                        MATCH (s)<-[:PRODUCED]-(:Session)<-[:RAN]-(author:Dev)
                        MERGE (se)-[r:REUSED]->(s)
                        SET r.at=$at, r.outcome=$outcome,
                            r.tokens_saved = toInteger(coalesce(s.tokens_spent, 0) * 0.8)
                        WITH me, author, r, s WHERE me <> author
                        MERGE (me)-[c:CREDITS]->(author) SET c.count = coalesce(c.count, 0) + 1
                        RETURN r.tokens_saved AS tokens_saved, author.name AS author, s.title AS title""",
                     {"sid": session_id, "sol": solution_id, "at": at or now(), "outcome": outcome})
    return rows[0] if rows else {"tokens_saved": 0}


def report_outcome(org: Org, session_id: str, solution_id: str, worked: bool,
                   error: str | None = None) -> dict:
    if worked:
        return {"recorded": "worked", **record_reuse(org, session_id, solution_id, outcome="worked")}
    org.write("memory.failed",
              """MATCH (s:Solution {id:$sol}), (se:Session {id:$sid})<-[:RAN]-(d:Dev)
                 MERGE (e:Error {signature:$err})
                 MERGE (s)-[f:FAILED_WITH]->(e) SET f.at=$at, f.by=d.name
                 SET s.status = CASE s.status WHEN 'superseded' THEN 'superseded' ELSE 'broken' END
                 MERGE (se)-[r:REUSED]->(s) SET r.at=$at, r.outcome='failed', r.tokens_saved=0""",
              {"sol": solution_id, "sid": session_id, "err": error or "unspecified failure", "at": now()})
    return {"recorded": "failed", "solution_status": "broken"}


# ---------------------------------------------------------------- recall

def _effort_boost(minutes: int | None, attempts: int | None) -> float:
    hours = (minutes or 0) / 60
    return 1 + 0.08 * math.log1p(hours) + 0.04 * math.log1p(attempts or 0)


STATUS_FACTOR = {"active": 1.0, "broken": 0.45, "superseded": 0.6}


def _candidates(org: Org, query_emb: list[float], viewer: str, n: int) -> list[dict]:
    return org.read("recall.vector_candidates",
                    """CALL db.idx.vector.queryNodes('Task','embedding',$n,vecf32($emb)) YIELD node AS t, score
                       WITH t, 1 - score AS sim WHERE sim >= $min_sim
                       MATCH (s:Solution)-[:SOLVES]->(t)
                       MATCH (s)<-[:PRODUCED]-(:Session)<-[:RAN]-(a:Dev)-[:MEMBER_OF]->(at:Team)
                       MATCH (v:Dev {name:$viewer})-[:MEMBER_OF]->(vt:Team)
                       WHERE s.visibility = 'org' OR (s.visibility = 'team' AND at = vt) OR a = v
                       RETURN t.id AS task_id, t.text AS task_text, sim, s.id AS solution_id, s.status AS status
                       ORDER BY sim DESC""",
                    {"emb": query_emb, "n": n, "min_sim": RECALL_MIN_SIM, "viewer": viewer})


def _supersede_walk(org: Org, ids: list[str]) -> dict[str, list[str]]:
    """For each solution id, the chain [id, ..., newest] following incoming SUPERSEDES."""
    rows = org.read("recall.supersede_walk",
                    """UNWIND $ids AS sid
                       MATCH (s0:Solution {id:sid})
                       OPTIONAL MATCH p = (newer:Solution)-[:SUPERSEDES*1..4]->(s0)
                       WITH s0, p ORDER BY length(p) DESC
                       WITH s0, collect(p)[0] AS longest
                       RETURN s0.id AS id,
                              CASE WHEN longest IS NULL THEN [s0.id]
                                   ELSE reverse([n IN nodes(longest) | n.id]) END AS chain""",
                    {"ids": ids})
    return {r["id"]: r["chain"] for r in rows}


def _expand(org: Org, ids: list[str]) -> dict[str, dict]:
    rows = org.read("recall.expand",
                    """UNWIND $ids AS sid
                       MATCH (s:Solution {id:sid})<-[:PRODUCED]-(se:Session)<-[:RAN]-(a:Dev)-[:MEMBER_OF]->(tm:Team)
                       OPTIONAL MATCH (se)-[:IN_PROJECT]->(p:Project)
                       OPTIONAL MATCH (s)-[:TAUGHT]->(l:Lesson)
                       WITH s, se, a, tm, p, collect(DISTINCT {text:l.text, kind:l.kind}) AS lessons
                       OPTIONAL MATCH (s)-[:FAILED_WITH]->(e:Error)
                       WITH s, se, a, tm, p, lessons, collect(DISTINCT e.signature) AS errors
                       OPTIONAL MATCH (s)-[:HIT]->(h:Error)
                       WITH s, se, a, tm, p, lessons, errors, collect(DISTINCT h.signature) AS hit
                       OPTIONAL MATCH (s)-[:BUILDS_ON]->(b:Solution)
                       WITH s, se, a, tm, p, lessons, errors, hit, collect(DISTINCT {id:b.id, title:b.title}) AS builds_on
                       OPTIONAL MATCH (:Session)-[r:REUSED]->(s)
                       WITH s, se, a, tm, p, lessons, errors, hit, builds_on,
                            sum(CASE WHEN r.outcome IN ['reused','worked'] THEN 1 ELSE 0 END) AS reuse_ok
                       OPTIONAL MATCH (s)-[:SOLVES]->(t:Task)
                       RETURN s.id AS id, s.title AS title, s.summary AS summary, s.code AS code,
                              s.status AS status, s.effort_minutes AS effort_minutes, s.attempts AS attempts,
                              s.tokens_spent AS tokens_spent, s.visibility AS visibility, s.created_at AS created_at,
                              se.id AS session_id, se.started_at AS session_started,
                              a.name AS author, tm.name AS team, p.name AS project,
                              lessons, errors, hit, builds_on, reuse_ok,
                              t.id AS task_id, t.text AS task_text""",
                    {"ids": ids})
    out = {}
    for r in rows:
        r["lessons"] = [l for l in r["lessons"] if l.get("text")]
        r["builds_on"] = [b for b in r["builds_on"] if b.get("id")]
        out[r["id"]] = r
    return out


def _path(matched_task: dict, chain: list[str], d: dict, titles: dict[str, str]) -> dict:
    nodes, links = [], []
    def add(n):
        if n["id"] not in {x["id"] for x in nodes}:
            nodes.append(n)
    tid = nid("Task", matched_task["task_id"])
    add({"id": tid, "label": "Task", "name": matched_task["task_text"]})
    first = nid("Solution", chain[0])
    add({"id": first, "label": "Solution", "name": titles.get(chain[0], chain[0])})
    links.append({"source": first, "target": tid, "type": "SOLVES"})
    for older, newer in zip(chain, chain[1:]):
        add({"id": nid("Solution", newer), "label": "Solution", "name": titles.get(newer, newer)})
        links.append({"source": nid("Solution", newer), "target": nid("Solution", older), "type": "SUPERSEDES"})
    sol = nid("Solution", d["id"])
    ses, dev, team = nid("Session", d["session_id"]), nid("Dev", d["author"]), nid("Team", d["team"])
    add({"id": ses, "label": "Session", "name": d["session_id"]})
    add({"id": dev, "label": "Dev", "name": d["author"], "team": d["team"]})
    add({"id": team, "label": "Team", "name": d["team"]})
    links += [{"source": ses, "target": sol, "type": "PRODUCED"},
              {"source": dev, "target": ses, "type": "RAN"},
              {"source": dev, "target": team, "type": "MEMBER_OF"}]
    if d.get("project"):
        pj = nid("Project", d["project"])
        add({"id": pj, "label": "Project", "name": d["project"]})
        links.append({"source": ses, "target": pj, "type": "IN_PROJECT"})
    for l in d["lessons"][:4]:
        ln = nid("Lesson", abs(hash(l["text"])) % 10**8)
        add({"id": ln, "label": "Lesson", "name": l["text"][:80]})
        links.append({"source": sol, "target": ln, "type": "TAUGHT"})
    return {"nodes": nodes, "links": links}


def _memory(d: dict, match: dict, sim: float, score: float, skipped: list[dict], path: dict) -> dict:
    return {
        "solution": {k: d[k] for k in ("id", "title", "summary", "code", "status", "effort_minutes",
                                       "attempts", "tokens_spent", "visibility", "created_at")},
        "task": {"id": d.get("task_id") or match["task_id"], "text": d.get("task_text") or match["task_text"]},
        "similarity": round(sim, 4), "score": round(score, 4),
        "author": {"name": d["author"], "team": d["team"]},
        "project": {"name": d["project"]} if d.get("project") else None,
        "session": {"id": d["session_id"], "started_at": d["session_started"]},
        "lessons": d["lessons"],
        "errors": [{"signature": e} for e in d["errors"] + d["hit"]],
        "skipped": skipped,
        "builds_on": d["builds_on"],
        "reuse_count": d["reuse_ok"],
        "tokens_saved_estimate": int((d.get("tokens_spent") or 0) * 0.8),
        "path": path,
    }


def recall(org: Org, query: str, viewer: str, k: int = 5, graph: bool = True) -> list[dict]:
    """graph=False is the 'vector-only' baseline: nearest task's solution, nothing else."""
    emb = embed(query)
    cands = _candidates(org, emb, viewer, n=max(k * 4, 12))
    if not cands:
        return []
    if not graph:
        seen, picked = set(), []
        for c in cands:
            if c["solution_id"] not in seen:
                seen.add(c["solution_id"])
                picked.append(c)
            if len(picked) == k:
                break
        details = _expand(org, [c["solution_id"] for c in picked])
        out = []
        for c in picked:
            d = details[c["solution_id"]]
            d = {**d, "lessons": [], "errors": [], "hit": [], "builds_on": []}  # a vector store has just the doc
            out.append(_memory(d, c, c["sim"], c["sim"], [], _path(c, [d["id"]], d, {d["id"]: d["title"]})))
        return out

    chains = _supersede_walk(org, list({c["solution_id"] for c in cands}))
    best: dict[str, dict] = {}            # newest solution id -> best matching candidate
    for c in cands:
        chain = chains.get(c["solution_id"], [c["solution_id"]])
        head = chain[-1]
        prev = best.get(head)
        longest = chain if prev is None or len(chain) > len(prev["chain"]) else prev["chain"]
        if prev is None or c["sim"] > prev["sim"]:
            best[head] = {**c, "chain": longest}
        else:
            prev["chain"] = longest   # keep the full history of what we walked past
    all_ids = list({i for b in best.values() for i in b["chain"]})
    details = _expand(org, all_ids)
    titles = {i: d["title"] for i, d in details.items()}
    results = []
    for head, c in best.items():
        d = details.get(head)
        if not d:
            continue
        skipped = []
        for old in c["chain"][:-1]:
            od = details.get(old, {})
            why = od.get("errors") or []
            skipped.append({"id": old, "title": od.get("title", old), "status": od.get("status", "superseded"),
                            "reason": f"failed with {why[0]}" if why else "superseded by a newer fix"})
        score = (c["sim"] * STATUS_FACTOR.get(d["status"], 0.5)
                 * _effort_boost(d["effort_minutes"], d["attempts"])
                 * (1 + 0.05 * math.log1p(d["reuse_ok"] or 0)))
        results.append(_memory(d, c, c["sim"], score, skipped, _path(c, c["chain"], d, titles)))
    results.sort(key=lambda m: m["score"], reverse=True)
    return results[:k]


# ---------------------------------------------------------------- lineage

def lineage(org: Org, solution_id: str) -> dict:
    rows = org.read("lineage.chain",
                    """MATCH (s:Solution {id:$id})
                       OPTIONAL MATCH up = (s)-[:BUILDS_ON|SUPERSEDES*1..6]->(anc:Solution)
                       WITH s, collect(up) AS ups
                       OPTIONAL MATCH down = (desc:Solution)-[:BUILDS_ON|SUPERSEDES*1..6]->(s)
                       WITH s, ups, collect(down) AS downs
                       UNWIND (ups + downs + [null]) AS p
                       WITH s, p WHERE p IS NOT NULL
                       UNWIND relationships(p) AS r
                       WITH DISTINCT startNode(r) AS a, endNode(r) AS b, type(r) AS rel
                       RETURN a.id AS from_id, b.id AS to_id, rel""", {"id": solution_id})
    ids = list({solution_id} | {r["from_id"] for r in rows} | {r["to_id"] for r in rows})
    info = org.read("lineage.nodes",
                    """UNWIND $ids AS i MATCH (s:Solution {id:i})<-[:PRODUCED]-(se:Session)<-[:RAN]-(d:Dev)-[:MEMBER_OF]->(t:Team)
                       OPTIONAL MATCH (se)-[:IN_PROJECT]->(p:Project)
                       RETURN s.id AS id, s.title AS title, s.status AS status, s.created_at AS created_at,
                              d.name AS dev, t.name AS team, p.name AS project""", {"ids": ids})
    chain = sorted(({"id": r["id"], "title": r["title"], "status": r["status"], "project": r["project"],
                     "author": {"name": r["dev"], "team": r["team"]}, "created_at": r["created_at"]}
                    for r in info), key=lambda x: x["created_at"] or 0)
    path = {"nodes": [{"id": nid("Solution", c["id"]), "label": "Solution", "name": c["title"],
                       "status": c["status"]} for c in chain],
            "links": [{"source": nid("Solution", r["from_id"]), "target": nid("Solution", r["to_id"]),
                       "type": r["rel"]} for r in rows]}
    return {"chain": chain, "edges": rows, "path": path}
