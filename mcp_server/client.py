"""Thin HTTP client shared by the MCP server and the Claude Code hooks.

Agents never touch FalkorDB directly: they call the Mycelium API, so teammates on
different machines share one org graph just by pointing MYC_API at the same server.
The active Mycelium session for a project directory lives in `.mycelium/session.json`.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()


def cfg() -> dict:
    return {"api": os.getenv("MYC_API", "http://localhost:8000").rstrip("/"),
            "org": os.getenv("MYC_ORG", "graphhq"),
            "dev": os.getenv("MYC_DEV", ""),
            "project": os.getenv("MYC_PROJECT") or None,
            "token": os.getenv("MYC_WRITE_TOKEN", "")}


def _url(path: str) -> str:
    c = cfg()
    return f"{c['api']}/api/orgs/{c['org']}{path}"


def _headers() -> dict:
    t = cfg()["token"]
    return {"x-myc-token": t} if t else {}


def get(path: str, **params) -> dict:
    r = httpx.get(_url(path), params=params, headers=_headers(), timeout=20)
    r.raise_for_status()
    return r.json()


def post(path: str, body: dict | None = None) -> dict:
    r = httpx.post(_url(path), json=body or {}, headers=_headers(), timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"Mycelium API {r.status_code}: {r.text[:300]}")
    return r.json()


# ---------------------------------------------------------------- session state per project dir

def state_path(cwd: str | None = None) -> Path:
    return Path(cwd or os.getcwd()) / ".mycelium" / "session.json"


def load_state(cwd: str | None = None) -> dict:
    p = state_path(cwd)
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def save_state(state: dict, cwd: str | None = None) -> None:
    p = state_path(cwd)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=1))


def ensure_session(task: str, components: list[str] | None = None, cwd: str | None = None) -> tuple[dict, dict | None]:
    """Return (state, start_response_or_None). Starts a Mycelium session if none is active."""
    st = load_state(cwd)
    c = cfg()
    if st.get("session_id") and st.get("org") == c["org"] and not st.get("ended"):
        return st, None
    res = post("/sessions", {"dev": c["dev"], "task": task, "components": components or [],
                             "project": c["project"], "agent": "claude-code"})
    st = {"session_id": res["session_id"], "org": c["org"], "dev": c["dev"], "task": task,
          "saved": False, "nudged": False, "last_inbox": 0}
    save_state(st, cwd)
    return st, res


# ---------------------------------------------------------------- formatting for agents (compact, readable)

def fmt_effort(minutes: int | None, attempts: int | None) -> str:
    m = minutes or 0
    span = f"{m // 480} working day(s)" if m >= 480 else (f"{m // 60}h" if m >= 60 else f"{m}m")
    return f"{span}, {attempts or 0} attempts"


def fmt_memory(m: dict, with_code: bool = True) -> str:
    s = m["solution"]
    lines = [f"### {s['title']}  [{s['id']}]",
             f"Credit: {m['author']['name']} ({m['author']['team']})"
             + (f", project {m['project']['name']}" if m.get("project") else "")
             + f", session {m['session']['id']} | effort {fmt_effort(s['effort_minutes'], s['attempts'])}"
             + f" | similarity {m['similarity']:.2f} | reused {int(m['reuse_count'] or 0)}x"
             + f" | ~{m['tokens_saved_estimate']:,} tokens saved if reused",
             s["summary"]]
    for sk in m.get("skipped", []):
        lines.append(f"- SKIPPED stale fix '{sk['title']}' [{sk['id']}]: {sk['reason']}")
    for l in m.get("lessons", []):
        lines.append(f"- {l['kind'].upper()}: {l['text']}")
    if m.get("builds_on"):
        lines.append("- builds on: " + ", ".join(f"{b['title']} [{b['id']}]" for b in m["builds_on"]))
    if with_code and s.get("code"):
        lines.append("```\n" + s["code"][:1500] + "\n```")
    return "\n".join(lines)


def fmt_inbox(inbox: dict) -> str:
    out = []
    for q in inbox.get("questions", []):
        out.append(f"- QUESTION for you from {q['asker']} ({q['asker_team']}) [{q['question_id']}]: {q['text']}\n"
                   f"  (routed to you because: {q['reason'][:200]}). Answer with answer_question if you know.")
    for n in inbox.get("notices", []):
        out.append(f"- CHANGE NOTICE from {n['by']} on {n['component']}: {n['text']}")
    for o in inbox.get("overlaps", []):
        out.append(f"- OVERLAP: {o['dev']} ({o['team']}) is working on a similar task right now: '{o['task']}' "
                   f"(session {o['session_id']}). Consider ask_org or coordinating.")
    for h in inbox.get("handoffs", []):
        out.append(f"- OPEN HANDOFF from {h['from_dev']} [{h['handoff_id']}]: {h['task']} | notes: {h['notes'][:200]}")
    return "\n".join(out)
