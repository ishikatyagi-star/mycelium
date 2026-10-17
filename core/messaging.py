"""Agent-to-agent coordination across the org.

* ask_org: answer from memory if the org already knows; otherwise route the question,
  through the graph, to the agent or person most likely to know *right now*.
* answer: an agent answers from its own session context; the answer becomes memory.
* announce_change: a change to a component ripples over DEPENDS_ON to every live agent
  working on something that depends on it (and to owning teams if nobody is live).
* handoff / pick_up: unfinished work becomes a node any agent can continue.
"""
from __future__ import annotations

from collections import defaultdict

from . import events
from .db import Org, now
from .embed import embed
from .ids import new_id, nid
from .memory import SaveRequest, end_session, recall, record_reuse, save_solution, start_session
from .presence import LIVE_WINDOW_S

ANSWER_FROM_MEMORY_SIM = 0.80
MAX_IMPACT_DEPTH = 4


def _asker(org: Org, session_id: str | None, dev: str | None) -> dict:
    if session_id:
        rows = org.read("ask.asker_session",
                        """MATCH (d:Dev)-[:RAN]->(s:Session {id:$sid}), (d)-[:MEMBER_OF]->(t:Team)
                           RETURN d.name AS dev, t.name AS team""", {"sid": session_id})
    else:
        rows = org.read("ask.asker_dev",
                        "MATCH (d:Dev {name:$dev})-[:MEMBER_OF]->(t:Team) RETURN d.name AS dev, t.name AS team",
                        {"dev": dev})
    if not rows:
        raise ValueError("unknown asker (session or dev not in org graph)")
    return rows[0]


def pagerank(org: Org) -> dict[str, float]:
    """Expertise authority: devs credited by devs who are themselves credited rank higher."""
    try:
        rows = org.read("brain.pagerank",
                        "CALL algo.pageRank('Dev','CREDITS') YIELD node, score RETURN node.name AS dev, score")
        top = max((r["score"] for r in rows), default=0) or 1
        return {r["dev"]: r["score"] / top for r in rows}   # normalised: 1.0 = most credited
    except Exception:
        return {}


