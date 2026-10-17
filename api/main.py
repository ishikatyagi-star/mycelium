"""Mycelium HTTP API. The MCP server, Claude Code hooks, fleet agents and the web app all talk to this.

Public demo mode (MYC_PUBLIC=1): the shared demo org `acme` is read-only for anonymous
visitors; visitors who want to write get a private sandbox copy (POST /api/sandbox).
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from core import brain as B
from core import events
from core import memory as M
from core import messaging as Msg
from core import org as O
from core import presence as P
from core.db import DatabaseUnavailable, Org, client, current_trace, list_orgs, ping, start_trace
from core.schema import ensure_schema

PUBLIC = os.getenv("MYC_PUBLIC") == "1"
WRITE_TOKEN = os.getenv("MYC_WRITE_TOKEN", "")      # agents (MCP/fleet) send this to write to protected orgs
PROTECTED_ORGS = {"acme", "mycelium"} if PUBLIC else set()

SANDBOX_TTL_S = int(os.getenv("MYC_SANDBOX_TTL_S", str(3 * 3600)))
MAX_SANDBOXES = 40


def _sandbox_created(slug: str) -> int:
    """Sandbox slugs embed their creation time: sandbox_<hex epoch>_<rand>. Legacy slugs count as expired."""
    try:
        return int(slug.split("_")[1], 16)
    except (IndexError, ValueError):
        return 0


def janitor_once() -> dict:
    """Housekeeping: close sessions whose agent stopped heartbeating; delete old visitor sandboxes."""
    expired, deleted = 0, []
    orgs = list_orgs()
    for slug in orgs:
        if not slug.startswith("sandbox_"):
            expired += P.expire_stale(Org(slug))
    sandboxes = sorted((s for s in orgs if s.startswith("sandbox_")), key=_sandbox_created)
    for i, slug in enumerate(sandboxes):
        too_old = time.time() - _sandbox_created(slug) > SANDBOX_TTL_S
        too_many = len(sandboxes) - i > MAX_SANDBOXES
        if too_old or too_many:
            Org(slug).delete()
            deleted.append(slug)
    return {"expired_sessions": expired, "deleted_sandboxes": deleted}


async def janitor_loop():
    while True:
        try:
            r = await asyncio.to_thread(janitor_once)
            if r["expired_sessions"] or r["deleted_sandboxes"]:
                print("janitor:", r)
        except Exception as e:
            print("janitor error:", e)
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(_app):
    try:
        if "acme" not in list_orgs() and os.getenv("MYC_AUTOSEED", "1") == "1":
            from seed.acme import seed
            seed("acme")
        for slug in list_orgs():
            ensure_schema(Org(slug))
    except Exception as e:  # keep the API up; /api/health reports DB state
        print("startup warning:", e)
    task = asyncio.create_task(janitor_loop())
    yield
    task.cancel()


app = FastAPI(title="Mycelium", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ---------------------------------------------------------------- plumbing

_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def guard(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.method != "GET" and PUBLIC:
        ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0]
        q, t = _hits[ip], time.time()
        while q and q[0] < t - 60:
            q.popleft()
        if len(q) >= 60:
            return JSONResponse({"detail": "rate limited"}, status_code=429)
        q.append(t)
    start_trace()
    try:
        return await call_next(request)
    except DatabaseUnavailable as e:
        return JSONResponse({"detail": f"FalkorDB unavailable: {e}"}, status_code=503)


def org_for(slug: str, request: Request | None = None, write: bool = False) -> Org:
    """write=True: agent-identity writes (sessions, memory). In public mode these need the agent token on the
    shared demo org; visitors write freely in their own sandbox org. Questions and notices are open to
    visitors (rate-limited) so judges can try the live network."""
    if slug not in list_orgs():
        raise HTTPException(404, f"unknown org {slug!r}")
    if write and slug in PROTECTED_ORGS:
        if not (WRITE_TOKEN and request is not None and request.headers.get("x-myc-token") == WRITE_TOKEN):
            raise HTTPException(403, "the public demo org is read-only: create a sandbox (POST /api/sandbox)")
    return Org(slug)


def traced(payload: dict) -> dict:
    payload["trace"] = current_trace()
    return payload


def bad(e: Exception):
    raise HTTPException(400, str(e))


# ---------------------------------------------------------------- read endpoints

@app.get("/api/health")
def health():
    if not ping():
        return JSONResponse({"ok": False, "falkordb": False}, status_code=503)
    return {"ok": True, "falkordb": True, "orgs": list_orgs()}


@app.get("/api/orgs/{org}/overview")
def overview(org: str):
    return traced(O.overview(org_for(org)))


@app.get("/api/orgs/{org}/graph")
def graph(org: str, view: str = "org"):
    o = org_for(org)
    nodes: dict[str, dict] = {}
    links: list[dict] = []

    def n(label, key, name=None, **extra):
        i = f"{label}:{key}"
        nodes.setdefault(i, {"id": i, "label": label, "name": name or key, **extra})
        return i

    for r in o.read("graph.org", """MATCH (t:Team)-[:OWNS]->(c:Component)
                                     RETURN t.name AS team, c.name AS comp, c.category AS cat"""):
        links.append({"source": n("Team", r["team"]), "target": n("Component", r["comp"], team=r["team"],
                                                                     category=r["cat"]), "type": "OWNS"})
    for r in o.read("graph.deps", "MATCH (a:Component)-[:DEPENDS_ON]->(b:Component) RETURN a.name AS a, b.name AS b"):
        links.append({"source": n("Component", r["a"]), "target": n("Component", r["b"]), "type": "DEPENDS_ON"})
    if view in ("org", "all"):
        for r in o.read("graph.devs", "MATCH (d:Dev)-[:MEMBER_OF]->(t:Team) RETURN d.name AS d, t.name AS t"):
            links.append({"source": n("Dev", r["d"], team=r["t"]), "target": n("Team", r["t"]), "type": "MEMBER_OF"})
        for s in P.live_sessions(o):
            sid = n("Session", s["id"], s["task"], status="live", team=s["dev"]["team"], dev=s["dev"]["name"])
            links.append({"source": n("Dev", s["dev"]["name"], team=s["dev"]["team"]), "target": sid, "type": "RAN"})
            for c in s["components"]:
                links.append({"source": sid, "target": n("Component", c), "type": "TOUCHES"})
            for ov in s["overlaps"]:
                links.append({"source": sid, "target": f"Session:{ov['session_id']}", "type": "OVERLAPS"})
    if view in ("memory", "all"):
        for r in o.read("graph.memory", """MATCH (d:Dev)-[:RAN]->(:Session)-[:PRODUCED]->(s:Solution)
                                            WHERE s.visibility = 'org'
                                            OPTIONAL MATCH (s)-[r:SUPERSEDES|BUILDS_ON]->(o:Solution)
                                            RETURN d.name AS dev, s.id AS id, s.title AS title, s.status AS status,
                                                   s.effort_minutes AS effort, type(r) AS rel, o.id AS other"""):
            sid = n("Solution", r["id"], r["title"], status=r["status"], effort_minutes=r["effort"])
            links.append({"source": n("Dev", r["dev"]), "target": sid, "type": "AUTHORED"})
            if r["other"]:
                links.append({"source": sid, "target": f"Solution:{r['other']}", "type": r["rel"]})
    ids = set(nodes)
    links = [l for l in links if l["source"] in ids and l["target"] in ids]
    uniq = {(l["source"], l["target"], l["type"]): l for l in links}
    return {"nodes": list(nodes.values()), "links": list(uniq.values())}


@app.get("/api/orgs/{org}/live")
def live(org: str):
    o = org_for(org)
    return traced({"sessions": P.live_sessions(o)})


@app.get("/api/orgs/{org}/questions")
def questions(org: str):
    return {"threads": Msg.threads(org_for(org))}


@app.get("/api/orgs/{org}/lineage/{solution_id}")
def lineage(org: str, solution_id: str):
    return traced(M.lineage(org_for(org), solution_id))


@app.get("/api/orgs/{org}/brain")
def brain(org: str):
    return traced(B.brain(org_for(org)))


@app.get("/api/orgs/{org}/who_knows")
def who_knows(org: str, topic: str):
    return traced({"experts": B.who_knows(org_for(org), topic)})


@app.get("/api/orgs/{org}/solutions/{solution_id}")
def solution(org: str, solution_id: str):
    res = M._expand(org_for(org), [solution_id])
    if solution_id not in res:
        raise HTTPException(404, "unknown solution")
    return res[solution_id]


# ---------------------------------------------------------------- recall / ask (reads + logged questions)

class RecallBody(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    as_dev: str
    k: int = Field(5, ge=1, le=20)


@app.post("/api/orgs/{org}/recall")
def recall(org: str, body: RecallBody):
    o = org_for(org)
    if not O.dev_info(o, body.as_dev):
        raise HTTPException(400, f"unknown dev {body.as_dev!r}")
    return traced({"results": M.recall(o, body.query, body.as_dev, k=body.k)})


@app.post("/api/orgs/{org}/compare")
def compare(org: str, body: RecallBody):
    o = org_for(org)
    vector_only = M.recall(o, body.query, body.as_dev, k=body.k, graph=False)
    myc = M.recall(o, body.query, body.as_dev, k=body.k, graph=True)
    return traced({"vector_only": vector_only, "mycelium": myc})


class AskBody(BaseModel):
    question: str = Field(min_length=5, max_length=2000)
    as_dev: str | None = None
    session_id: str | None = None


@app.post("/api/orgs/{org}/ask")
def ask(org: str, body: AskBody, request: Request):
    o = org_for(org)
    try:
        return traced(Msg.ask_org(o, body.question, session_id=body.session_id, dev=body.as_dev))
    except ValueError as e:
        bad(e)


class AnswerBody(BaseModel):
    text: str = Field(min_length=2, max_length=8000)
    as_dev: str | None = None
    session_id: str | None = None
    save_as_memory: bool = True


@app.post("/api/orgs/{org}/questions/{qid}/answer")
def answer(org: str, qid: str, body: AnswerBody, request: Request):
    o = org_for(org, request, write=True)
    try:
        return Msg.answer(o, qid, body.text, session_id=body.session_id, dev=body.as_dev,
                          save_as_memory=body.save_as_memory)
    except ValueError as e:
        bad(e)


# ---------------------------------------------------------------- agent lifecycle (MCP server, hooks, fleet)

class SessionBody(BaseModel):
    dev: str
    task: str = Field(min_length=3, max_length=2000)
    components: list[str] = []
    project: str | None = None
    agent: str = "claude-code"
    session_id: str | None = None


@app.post("/api/orgs/{org}/sessions")
def start_session(org: str, body: SessionBody, request: Request):
    o = org_for(org, request, write=True)
    try:
        s = M.start_session(o, body.dev, body.task, body.components, body.project, body.agent,
                            session_id=body.session_id)
    except ValueError as e:
        bad(e)
    overlaps = P.detect_overlaps(o, s["session_id"])
    info = O.dev_info(o, body.dev)
    events.publish(org, "session_started", session_id=s["session_id"], dev=info, task=body.task,
                   components=s["components"])
    for ov in overlaps:
        events.publish(org, "overlap", a={"session_id": s["session_id"], "dev": info},
                       b={"session_id": ov["session_id"], "dev": ov["dev"]}, score=ov["score"], task=ov["task"])
    memories = M.recall(o, body.task, body.dev, k=3)
    return traced({**s, "overlaps": overlaps, "memories": memories})


class HeartbeatBody(BaseModel):
    components: list[str] = []
    attempts: int | None = None
    tokens: int | None = None
    task: str | None = None


@app.post("/api/orgs/{org}/sessions/{sid}/heartbeat")
def heartbeat(org: str, sid: str, body: HeartbeatBody, request: Request):
    o = org_for(org, request, write=True)
    comps = M.touch_session(o, sid, body.components, body.attempts, body.tokens)
    overlaps = P.detect_overlaps(o, sid)
    return {"components": comps, "overlaps": overlaps}


@app.post("/api/orgs/{org}/sessions/{sid}/end")
def end(org: str, sid: str, request: Request):
    o = org_for(org, request, write=True)
    M.end_session(o, sid)
    events.publish(org, "session_ended", session_id=sid)
    return {"ok": True}


@app.get("/api/orgs/{org}/sessions/{sid}/inbox")
def inbox(org: str, sid: str, peek: bool = False):
    return Msg.inbox(org_for(org), sid, mark_read=not peek)


class SaveBody(BaseModel):
    title: str
    summary: str
    code: str = ""
    libraries: list[dict] = []
    lessons: list[dict] = []
    errors: list[str] = []
    visibility: str = "org"
    builds_on: list[str] = []
    supersedes: list[str] = []
    effort_minutes: int | None = None
    attempts: int | None = None
    tokens_spent: int | None = None


@app.post("/api/orgs/{org}/sessions/{sid}/solutions")
def save(org: str, sid: str, body: SaveBody, request: Request):
    o = org_for(org, request, write=True)
    res = M.save_solution(o, M.SaveRequest(session_id=sid, **body.model_dump()))
    if res["decision"] == "ACCEPT":
        dev = o.read("api.dev_of_session", """MATCH (d:Dev)-[:RAN]->(:Session {id:$sid}), (d)-[:MEMBER_OF]->(t:Team)
                                              RETURN d.name AS name, t.name AS team""", {"sid": sid})
        events.publish(org, "memory_saved", solution_id=res["solution_id"], title=body.title,
                       dev=dev[0] if dev else None)
    return res


class OutcomeBody(BaseModel):
    solution_id: str
    worked: bool
    error: str | None = None


@app.post("/api/orgs/{org}/sessions/{sid}/outcome")
def outcome(org: str, sid: str, body: OutcomeBody, request: Request):
    o = org_for(org, request, write=True)
    res = M.report_outcome(o, sid, body.solution_id, body.worked, body.error)
    if body.worked:
        info = o.read("api.reuse_info", """MATCH (d:Dev)-[:RAN]->(:Session {id:$sid}), (d)-[:MEMBER_OF]->(t:Team)
                                           MATCH (s:Solution {id:$sol})<-[:PRODUCED]-(:Session)<-[:RAN]-(a:Dev)-[:MEMBER_OF]->(at:Team)
                                           RETURN d.name AS by, t.name AS by_team, a.name AS author, at.name AS author_team,
                                                  s.title AS title""", {"sid": sid, "sol": body.solution_id})
        if info:
            i = info[0]
            events.publish(org, "reuse", solution_id=body.solution_id, title=i["title"],
                           by={"name": i["by"], "team": i["by_team"]},
                           author={"name": i["author"], "team": i["author_team"]},
                           tokens_saved=res.get("tokens_saved", 0))
    return res


class NoticeBody(BaseModel):
    component: str
    text: str = Field(min_length=5, max_length=2000)
    kind: str = "interface_change"
    as_dev: str | None = None
    session_id: str | None = None
    depth: int = Field(3, ge=1, le=4)


@app.post("/api/orgs/{org}/notices")
def notice(org: str, body: NoticeBody, request: Request):
    o = org_for(org)
    try:
        return traced(Msg.announce_change(o, body.component, body.text, body.kind, body.session_id,
                                          body.as_dev, body.depth))
    except ValueError as e:
        bad(e)


class HandoffBody(BaseModel):
    notes: str = Field(min_length=5, max_length=8000)
    to_team: str | None = None


@app.post("/api/orgs/{org}/sessions/{sid}/handoff")
def handoff(org: str, sid: str, body: HandoffBody, request: Request):
    o = org_for(org, request, write=True)
    return Msg.handoff(o, sid, body.notes, body.to_team)


@app.post("/api/orgs/{org}/sessions/{sid}/pickup/{hid}")
def pickup(org: str, sid: str, hid: str, request: Request):
    o = org_for(org, request, write=True)
    return Msg.pick_up(o, hid, sid)


# ---------------------------------------------------------------- sandbox + events

@app.post("/api/sandbox")
def sandbox():
    slug = f"sandbox_{int(time.time()):x}_{secrets.token_hex(2)}"
    Org("acme").copy_to(slug)
    return {"org": slug, "expires_in_s": SANDBOX_TTL_S}


@app.get("/api/orgs/{org}/events")
async def stream(org: str, request: Request):
    org_for(org)

    async def gen():
        pubsub = client().connection.pubsub()
        pubsub.subscribe(events.channel(org))
        try:
            yield {"event": "hello", "data": json.dumps({"org": org})}
            last_ping = time.time()
            while not await request.is_disconnected():
                msg = await asyncio.to_thread(pubsub.get_message, ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("type") == "message":
                    data = msg["data"].decode() if isinstance(msg["data"], bytes) else msg["data"]
                    yield {"event": json.loads(data).get("type", "event"), "data": data}
                if time.time() - last_ping > 15:
                    last_ping = time.time()
                    yield {"event": "ping", "data": "{}"}
        finally:
            pubsub.close()

    return EventSourceResponse(gen())
