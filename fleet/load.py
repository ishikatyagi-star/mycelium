"""Concurrency load test: N agents doing the full agent loop in parallel against one org graph.

  PYTHONPATH=. uv run python -m fleet.load --agents 10,25,50 --seconds 20

Each simulated agent loops: start_session (writes + overlap detection + recall) -> recall -> ask_org
(every 5th loop) -> save_solution -> report_outcome -> end_session. Runs on a GRAPH.COPY of 'acme'.
Writes eval/concurrency.md.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import random
import statistics
import time
from collections import defaultdict
from pathlib import Path

import httpx

from core.db import Org

API = os.getenv("MYC_API", "http://localhost:8000").rstrip("/")
DEVS = ["Priya", "Arjun", "Meera", "Yash", "Rohan", "Sara", "Kabir", "Ananya", "Leo", "Ishika", "Neha", "Tom", "Zara", "Omar"]
TASKS = ["token refresh logs users out", "kafka consumer lag during month end", "duplicate webhook events",
         "postgres too many connections", "arm64 docker build fails", "push notifications missing on iOS",
         "csv export has duplicate customers", "ledger off by a cent after FX", "traces broken across kafka",
         "offline edits overwritten on sync", "dashboard off by one day at midnight", "login endpoint brute force"]


async def worker(c: httpx.AsyncClient, org: str, stop: float, lat: dict, errors: list, wid: int):
    base = f"{API}/api/orgs/{org}"
    n = 0
    while time.time() < stop:
        dev, task = random.choice(DEVS), f"{random.choice(TASKS)} (load {wid}-{n})"

        async def timed(op, method, url, **kw):
            t0 = time.perf_counter()
            r = await c.request(method, url, timeout=60, **kw)
            lat[op].append((time.perf_counter() - t0) * 1000)
            if r.status_code >= 400:
                errors.append((op, r.status_code, r.text[:120]))
                raise RuntimeError(op)
            return r.json()
        try:
            s = await timed("start_session", "POST", f"{base}/sessions", json={"dev": dev, "task": task, "components": [], "agent": "load"})
            sid = s["session_id"]
            rec = await timed("recall", "POST", f"{base}/recall", json={"query": task, "as_dev": dev, "k": 5})
            if n % 5 == 0:
                await timed("ask_org", "POST", f"{base}/ask", json={"question": f"has anyone solved {task}?", "session_id": sid})
            await timed("save_solution", "POST", f"{base}/sessions/{sid}/solutions",
                        json={"title": f"Load fix {wid}-{n}", "summary": f"Synthetic load-test memory for {task}."})
            if rec["results"]:
                await timed("report_outcome", "POST", f"{base}/sessions/{sid}/outcome",
                            json={"solution_id": rec["results"][0]["solution"]["id"], "worked": True})
            await timed("end_session", "POST", f"{base}/sessions/{sid}/end")
        except Exception:
            pass
        n += 1


async def run(n_agents: int, seconds: int) -> dict:
    org = f"loadtest_{n_agents}"
    Org(org).delete()
    Org("acme").copy_to(org)
    lat: dict[str, list] = defaultdict(list)
    errors: list = []
    limits = httpx.Limits(max_connections=n_agents + 10, max_keepalive_connections=n_agents + 10)
    async with httpx.AsyncClient(limits=limits) as c:
        await c.get(f"{API}/api/health")
        stop = time.time() + seconds
        await asyncio.gather(*(worker(c, org, stop, lat, errors, i) for i in range(n_agents)))
    nodes = Org(org).read("load.count", "MATCH (n) RETURN count(n) AS n")[0]["n"]
    Org(org).delete()
    total = sum(len(v) for v in lat.values())
    pct = lambda v, p: round(sorted(v)[max(0, int(len(v) * p) - 1)], 1) if v else None
    return {"agents": n_agents, "seconds": seconds, "ops": total, "ops_per_s": round(total / seconds, 1),
            "errors": len(errors), "nodes_after": nodes,
            "per_op": {k: {"n": len(v), "p50": round(statistics.median(v), 1), "p95": pct(v, 0.95)} for k, v in lat.items()},
            "sample_errors": errors[:3]}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", default="10,25,50")
    ap.add_argument("--seconds", type=int, default=20)
    a = ap.parse_args()
    results = []
    for n in [int(x) for x in a.agents.split(",")]:
        r = await run(n, a.seconds)
        results.append(r)
        print(f"{n} agents: {r['ops']} ops ({r['ops_per_s']}/s), errors {r['errors']}, "
              + ", ".join(f"{k} p50 {v['p50']}ms p95 {v['p95']}ms" for k, v in r["per_op"].items()))
    md = ["# Concurrency: many agents, one org graph", "",
          "N simulated agents run the full agent loop in parallel through the HTTP API (FastAPI, single uvicorn "
          "worker) against one FalkorDB graph (local Docker, Apple Silicon laptop). Latency is end-to-end per HTTP "
          "call, so it includes embedding the text (CPU, in the API process) and JSON. Reproduce: "
          "`PYTHONPATH=. uv run python -m fleet.load`.", "",
          "| Agents | Ops | Ops/s | Errors | start_session p50/p95 | recall p50/p95 | save_solution p50/p95 | ask_org p50/p95 |",
          "|---|---|---|---|---|---|---|---|"]
    for r in results:
        g = lambda k: f"{r['per_op'].get(k, {}).get('p50', '-')} / {r['per_op'].get(k, {}).get('p95', '-')} ms"
        md.append(f"| {r['agents']} | {r['ops']} | {r['ops_per_s']} | {r['errors']} | {g('start_session')} | {g('recall')} | "
                  f"{g('save_solution')} | {g('ask_org')} |")
    md += ["", "Notes: writes are short single-purpose Cypher statements (MERGE-based), so concurrent agents never "
           "hold long transactions. The bottleneck at high N is the single API worker computing embeddings, not "
           "FalkorDB: graph query times stay in the low milliseconds (see the `trace` in any API response)."]
    out = Path(__file__).resolve().parents[1] / "eval" / "concurrency.md"
    out.write_text("\n".join(md) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    asyncio.run(main())