def route(org: Org, question: str, asker_dev: str, emb: list[float] | None = None) -> list[dict]:
    """Rank who should get this question. Every candidate carries the graph evidence (path)."""
    emb = emb or embed(question)
    since = now() - LIVE_WINDOW_S
    # 1) what part of the org is this about? components touched while solving similar tasks
    comp_rows = org.read("route.components_from_similar_work",
                         """CALL db.idx.vector.queryNodes('Task','embedding',8,vecf32($emb)) YIELD node AS t, score
                            WITH t, 1 - score AS sim WHERE sim >= 0.68
                            MATCH (t)<-[:WORKED_ON]-(:Session)-[:TOUCHES]->(c:Component)
                            RETURN c.name AS component, max(sim) AS w""", {"emb": emb})
    comps = {r["component"]: min(1.0, (r["w"] - 0.6) / 0.3) for r in comp_rows}
    mentioned = org.read("route.components_mentioned",
                         "MATCH (c:Component) WHERE toLower($q) CONTAINS toLower(c.name) RETURN c.name AS component",
                         {"q": question})
    for r in mentioned:
        comps[r["component"]] = 1.0
    comp_list = [{"name": k, "w": v} for k, v in comps.items()]

    cand: dict[str, dict] = defaultdict(lambda: {"by_kind": defaultdict(float), "reasons": [], "links": [], "nodes": {}})

    def add(dev, team, pts, reason, nodes, links, session=None, kind="other"):
        c = cand[dev]
        c["dev"] = {"name": dev, "team": team}
        c["by_kind"][kind] = max(c["by_kind"][kind], pts)   # strongest evidence of each kind, no piling up
        c["reasons"].append(reason)
        for n in nodes:
            c["nodes"][n["id"]] = n
        c["links"] += links
        if session:
            c["session"] = session

    qid = "Question:new"
    # 2) live agents touching those components right now
    if comp_list:
        for r in org.read("route.live_on_components",
                          """UNWIND $comps AS cw MATCH (c:Component {name:cw.name})
                             MATCH (d:Dev)-[:RAN]->(s:Session {status:'live'})-[:TOUCHES]->(c)
                             WHERE s.last_seen >= $since AND d.name <> $asker
                             MATCH (d)-[:MEMBER_OF]->(t:Team)
                             RETURN d.name AS dev, t.name AS team, s.id AS sid, s.task AS task, c.name AS component, cw.w AS w""",
                          {"comps": comp_list, "since": since, "asker": asker_dev}):
            add(r["dev"], r["team"], 3.0 * r["w"],
                f"agent is live on {r['component']} right now ({r['task'][:60]})",
                [{"id": nid("Component", r["component"]), "label": "Component", "name": r["component"]},
                 {"id": nid("Session", r["sid"]), "label": "Session", "name": r["task"][:60]},
                 {"id": nid("Dev", r["dev"]), "label": "Dev", "name": r["dev"], "team": r["team"]}],
                [{"source": qid, "target": nid("Component", r["component"]), "type": "ABOUT"},
                 {"source": nid("Session", r["sid"]), "target": nid("Component", r["component"]), "type": "TOUCHES"},
                 {"source": nid("Dev", r["dev"]), "target": nid("Session", r["sid"]), "type": "RAN"}],
                session=r["sid"], kind="live")
        # 3) owners of those components
        for r in org.read("route.owners",
                          """UNWIND $comps AS cw MATCH (t:Team)-[:OWNS]->(c:Component {name:cw.name})
                             MATCH (d:Dev)-[:MEMBER_OF]->(t) WHERE d.name <> $asker
                             RETURN d.name AS dev, t.name AS team, c.name AS component, cw.w AS w""",
                          {"comps": comp_list, "asker": asker_dev}):
            add(r["dev"], r["team"], 0.8 * r["w"], f"{r['team']} owns {r['component']}",
                [{"id": nid("Component", r["component"]), "label": "Component", "name": r["component"]},
                 {"id": nid("Team", r["team"]), "label": "Team", "name": r["team"]},
                 {"id": nid("Dev", r["dev"]), "label": "Dev", "name": r["dev"], "team": r["team"]}],
                [{"source": qid, "target": nid("Component", r["component"]), "type": "ABOUT"},
                 {"source": nid("Team", r["team"]), "target": nid("Component", r["component"]), "type": "OWNS"},
                 {"source": nid("Dev", r["dev"]), "target": nid("Team", r["team"]), "type": "MEMBER_OF"}], kind="owner")
    # 4) people who solved similar problems before (any status: even a failed attempt is experience)
    for r in org.read("route.past_solvers",
                      """CALL db.idx.vector.queryNodes('Task','embedding',8,vecf32($emb)) YIELD node AS t, score
                         WITH t, 1 - score AS sim WHERE sim >= 0.6
                         MATCH (t)<-[:SOLVES]-(s:Solution)<-[:PRODUCED]-(:Session)<-[:RAN]-(d:Dev)-[:MEMBER_OF]->(tm:Team)
                         WHERE d.name <> $asker
                         RETURN d.name AS dev, tm.name AS team, s.id AS sol, s.title AS title, sim""",
                      {"emb": emb, "asker": asker_dev}):
        add(r["dev"], r["team"], 2.0 * r["sim"], f"solved a similar problem: '{r['title']}' (sim {r['sim']:.2f})",
            [{"id": nid("Solution", r["sol"]), "label": "Solution", "name": r["title"]},
             {"id": nid("Dev", r["dev"]), "label": "Dev", "name": r["dev"], "team": r["team"]}],
            [{"source": qid, "target": nid("Solution", r["sol"]), "type": "SIMILAR_TO"},
             {"source": nid("Dev", r["dev"]), "target": nid("Solution", r["sol"]), "type": "AUTHORED"}], kind="solver")
    # 5) authority: PageRank over who-credits-whom
    pr = pagerank(org)
    out = []
    for dev, c in cand.items():
        score = sum(c["by_kind"].values()) * (1 + 0.5 * pr.get(dev, 0.0))
        out.append({"kind": "session" if c.get("session") else "dev",
                    "id": c.get("session") or dev, "dev": c["dev"], "score": round(score, 3),
                    "reason": "; ".join(dict.fromkeys(c["reasons"]))[:400],
                    "path": {"nodes": [{"id": qid, "label": "Question", "name": question[:80]}] + list(c["nodes"].values()),
                             "links": [dict(t) for t in {tuple(l.items()) for l in c["links"]}]}})
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


