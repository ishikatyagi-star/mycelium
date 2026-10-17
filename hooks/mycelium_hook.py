"""Claude Code hooks: make Mycelium ambient, so the agent doesn't have to remember to use it.

  SessionStart      -> tell the agent it is connected (org, identity, live agents nearby)
  UserPromptSubmit  -> first prompt: register a Mycelium session for this task, inject the best memories
                       and overlapping live work. Later prompts: heartbeat + inject new inbox items
                       (questions routed to you, change notices, overlaps, handoffs).
  PostToolUse       -> during long autonomous runs, check the inbox at most once a minute
  Stop              -> once per session, nudge the agent to save what it learned
  SessionEnd        -> mark the Mycelium session done

Never blocks the agent on failure: any error -> no output.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp_server import client as C  # noqa: E402


def emit(event: str, context: str) -> None:
    if context:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}))


def inbox_text(st: dict) -> str:
    inbox = C.get(f"/sessions/{st['session_id']}/inbox")
    text = C.fmt_inbox(inbox)
    answers = [t for t in C.get("/questions")["threads"]
               if t["asker"]["name"] == C.cfg()["dev"] and t.get("answer")
               and t["id"] not in st.get("seen_answers", [])]
    if answers:
        st.setdefault("seen_answers", []).extend(a["id"] for a in answers)
        text += ("\n" if text else "") + "\n".join(
            f"- ANSWER to your question '{a['text'][:80]}' from {a['answer']['by']['name']} "
            f"({a['answer']['by']['team']}): {a['answer']['text']}" for a in answers)
    return text


def on_session_start(inp: dict) -> None:
    st = C.load_state(inp.get("cwd"))
    if st.get("session_id") and not st.get("ended"):   # previous agent session never closed: close it
        try:
            C.post(f"/sessions/{st['session_id']}/end")
        except Exception:
            pass
        st["ended"] = True
        C.save_state(st, inp.get("cwd"))
    c = C.cfg()
    live = C.get("/live")["sessions"]
    emit("SessionStart",
         f"[Mycelium] Connected to org '{c['org']}' as {c['dev']}. {len(live)} other agents are live in the org. "
         "Use the mycelium tools: recall before solving, ask_org when blocked, announce_change when you change "
         "an interface others depend on, save_solution when done.")


def on_prompt(inp: dict) -> None:
    cwd, prompt = inp.get("cwd"), (inp.get("prompt") or "").strip()
    if not prompt or prompt.startswith("/"):
        return
    st, started = C.ensure_session(prompt[:500], cwd=cwd)
    parts = []
    if started:
        mems = [m for m in started.get("memories", []) if m["similarity"] >= 0.72]
        if mems:
            parts.append("[Mycelium] The org has solved similar problems before. Reuse them, credit the author, "
                         "and call report_outcome:\n\n" + "\n\n".join(C.fmt_memory(m, with_code=False) for m in mems))
        if started.get("overlaps"):
            parts.append("[Mycelium] Live overlapping work in the org right now:\n" + "\n".join(
                f"- {o['dev']['name']} ({o['dev']['team']}): '{o['task']}' (session {o['session_id']})"
                for o in started["overlaps"]))
    else:
        C.post(f"/sessions/{st['session_id']}/heartbeat", {})
    box = inbox_text(st)
    if box:
        parts.append("[Mycelium] Inbox:\n" + box)
    st["last_inbox"] = time.time()
    C.save_state(st, cwd)
    emit("UserPromptSubmit", "\n\n".join(parts))


def on_post_tool(inp: dict) -> None:
    st = C.load_state(inp.get("cwd"))
    if not st.get("session_id") or time.time() - st.get("last_inbox", 0) < 60:
        return
    st["last_inbox"] = time.time()
    C.post(f"/sessions/{st['session_id']}/heartbeat", {})
    box = inbox_text(st)
    C.save_state(st, inp.get("cwd"))
    emit("PostToolUse", "[Mycelium] New in your inbox:\n" + box if box else "")


def on_stop(inp: dict) -> None:
    st = C.load_state(inp.get("cwd"))
    if not st.get("session_id") or st.get("saved") or st.get("nudged") or inp.get("stop_hook_active"):
        return
    st["nudged"] = True
    C.save_state(st, inp.get("cwd"))
    print(json.dumps({"decision": "block", "reason":
        "[Mycelium] If you solved something non-trivial in this session, call save_solution (title, summary, "
        "lessons incl. dead ends you tried, libraries, builds_on/supersedes ids of anything you reused) so the "
        "next agent in the org doesn't repeat it. If nothing is worth saving, just stop."}))


def on_session_end(inp: dict) -> None:
    st = C.load_state(inp.get("cwd"))
    if st.get("session_id") and not st.get("ended"):
        C.post(f"/sessions/{st['session_id']}/end")
        st["ended"] = True
        C.save_state(st, inp.get("cwd"))


HANDLERS = {"session-start": on_session_start, "prompt": on_prompt, "post-tool": on_post_tool,
            "stop": on_stop, "session-end": on_session_end}

if __name__ == "__main__":
    try:
        inp = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    except Exception:
        inp = {}
    try:
        HANDLERS[sys.argv[1]](inp)
    except Exception as e:  # never break the user's agent
        print(f"mycelium hook skipped: {e}", file=sys.stderr)
