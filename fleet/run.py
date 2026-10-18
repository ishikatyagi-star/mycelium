"""Agent fleet: simulated agents across the org's teams, running concurrently against the Mycelium API.

They start sessions, reuse what the org already knows, ask the org when stuck, announce changes,
answer questions routed to them (with Grok, from their own task context + org memory), save what
they learn, and hand off. Real people join the same org from Claude Code via the MCP server.

  PYTHONPATH=. uv run python -m fleet.run                 # all fleet agents, continuous
  PYTHONPATH=. uv run python -m fleet.run --hold          # stay on the first task (live demo standby)
  PYTHONPATH=. uv run python -m fleet.run --agents Meera,Kabir --step 4
"""
from __future__ import annotations

import argparse
import asyncio
import os
import random

import httpx
from dotenv import load_dotenv

from core import llm
from fleet.scenarios import FLEET

load_dotenv()

API = os.getenv("MYC_API", "http://localhost:8000").rstrip("/")
ORG = os.getenv("MYC_ORG", "acme")
HEADERS = {"x-myc-token": os.getenv("MYC_WRITE_TOKEN", "")}


def log(dev: str, msg: str) -> None:
    print(f"[{dev:>7}] {msg}", flush=True)


async def call(c: httpx.AsyncClient, method: str, path: str, **kw) -> dict:
    r = await c.request(method, f"{API}/api/orgs/{ORG}{path}", headers=HEADERS, timeout=60, **kw)
    r.raise_for_status()
    return r.json()


def _related(a: str, b: str) -> float:
    import numpy as np
    from core.embed import embed
    x, y = np.array(embed(a)), np.array(embed(b))
    return float(x @ y / (np.linalg.norm(x) * np.linalg.norm(y)))


def answer_text(dev: str, team: str, sc: dict, question: str, memories: list[dict]) -> tuple[str, bool]:
    """Returns (answer, is_knowledge). 'I don't know' answers are delivered but never stored as memory."""
    context = "\n".join(f"- {m['solution']['title']} ({m['author']['name']}): {m['solution']['summary']}"
                        for m in memories[:3])
    out = llm.chat(
        f"You are the AI coding agent of {dev} on the {team} team at Acme. You are currently working on: "
        f"'{sc['task']}' (components: {', '.join(sc['components'])}). Another agent in the company routed a "
        "question to you. Answer in 1-3 sentences, concretely, from your own work context and the org memory "
        "below. If you genuinely do not know, say so and suggest who might.",
        f"Your private working notes: {sc.get('knows', '(none)')}\nOrg memory:\n{context or '(none)'}\n\n"
        f"Question: {question}\nIf you do not know, start your reply with 'UNSURE:'.", max_tokens=220)
    if out:
        return out.removeprefix("UNSURE:").strip(), not out.startswith("UNSURE")
    if sc.get("knows") and _related(question, sc["task"] + " " + sc["knows"]) >= 0.6:
        return sc["knows"], True
    if memories and memories[0]["similarity"] >= 0.7:
        m = memories[0]
        return f"Not from my current task, but {m['author']['name']} solved this: {m['solution']['summary']}", False
    return f"I'm on '{sc['task']}' and haven't hit that; I don't know. Try the owning team.", False


def solution_for(dev: str, sc: dict, memories: list[dict]) -> dict:
    reused = memories[0] if memories and memories[0]["similarity"] >= 0.75 else None
    gen = llm.chat_json(
        "You write concise engineering memory entries for a company knowledge graph.",
        f"Task: {sc['task']}\nComponents: {sc['components']}\n"
        + (f"We reused: {reused['solution']['title']}: {reused['solution']['summary']}\n" if reused else "")
        + 'Return {"title": str (<=90 chars), "summary": str (2-3 sentences, what fixed it), '
          '"lessons": [{"text": str, "kind": "pitfall"|"tip"|"dead_end"}] (1-3 items)}')
    if not gen or not gen.get("title"):
        gen = {"title": f"Fix: {sc['task'][:80]}",
               "summary": f"Resolved '{sc['task']}' on {', '.join(sc['components'])}."
                          + (f" Reused {reused['author']['name']}'s approach: {reused['solution']['title']}." if reused else ""),
               "lessons": []}
    return {"title": gen["title"][:150], "summary": gen.get("summary", "")[:1500] or "Resolved.",
            "lessons": [l for l in gen.get("lessons", []) if isinstance(l, dict)][:3],
            "builds_on": [reused["solution"]["id"]] if reused else [],
            "effort_minutes": random.randint(20, 240), "attempts": random.randint(1, 6)}