def ask_org(org: Org, question: str, session_id: str | None = None, dev: str | None = None) -> dict:
    asker = _asker(org, session_id, dev)
    emb = embed(question)
    qid = new_id("q")
    org.write("ask.create_question",
              """CREATE (q:Question {id:$qid, text:$text, embedding:vecf32($emb), status:'open', at:$at})
                 WITH q MATCH (d:Dev {name:$dev}) MERGE (d)-[:ASKED]->(q)""",
              {"qid": qid, "text": question, "emb": emb, "at": now(), "dev": asker["dev"]})
    if session_id:
        org.write("ask.link_session", "MATCH (s:Session {id:$sid}), (q:Question {id:$qid}) MERGE (s)-[:ASKED]->(q)",
                  {"sid": session_id, "qid": qid})
    events.publish(org.slug, "question_asked", question_id=qid, text=question,
                   asker={"name": asker["dev"], "team": asker["team"]})

    mem = recall(org, question, asker["dev"], k=5)
    direct = sorted((m for m in mem if m["similarity"] >= ANSWER_FROM_MEMORY_SIM
                     and m["solution"]["status"] == "active"), key=lambda m: m["similarity"], reverse=True)
    if direct:
        top = direct[0]
        org.write("ask.answered_from_memory",
                  """MATCH (q:Question {id:$qid}), (s:Solution {id:$sol})
                     SET q.status = 'answered', q.mode = 'memory' MERGE (q)-[:ANSWERED_BY]->(s)""",
                  {"qid": qid, "sol": top["solution"]["id"]})
        if session_id:
            record_reuse(org, session_id, top["solution"]["id"])
        return {"question_id": qid, "mode": "memory", "answer": top,
                "also": [m for m in mem if m["solution"]["id"] != top["solution"]["id"]],
                "routed_to": None, "candidates": [], "path": top["path"]}

    cands = route(org, question, asker["dev"], emb)
    if not cands:
        org.write("ask.not_found", "MATCH (q:Question {id:$qid}) SET q.status='unrouted', q.mode='not_found'",
                  {"qid": qid})
        return {"question_id": qid, "mode": "not_found", "answer": None, "routed_to": None,
                "candidates": [], "path": {"nodes": [], "links": []},
                "message": "Nothing in the org graph relates to this yet: no memory, no owner, no live agent."}
    top = cands[0]
    target_match = ("MATCH (x:Session {id:$tid})" if top["kind"] == "session" else "MATCH (x:Dev {name:$tid})")
    org.write("ask.route",
              f"""MATCH (q:Question {{id:$qid}}) {target_match}
                  MERGE (q)-[r:ROUTED_TO]->(x) SET r.reason=$reason, r.score=$score, r.at=$at
                  SET q.status='routed', q.mode='routed'
                  WITH q UNWIND $comps AS cn MATCH (c:Component {{name:cn}}) MERGE (q)-[:ABOUT]->(c)""",
              {"qid": qid, "tid": top["id"], "reason": top["reason"], "score": top["score"], "at": now(),
               "comps": [n["name"] for n in top["path"]["nodes"] if n["label"] == "Component"]})
    for n in top["path"]["nodes"]:
        if n["id"] == "Question:new":
            n["id"] = nid("Question", qid)
    for l in top["path"]["links"]:
        if l["source"] == "Question:new":
            l["source"] = nid("Question", qid)
    events.publish(org.slug, "question_routed", question_id=qid,
                   to={"kind": top["kind"], "id": top["id"], "dev": top["dev"]}, reason=top["reason"])
    return {"question_id": qid, "mode": "routed", "answer": None, "also": mem,
            "routed_to": {k: top[k] for k in ("kind", "id", "dev", "reason", "score")},
            "candidates": [{k: c[k] for k in ("kind", "id", "dev", "reason", "score")} for c in cands[:5]],
            "path": top["path"]}


