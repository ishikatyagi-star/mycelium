"""Live awareness: which agents are running right now, on what, and who overlaps with whom."""
from __future__ import annotations

from .db import Org, now

LIVE_WINDOW_S = 30 * 60      # a session with no heartbeat for 30 min is no longer live
OVERLAP_MIN_SIM = 0.70


def live_sessions(org: Org) -> list[dict]:
    rows = org.read("presence.live",
                    """MATCH (d:Dev)-[:RAN]->(s:Session {status:'live'})
                       WHERE s.last_seen >= $since
                       MATCH (d)-[:MEMBER_OF]->(t:Team)
                       OPTIONAL MATCH (s)-[:TOUCHES]->(c:Component)
                       WITH s, d, t, collect(DISTINCT c.name) AS components
                       OPTIONAL MATCH (s)-[o:OVERLAPS]-(s2:Session {status:'live'})<-[:RAN]-(d2:Dev)-[:MEMBER_OF]->(t2:Team)
                       RETURN s.id AS id, s.task AS task, s.agent AS agent, s.started_at AS started_at,
                              s.last_seen AS last_seen, d.name AS dev, t.name AS team, components,
                              collect(DISTINCT CASE WHEN s2 IS NULL THEN NULL ELSE
                                {session_id:s2.id, dev:{name:d2.name, team:t2.name}, task:s2.task, score:o.score} END) AS overlaps
                       ORDER BY started_at DESC""", {"since": now() - LIVE_WINDOW_S})
    for r in rows:
        r["dev"] = {"name": r.pop("dev"), "team": r.pop("team")}
        r["overlaps"] = [o for o in r["overlaps"] if o]
    return rows


def detect_overlaps(org: Org, session_id: str) -> list[dict]:
    """Find *other* live sessions working on a similar task right now and link them.

    Similar = the vector index says their tasks are close. The graph adds who/which team,
    and the OVERLAPS edge makes it visible to both agents (and the org view)."""
    rows = org.read("presence.overlap_candidates",
                    """MATCH (me:Session {id:$sid})-[:WORKED_ON]->(t:Task)
                       MATCH (me)<-[:RAN]-(md:Dev)-[:MEMBER_OF]->(mt:Team)
                       CALL db.idx.vector.queryNodes('Task','embedding',10,t.embedding) YIELD node AS ot, score
                       WITH me, md, mt, ot, 1 - score AS sim WHERE sim >= $min_sim
                       MATCH (other:Session {status:'live'})-[:WORKED_ON]->(ot)
                       WHERE other <> me AND other.last_seen >= $since
                       MATCH (other)<-[:RAN]-(od0:Dev) WHERE od0 <> md
                       MATCH (other)<-[:RAN]-(od:Dev)-[:MEMBER_OF]->(otm:Team)
                       RETURN DISTINCT other.id AS session_id, od.name AS dev, otm.name AS team,
                              other.task AS task, sim, otm <> mt AS cross_team,
                              other.started_at AS started_at
                       ORDER BY sim DESC LIMIT 5""",
                    {"sid": session_id, "min_sim": OVERLAP_MIN_SIM, "since": now() - LIVE_WINDOW_S})
    if rows:
        org.write("presence.link_overlaps",
                  """MATCH (me:Session {id:$sid}) UNWIND $others AS o
                     MATCH (s:Session {id:o.id})
                     MERGE (me)-[r:OVERLAPS]->(s) SET r.score = o.sim, r.at = $at""",
                  {"sid": session_id, "at": now(),
                   "others": [{"id": r["session_id"], "sim": r["sim"]} for r in rows]})
    return [{"session_id": r["session_id"], "dev": {"name": r["dev"], "team": r["team"]},
             "task": r["task"], "score": round(r["sim"], 3), "cross_team": r["cross_team"],
             "started_at": r["started_at"]} for r in rows]


def claim(org: Org, session_id: str) -> None:
    org.write("presence.claim",
              """MATCH (s:Session {id:$sid})-[:WORKED_ON]->(t:Task)
                 MERGE (s)-[c:CLAIMS]->(t) SET c.since = $at""", {"sid": session_id, "at": now()})


def expire_stale(org: Org) -> int:
    rows = org.write("presence.expire",
                     """MATCH (s:Session {status:'live'}) WHERE s.last_seen < $since
                        SET s.status = 'done', s.ended_at = s.last_seen RETURN count(s) AS n""",
                     {"since": now() - LIVE_WINDOW_S})
    return rows[0]["n"] if rows else 0
