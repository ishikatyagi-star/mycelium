"""Mycelium MCP server: plugs any MCP client (Claude Code, Cursor, ...) into the org's shared context graph.

Install in Claude Code (from the repo root):
  scripts/install_claude.sh <project_dir> <dev> [org] [api] [project]
which runs: claude mcp add mycelium -e MYC_DEV=... -- uv run --project <repo> python <repo>/mcp_server/server.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# runnable as a plain script from any project directory (cwd stays the user's project)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from mcp_server import client as C  # noqa: E402

import logging  # noqa: E402
logging.getLogger("httpx").setLevel(logging.WARNING)

mcp = MCPServer("mycelium", instructions=(
    "Mycelium is your company's shared memory and coordination layer. "
    "BEFORE solving a non-trivial problem, call `recall` - someone in the org may already have solved it "
    "(possibly with days of effort). If you reuse a recalled solution, credit the author in your reply and "
    "call `report_outcome`. If nothing is in memory and you are blocked, `ask_org` routes your question to "
    "the agent or person most likely to know right now. When you change an interface others depend on, "
    "call `announce_change`. When you finish solving something non-trivial, call `save_solution` with the "
    "lessons and dead ends so the next agent does not repeat them."))


def _sid(task_hint: str = "working session") -> str:
    st, _ = C.ensure_session(task_hint)
    return st["session_id"]


@mcp.tool()
def recall(problem: str, k: int = 5) -> str:
    """Search the org's memory for past solutions to a problem (any team, any project, any time).
    Results skip stale/broken fixes (following SUPERSEDES), include lessons/dead ends, effort spent, and credit."""
    res = C.post("/recall", {"query": problem, "as_dev": C.cfg()["dev"], "k": k})["results"]
    if not res:
        return "Nothing in org memory matches this problem. Consider ask_org, then save_solution when solved."
    return f"{len(res)} memories (best first):\n\n" + "\n\n".join(C.fmt_memory(m) for m in res)


@mcp.tool()
def ask_org(question: str) -> str:
    """Ask the whole org. Answers from memory if the org already knows; otherwise routes the question,
    via the graph (component ownership, live agents touching those components, past solvers, PageRank),
    to the best agent/person, who answers asynchronously (check_inbox later)."""
    sid = _sid(question)
    r = C.post("/ask", {"question": question, "session_id": sid})
    if r["mode"] == "memory":
        return "Answered from org memory:\n\n" + C.fmt_memory(r["answer"])
    if r["mode"] == "routed":
        t = r["routed_to"]
        others = "; ".join(f"{c['dev']['name']} ({c['dev']['team']}, {c['score']})" for c in r["candidates"][1:4])
        return (f"Routed question [{r['question_id']}] to {t['dev']['name']} ({t['dev']['team']}) "
                f"via {'their live agent session ' + t['id'] if t['kind'] == 'session' else 'their inbox'}.\n"
                f"Why: {t['reason']}\nOther candidates: {others}\n"
                "The answer will show up in check_inbox / your next prompt context.")
    return r.get("message", "No one in the org graph relates to this yet.")


@mcp.tool()
def check_inbox() -> str:
    """Questions routed to you, change notices for components you touch, overlapping live work, open handoffs."""
    st = C.load_state()
    if not st.get("session_id"):
        return "No active Mycelium session yet."
    inbox = C.get(f"/sessions/{st['session_id']}/inbox")
    answers = [t for t in C.get("/questions")["threads"]
               if t["asker"]["name"] == C.cfg()["dev"] and t.get("answer")]
    text = C.fmt_inbox(inbox)
    if answers:
        text += "\n" + "\n".join(f"- ANSWER to your question '{a['text'][:80]}' from {a['answer']['by']['name']} "
                                 f"({a['answer']['by']['team']}): {a['answer']['text']}" for a in answers[:5])
    return text or "Inbox empty."


@mcp.tool()
def answer_question(question_id: str, answer: str) -> str:
    """Answer a question another agent routed to you. Your answer also becomes org memory."""
    r = C.post(f"/questions/{question_id}/answer", {"text": answer, "session_id": _sid()})
    return f"Answered. Saved to org memory as {r.get('memory_solution_id')}."


@mcp.tool()
def save_solution(title: str, summary: str, code: str = "", libraries: list[dict] | None = None,
                  lessons: list[dict] | None = None, errors: list[str] | None = None,
                  visibility: str = "org", builds_on: list[str] | None = None,
                  supersedes: list[str] | None = None, attempts: int | None = None,
                  effort_minutes: int | None = None) -> str:
    """Save what you just solved to org memory.
    lessons: [{"text": "...", "kind": "pitfall"|"tip"|"dead_end"}] - include dead ends you tried!
    libraries: [{"name": "pandas", "version": "2.2"}]. visibility: private|team|org.
    builds_on / supersedes: ids of recalled solutions this extends / replaces."""
    st = C.load_state()
    sid = st.get("session_id") or _sid(title)
    r = C.post(f"/sessions/{sid}/solutions", {
        "title": title, "summary": summary, "code": code, "libraries": libraries or [], "lessons": lessons or [],
        "errors": errors or [], "visibility": visibility, "builds_on": builds_on or [], "supersedes": supersedes or [],
        "attempts": attempts, "effort_minutes": effort_minutes})
    if r["decision"] == "ACCEPT":
        st = C.load_state()
        st["saved"] = True
        C.save_state(st)
        return f"Saved as {r['solution_id']}." + (f" Notes: {r['reasons']}" if r["reasons"] else "")
    return f"Rejected by the write gate: {r['reasons']}"


@mcp.tool()
def report_outcome(solution_id: str, worked: bool, error: str | None = None) -> str:
    """Report whether a recalled solution worked for you. Worked: credits the author (feeds expertise ranking).
    Failed: marks it broken with the error so future agents are warned."""
    r = C.post(f"/sessions/{_sid()}/outcome", {"solution_id": solution_id, "worked": worked, "error": error})
    return f"Recorded: {r}"


@mcp.tool()
def announce_change(component: str, description: str, kind: str = "interface_change") -> str:
    """Announce a change to a component (API/schema/config/behaviour). Mycelium walks DEPENDS_ON to find every
    live agent working on something that depends on it and warns them; owning teams get it if nobody is live."""
    r = C.post("/notices", {"component": component, "text": description, "kind": kind, "session_id": _sid()})
    hits = "\n".join(f"- {d['dev']['name']} ({d['dev']['team']}) live on {d['component']} (depth {d['depth']})"
                     for d in r["impact"]) or "- no live agents affected"
    teams = ", ".join(f"{t['team']} ({t['component']})" for t in r["team_deliveries"]) or "none"
    return f"Notice {r['notice_id']} on {r['component']} delivered to:\n{hits}\nTeam inboxes: {teams}"


@mcp.tool()
def handoff(notes: str, to_team: str | None = None) -> str:
    """Hand off unfinished work: notes on state, next steps, gotchas. Any agent (optionally on to_team) can pick it up."""
    r = C.post(f"/sessions/{_sid()}/handoff", {"notes": notes, "to_team": to_team})
    return f"Handoff {r['handoff_id']} created for task: {r.get('task')}"


@mcp.tool()
def pick_up_handoff(handoff_id: str) -> str:
    """Continue someone's handed-off work with their full context."""
    r = C.post(f"/sessions/{_sid()}/pickup/{handoff_id}")
    return (f"Picked up from {r.get('from_dev')}: {r.get('task')}\nNotes: {r.get('notes')}\n"
            f"Components: {r.get('components')}\nTheir solutions so far: {r.get('solutions')}")