def answer(org: Org, question_id: str, text: str, session_id: str | None = None,
           dev: str | None = None, save_as_memory: bool = True) -> dict:
    who = _asker(org, session_id, dev)
    q = org.read("answer.question",
                 """MATCH (asker:Dev)-[:ASKED]->(q:Question {id:$qid})
                    RETURN q.text AS text, q.status AS status, asker.name AS asker""", {"qid": question_id})
    if not q:
        raise ValueError("unknown question")
    q = q[0]
    aid = new_id("ans")
    org.write("answer.create",
              """MATCH (q:Question {id:$qid}), (d:Dev {name:$dev})
                 CREATE (a:Answer {id:$aid, text:$text, at:$at})
                 MERGE (d)-[:ANSWERED]->(a) MERGE (a)-[:ANSWERS]->(q)
                 SET q.status = 'answered'
                 WITH d MATCH (asker:Dev {name:$asker}) WHERE asker <> d
                 MERGE (asker)-[c:CREDITS]->(d) SET c.count = coalesce(c.count,0) + 1""",
              {"qid": question_id, "dev": who["dev"], "aid": aid, "text": text, "at": now(), "asker": q["asker"]})
    # The answer becomes org memory, so the next agent with this question never has to ask.
    # A short 'answer' session makes the Solution SOLVE the question's own task.
    if not save_as_memory:
        events.publish(org.slug, "answer", question_id=question_id, by={"name": who["dev"], "team": who["team"]},
                       text=text[:300])
        return {"ok": True, "answer_id": aid, "memory_solution_id": None}
    tmp = start_session(org, who["dev"], q["text"], agent="answer", status="done")
    end_session(org, tmp["session_id"])
    saved = save_solution(org, SaveRequest(session_id=tmp["session_id"], title=f"Q: {q['text'][:120]}",
                                           summary=text, visibility="org", effort_minutes=5))
    if saved.get("solution_id"):
        org.write("answer.link_memory", "MATCH (a:Answer {id:$aid}), (s:Solution {id:$sol}) MERGE (a)-[:BECAME]->(s)",
                  {"aid": aid, "sol": saved["solution_id"]})
    events.publish(org.slug, "answer", question_id=question_id, by={"name": who["dev"], "team": who["team"]},
                   text=text[:300])
    return {"ok": True, "answer_id": aid, "memory_solution_id": saved.get("solution_id")}


def announce_change(org: Org, component: str, text: str, kind: str = "interface_change",
                    session_id: str | None = None, dev: str | None = None, depth: int = 3) -> dict:
    who = _asker(org, session_id, dev)
    depth = int(depth)
    if not 1 <= depth <= MAX_IMPACT_DEPTH:
        raise ValueError("depth must be 1..4")
    exists = org.read("notice.component", "MATCH (c:Component) WHERE toLower(c.name)=toLower($c) RETURN c.name AS name",
                      {"c": component})
    if not exists:
        raise ValueError(f"unknown component {component!r}")
    component = exists[0]["name"]
    notice_id = new_id("ntc")
    org.write("notice.create",
              """MATCH (c:Component {name:$c}), (d:Dev {name:$dev})
                 CREATE (n:Notice {id:$id, kind:$kind, text:$text, at:$at})
                 MERGE (d)-[:ANNOUNCED]->(n) MERGE (n)-[:AFFECTS]->(c)""",
              {"c": component, "dev": who["dev"], "id": notice_id, "kind": kind, "text": text, "at": now()})
    if session_id:
        org.write("notice.link_session", "MATCH (s:Session {id:$sid}), (n:Notice {id:$id}) MERGE (s)-[:ANNOUNCED]->(n)",
                  {"sid": session_id, "id": notice_id})
    # Variable-length bounds cannot be query parameters in FalkorDB: depth is validated above, then inlined.
    impact = org.read("notice.impact",
                      f"""MATCH (c:Component {{name:$c}})
                          MATCH p = (dep:Component)-[:DEPENDS_ON*1..{depth}]->(c)
                          WITH dep, p ORDER BY length(p)
                          WITH dep, collect(p)[0] AS p
                          OPTIONAL MATCH (t:Team)-[:OWNS]->(dep)
                          RETURN dep.name AS component, length(p) AS depth,
                                 [n IN nodes(p) | n.name] AS chain, t.name AS owner""", {"c": component})
    affected = [{"component": component, "depth": 0, "chain": [component], "owner": None}] + impact
    live = org.read("notice.live_sessions",
                    """UNWIND $comps AS cn
                       MATCH (d:Dev)-[:RAN]->(s:Session {status:'live'})-[:TOUCHES]->(:Component {name:cn})
                       WHERE s.last_seen >= $since AND d.name <> $me
                       MATCH (d)-[:MEMBER_OF]->(t:Team)
                       RETURN DISTINCT s.id AS sid, d.name AS dev, t.name AS team, cn AS component""",
                    {"comps": [a["component"] for a in affected], "since": now() - LIVE_WINDOW_S, "me": who["dev"]})
    by_comp = {a["component"]: a for a in affected}
    # one delivery per session: the closest affected component wins
    live = sorted(live, key=lambda r: by_comp[r["component"]]["depth"])
    seen_sessions: set[str] = set()
    deliveries, covered = [], set()
    for r in live:
        covered.add(r["component"])
        if r["sid"] in seen_sessions:
            continue
        seen_sessions.add(r["sid"])
        a = by_comp[r["component"]]
        chain = a["chain"]
        nodes = [{"id": nid("Component", n), "label": "Component", "name": n} for n in chain]
        links = [{"source": nid("Component", x), "target": nid("Component", y), "type": "DEPENDS_ON"}
                 for x, y in zip(chain, chain[1:])]
        nodes += [{"id": nid("Session", r["sid"]), "label": "Session", "name": r["sid"]},
                  {"id": nid("Dev", r["dev"]), "label": "Dev", "name": r["dev"], "team": r["team"]}]
        links += [{"source": nid("Session", r["sid"]), "target": nid("Component", chain[0]), "type": "TOUCHES"},
                  {"source": nid("Dev", r["dev"]), "target": nid("Session", r["sid"]), "type": "RAN"}]
        deliveries.append({"session_id": r["sid"], "dev": {"name": r["dev"], "team": r["team"]},
                           "component": r["component"], "depth": a["depth"], "path": {"nodes": nodes, "links": links}})
    if deliveries:
        org.write("notice.deliver_sessions",
                  """MATCH (n:Notice {id:$id}) UNWIND $sids AS sid MATCH (s:Session {id:sid})
                     MERGE (n)-[r:DELIVERED_TO]->(s) SET r.at=$at, r.read=false""",
                  {"id": notice_id, "sids": [d["session_id"] for d in deliveries], "at": now()})
    team_deliveries = [{"team": a["owner"], "component": a["component"]} for a in impact
                       if a["component"] not in covered and a["owner"]]
    if team_deliveries:
        org.write("notice.deliver_teams",
                  """MATCH (n:Notice {id:$id}) UNWIND $teams AS tn MATCH (t:Team {name:tn})
                     MERGE (n)-[r:DELIVERED_TO]->(t) SET r.at=$at""",
                  {"id": notice_id, "teams": list({t["team"] for t in team_deliveries}), "at": now()})
    events.publish(org.slug, "notice", notice_id=notice_id, component=component, text=text,
                   by={"name": who["dev"], "team": who["team"]},
                   delivered_to=[{"session_id": d["session_id"], "dev": d["dev"]} for d in deliveries])
    return {"notice_id": notice_id, "component": component, "impact": deliveries,
            "affected_components": affected, "team_deliveries": team_deliveries}


