"""Company brain: who knows what, what knowledge is at risk, and how help flows between teams."""
from __future__ import annotations

from collections import defaultdict

from .db import Org
from .embed import embed
from .messaging import pagerank


def who_knows(org: Org, topic: str, k: int = 5) -> list[dict]:
    """Topic relevance (vector over past tasks) x authority (PageRank over CREDITS) x effort invested."""
    rows = org.read("brain.who_knows",
                    """CALL db.idx.vector.queryNodes('Task','embedding',15,vecf32($emb)) YIELD node AS t, score
                       WITH t, 1 - score AS sim WHERE sim >= 0.65
                       MATCH (t)<-[:SOLVES]-(s:Solution)<-[:PRODUCED]-(:Session)<-[:RAN]-(d:Dev)-[:MEMBER_OF]->(tm:Team)
                       RETURN d.name AS dev, tm.name AS team, s.id AS sol, s.title AS title, sim,
                              s.effort_minutes AS effort, s.status AS status""", {"emb": embed(topic)})
    pr = pagerank(org)
    agg: dict[str, dict] = defaultdict(lambda: {"score": 0.0, "evidence": []})
    for r in rows:
        a = agg[r["dev"]]
        a["dev"] = {"name": r["dev"], "team": r["team"]}
        a["score"] += r["sim"] ** 3 * (1.0 if r["status"] == "active" else 0.5)
        a["evidence"].append({"solution_id": r["sol"], "title": r["title"], "similarity": round(r["sim"], 3)})
    out = [{"dev": a["dev"], "score": round(a["score"] * (1 + 0.5 * pr.get(d, 0)), 3),
            "pagerank": round(pr.get(d, 0), 4), "evidence": a["evidence"][:4]} for d, a in agg.items()]
    return sorted(out, key=lambda x: x["score"], reverse=True)[:k]


def experts(org: Org, k: int = 10) -> list[dict]:
    pr = pagerank(org)
    rows = org.read("brain.helped",
                    """MATCH (d:Dev)-[:MEMBER_OF]->(t:Team)
                       OPTIONAL MATCH (other:Dev)-[c:CREDITS]->(d)
                       RETURN d.name AS dev, t.name AS team, coalesce(sum(c.count), 0) AS helped""")
    out = [{"dev": {"name": r["dev"], "team": r["team"]}, "pagerank": round(pr.get(r["dev"], 0), 4),
            "helped": r["helped"]} for r in rows]
    return sorted(out, key=lambda x: (x["pagerank"], x["helped"]), reverse=True)[:k]


def knowledge_at_risk(org: Org, k: int = 10) -> list[dict]:
    """Hard-won fixes that only their author ever touched: if they leave, it's gone."""
    return [{"solution_id": r["id"], "title": r["title"], "owner": {"name": r["dev"], "team": r["team"]},
             "effort_minutes": r["effort"], "attempts": r["attempts"]}
            for r in org.read("brain.at_risk",
                              """MATCH (s:Solution {status:'active'})<-[:PRODUCED]-(:Session)<-[:RAN]-(d:Dev)-[:MEMBER_OF]->(t:Team)
                                 WHERE s.effort_minutes >= 240
                                 OPTIONAL MATCH (other:Session)-[:REUSED]->(s)
                                 OPTIONAL MATCH (other)<-[:RAN]-(od:Dev) WHERE od <> d
                                 WITH s, d, t, count(DISTINCT od) AS others
                                 WHERE others = 0
                                 RETURN s.id AS id, s.title AS title, d.name AS dev, t.name AS team,
                                        s.effort_minutes AS effort, s.attempts AS attempts
                                 ORDER BY effort DESC LIMIT $k""", {"k": k})]


def savings(org: Org) -> list[dict]:
    return org.read("brain.savings",
                    """MATCH (d:Dev)-[:RAN]->(:Session)-[r:REUSED]->(:Solution)
                       WHERE r.outcome IN ['reused','worked']
                       MATCH (d)-[:MEMBER_OF]->(t:Team)
                       RETURN t.name AS team, sum(r.tokens_saved) AS tokens_saved, count(r) AS reuses
                       ORDER BY tokens_saved DESC""")


def help_flows(org: Org) -> list[dict]:
    """Team -> team: how often one team's knowledge (reused fixes, answers) helped another."""
    return org.read("brain.help_flows",
                    """MATCH (a:Dev)-[c:CREDITS]->(b:Dev)
                       MATCH (a)-[:MEMBER_OF]->(ta:Team), (b)-[:MEMBER_OF]->(tb:Team)
                       WHERE ta <> tb
                       RETURN tb.name AS from_team, ta.name AS to_team, sum(c.count) AS count
                       ORDER BY count DESC""")


def brain(org: Org) -> dict:
    return {"experts": experts(org), "at_risk": knowledge_at_risk(org), "savings": savings(org),
            "help_flows": help_flows(org)}