@mcp.tool()
def touch_components(components: list[str]) -> str:
    """Declare which components you are working on (so related agents and change notices can find you)."""
    st = C.load_state()
    if not st.get("session_id"):
        st, _ = C.ensure_session(st.get("task") or "working session", components)
    r = C.post(f"/sessions/{st['session_id']}/heartbeat", {"components": components})
    ov = "\n".join(f"- {o['dev']['name']} ({o['dev']['team']}): {o['task']}" for o in r["overlaps"])
    return f"Now touching {r['components']}." + (f"\nOverlapping live work:\n{ov}" if ov else "")


@mcp.tool()
def who_knows(topic: str) -> str:
    """Who in the org knows most about a topic (past solutions x PageRank authority from reuse/answers)."""
    ex = C.get("/who_knows", topic=topic)["experts"]
    return "\n".join(f"- {e['dev']['name']} ({e['dev']['team']}) score {e['score']}: "
                     + "; ".join(x["title"] for x in e["evidence"][:3]) for e in ex) or "No one yet."


@mcp.tool()
def live_agents() -> str:
    """Which agents in the org are running right now and what they are working on."""
    s = C.get("/live")["sessions"]
    return "\n".join(f"- {x['dev']['name']} ({x['dev']['team']}) on {x['components']}: {x['task']}" for x in s) or "None."


@mcp.tool()
def lineage(solution_id: str) -> str:
    """How a solution evolved: what it builds on / supersedes, across projects and teams."""
    ch = C.get(f"/lineage/{solution_id}")["chain"]
    return "\n".join(f"{i+1}. {c['title']} [{c['id']}] - {c['author']['name']} ({c['author']['team']}), "
                     f"{c.get('project')}, {c['status']}" for i, c in enumerate(ch))


def main():
    mcp.run()


if __name__ == "__main__":
    main()