def handoff(org: Org, session_id: str, notes: str, to_team: str | None = None) -> dict:
    hid = new_id("hof")
    rows = org.write("handoff.create",
                     """MATCH (d:Dev)-[:RAN]->(s:Session {id:$sid})-[:WORKED_ON]->(t:Task)
                        CREATE (h:Handoff {id:$hid, notes:$notes, at:$at, status:'open'})
                        MERGE (s)-[:HANDED_OFF]->(h) MERGE (h)-[:FOR_TASK]->(t)
                        RETURN d.name AS dev, t.text AS task""",
                     {"sid": session_id, "hid": hid, "notes": notes, "at": now()})
    if to_team:
        org.write("handoff.to_team", "MATCH (h:Handoff {id:$hid}), (t:Team {name:$team}) MERGE (h)-[:FOR]->(t)",
                  {"hid": hid, "team": to_team})
    r = rows[0] if rows else {}
    events.publish(org.slug, "handoff", handoff_id=hid, **{"from": {"name": r.get("dev")}}, task=r.get("task"))
    return {"handoff_id": hid, **r}


def pick_up(org: Org, handoff_id: str, session_id: str) -> dict:
    rows = org.write("handoff.pick_up",
                     """MATCH (h:Handoff {id:$hid})<-[:HANDED_OFF]-(old:Session)<-[:RAN]-(d:Dev), (new:Session {id:$sid})
                        SET h.status='taken' MERGE (new)-[:PICKED_UP]->(h)
                        WITH h, old, d
                        OPTIONAL MATCH (old)-[:TOUCHES]->(c:Component)
                        WITH h, old, d, collect(DISTINCT c.name) AS components
                        OPTIONAL MATCH (old)-[:PRODUCED]->(s:Solution)
                        RETURN h.notes AS notes, old.task AS task, d.name AS from_dev, components,
                               collect(DISTINCT {id:s.id, title:s.title}) AS solutions""",
                     {"hid": handoff_id, "sid": session_id})
    return rows[0] if rows else {}