async def agent(dev: str, team: str, tasks: list[dict], step: float, hold: bool, work_steps: int):
    async with httpx.AsyncClient() as c:
        i = 0
        await asyncio.sleep(random.uniform(0, step * 2))
        while True:
            sc = tasks[i % len(tasks)]
            try:
                s = await call(c, "POST", "/sessions", json={"dev": dev, "task": sc["task"],
                                                              "components": sc["components"], "agent": "fleet"})
                sid, memories = s["session_id"], s.get("memories", [])
                log(dev, f"started '{sc['task'][:60]}' ({len(memories)} memories, {len(s['overlaps'])} overlaps)")
                if (i < len(tasks) and memories and memories[0]["similarity"] >= 0.75   # credit once per task, not per cycle
                        and memories[0]["solution"]["status"] == "active" and memories[0]["author"]["name"] != dev):
                    await asyncio.sleep(step)
                    await call(c, "POST", f"/sessions/{sid}/outcome",
                               json={"solution_id": memories[0]["solution"]["id"], "worked": True})
                    log(dev, f"reused {memories[0]['author']['name']}'s '{memories[0]['solution']['title'][:50]}'")
                if sc.get("ask"):
                    await asyncio.sleep(step)
                    r = await call(c, "POST", "/ask", json={"question": sc["ask"], "session_id": sid})
                    log(dev, f"asked org -> {r['mode']}"
                        + (f" -> {r['routed_to']['dev']['name']}" if r.get("routed_to") else ""))
                if sc.get("announce"):
                    await asyncio.sleep(step)
                    comp, text = sc["announce"]
                    r = await call(c, "POST", "/notices", json={"component": comp, "text": text, "session_id": sid})
                    log(dev, f"announced change on {comp} -> {len(r['impact'])} live agents")
                n = 0
                while hold or n < work_steps:
                    n += 1
                    await asyncio.sleep(step * random.uniform(0.7, 1.4))
                    await call(c, "POST", f"/sessions/{sid}/heartbeat", json={})
                    inbox = await call(c, "GET", f"/sessions/{sid}/inbox")
                    for q in inbox["questions"]:
                        rec = (await call(c, "POST", "/recall", json={"query": q["text"], "as_dev": dev, "k": 3}))["results"]
                        text, knowledge = await asyncio.to_thread(answer_text, dev, team, sc, q["text"], rec)
                        await call(c, "POST", f"/questions/{q['question_id']}/answer",
                                   json={"text": text, "session_id": sid, "save_as_memory": knowledge})
                        log(dev, f"answered {q['asker']}: {text[:70]}")
                if i < len(tasks):   # learn once per task; later cycles only add live activity
                    sol = await asyncio.to_thread(solution_for, dev, sc, memories)
                    r = await call(c, "POST", f"/sessions/{sid}/solutions", json=sol)
                    log(dev, f"saved '{sol['title'][:60]}' -> {r['decision']}")
                await call(c, "POST", f"/sessions/{sid}/end")
            except Exception as e:
                log(dev, f"error: {str(e)[:160]}")
                await asyncio.sleep(step * 3)
            i += 1


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", default=",".join(FLEET))
    ap.add_argument("--step", type=float, default=6.0, help="seconds between agent actions")
    ap.add_argument("--work-steps", type=int, default=12)
    ap.add_argument("--hold", action="store_true", help="stay live on the first task, keep answering")
    a = ap.parse_args()
    async with httpx.AsyncClient() as c:
        teams = {d: t["name"] for t in (await call(c, "GET", "/overview"))["teams"] for d in t["devs"]}
    names = [n.strip() for n in a.agents.split(",") if n.strip() in FLEET]
    print(f"fleet: {names} -> {API} org={ORG} llm={'on' if llm.available() else 'off (fallbacks)'}")
    await asyncio.gather(*(agent(n, teams[n], FLEET[n], a.step, a.hold, a.work_steps) for n in names))


if __name__ == "__main__":
    asyncio.run(main())