def inbox(org: Org, session_id: str, mark_read: bool = True) -> dict:
    me = org.read("inbox.me", """MATCH (d:Dev)-[:RAN]->(s:Session {id:$sid}), (d)-[:MEMBER_OF]->(t:Team)
                                 RETURN d.name AS dev, t.name AS team, s.started_at AS started_at""",
                  {"sid": session_id})
    if not me:
        return {"questions": [], "notices": [], "overlaps": [], "handoffs": []}
    me = me[0]
    questions = org.read("inbox.questions",
                         """MATCH (asker:Dev)-[:ASKED]->(q:Question {status:'routed'})-[r:ROUTED_TO]->(x)
                            WHERE (x:Session AND x.id = $sid) OR (x:Dev AND x.name = $dev)
                            MATCH (asker)-[:MEMBER_OF]->(at:Team)
                            RETURN q.id AS question_id, q.text AS text, asker.name AS asker, at.name AS asker_team,
                                   r.reason AS reason, q.at AS at ORDER BY at""",
                         {"sid": session_id, "dev": me["dev"]})
    notices = org.read("inbox.notices",
                       """MATCH (by:Dev)-[:ANNOUNCED]->(n:Notice)-[r:DELIVERED_TO]->(x)
                          WHERE ((x:Session AND x.id = $sid AND r.read = false) OR (x:Team AND x.name = $team AND n.at >= $since))
                          MATCH (n)-[:AFFECTS]->(c:Component)
                          RETURN DISTINCT n.id AS notice_id, n.text AS text, n.kind AS kind, c.name AS component,
                                 by.name AS by, n.at AS at ORDER BY at""",
                       {"sid": session_id, "team": me["team"], "since": me["started_at"] - 24 * 3600})
    overlaps = org.read("inbox.overlaps",
                        """MATCH (me:Session {id:$sid})-[o:OVERLAPS]-(s:Session {status:'live'})<-[:RAN]-(d:Dev)-[:MEMBER_OF]->(t:Team)
                           RETURN DISTINCT s.id AS session_id, d.name AS dev, t.name AS team, s.task AS task, o.score AS score""",
                        {"sid": session_id})
    handoffs = org.read("inbox.handoffs",
                        """MATCH (from:Dev)-[:RAN]->(:Session)-[:HANDED_OFF]->(h:Handoff {status:'open'})-[:FOR_TASK]->(t:Task)
                           OPTIONAL MATCH (h)-[:FOR]->(tm:Team)
                           WITH h, t, from, tm WHERE tm IS NULL OR tm.name = $team
                           RETURN h.id AS handoff_id, h.notes AS notes, t.text AS task, from.name AS from_dev, h.at AS at""",
                        {"team": me["team"]})
    if mark_read and notices:
        org.write("inbox.mark_read",
                  """MATCH (n:Notice)-[r:DELIVERED_TO]->(s:Session {id:$sid}) SET r.read = true""", {"sid": session_id})
    return {"questions": questions, "notices": notices, "overlaps": overlaps, "handoffs": handoffs}


def threads(org: Org, limit: int = 50) -> list[dict]:
    rows = org.read("threads.list",
                    """MATCH (asker:Dev)-[:ASKED]->(q:Question)
                       MATCH (asker)-[:MEMBER_OF]->(at:Team)
                       OPTIONAL MATCH (q)-[r:ROUTED_TO]->(x)
                       OPTIONAL MATCH (x)<-[:RAN]-(xd:Dev)
                       OPTIONAL MATCH (q)<-[:ANSWERS]-(a:Answer)<-[:ANSWERED]-(ad:Dev)-[:MEMBER_OF]->(adt:Team)
                       OPTIONAL MATCH (q)-[:ANSWERED_BY]->(ms:Solution)
                       RETURN q.id AS id, q.text AS text, q.status AS status, q.mode AS mode, q.at AS at,
                              asker.name AS asker, at.name AS asker_team,
                              CASE WHEN x IS NULL THEN NULL ELSE coalesce(xd.name, x.name) END AS routed_dev,
                              r.reason AS reason, a.text AS answer, ad.name AS answered_by, adt.name AS answered_team,
                              ms.title AS memory_title, ms.id AS memory_id
                       ORDER BY at DESC LIMIT $limit""", {"limit": limit})
    return [{"id": r["id"], "text": r["text"], "status": r["status"], "mode": r["mode"], "at": r["at"],
             "asker": {"name": r["asker"], "team": r["asker_team"]},
             "routed_to": r["routed_dev"], "reason": r["reason"],
             "answer": ({"text": r["answer"], "by": {"name": r["answered_by"], "team": r["answered_team"]}}
                        if r["answer"] else None),
             "memory": ({"id": r["memory_id"], "title": r["memory_title"]} if r["memory_id"] else None)}
            for r in rows]
