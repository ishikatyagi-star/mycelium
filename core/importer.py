"""Backfill: turn existing Claude Code transcripts (~/.claude/projects/<project>/<session>.jsonl) into org memory,
so a team adopting Mycelium starts with its history instead of an empty graph.

  PYTHONPATH=. uv run python -m core.importer <transcript.jsonl> --org graphhq --dev Ishika --project "Mobile 3.0" [--dry-run]

Pipeline: parse -> scrub secrets/PII -> segment by user prompt -> LLM proposes memories (or a heuristic
fallback) -> the normal write gate decides -> saved as finished sessions with real timestamps.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from . import llm
from .db import Org
from .memory import SaveRequest, end_session, save_solution, start_session

SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), "<redacted-key>"),
    (re.compile(r"xai-[A-Za-z0-9]{16,}"), "<redacted-key>"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "<redacted-token>"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "<redacted-aws-key>"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9\-._~+/]{16,}=*"), r"\1<redacted>"),
    (re.compile(r"(?i)((?:api[_-]?key|secret|password|passwd|token)\s*[=:]\s*)['\"]?[^\s'\"]{6,}"), r"\1<redacted>"),
    (re.compile(r"://[^/\s:@]+:[^/\s@]+@"), "://<redacted>@"),
    (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), "<email>"),
    (re.compile(r"\b[\w-]+(?:\.[\w-]+){3,}\.(?:cloud|internal|amazonaws\.com)\b"), "<host>"),
    (re.compile(r"/Users/[^/\s]+"), "~"),
    (re.compile(r"/home/[^/\s]+"), "~"),
]


def scrub(text: str) -> str:
    for pat, rep in SECRET_PATTERNS:
        text = pat.sub(rep, text)
    return text


def _text(content) -> tuple[str, list[str]]:
    """(plain text, error strings) from a message's content (str or list of blocks)."""
    if isinstance(content, str):
        return content, []
    texts, errors = [], []
    for b in content or []:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "text":
            texts.append(b.get("text", ""))
        elif b.get("type") == "tool_use":   # the agent's one-line intent for each action is good narrative
            desc = (b.get("input") or {}).get("description")
            if desc:
                texts.append(f"[action] {desc}")
        elif b.get("type") == "tool_result" and b.get("is_error"):
            c = b.get("content")
            errors.append(c if isinstance(c, str) else json.dumps(c)[:300])
        elif b.get("type") == "tool_result" and not b.get("is_error"):
            c = b.get("content")
            c = c if isinstance(c, str) else json.dumps(c)
            if any(k in c for k in ("Error", "Traceback", "error:", "FAILED", "Unauthorized")):
                errors.append(c[-300:])
    return "\n".join(texts), errors


CHUNK = 14  # long autonomous stretches are split so each chunk yields its own lessons


def parse(path: Path) -> list[dict]:
    """Segments: one per real user prompt (long stretches split into chunks of the assistant's narrative),
    with the tool errors that occurred along the way."""
    segments: list[dict] = []
    cur = None
    for line in path.read_text().splitlines():
        try:
            e = json.loads(line)
        except Exception:
            continue
        msg = e.get("message") or {}
        ts = e.get("timestamp")
        if e.get("type") == "user":
            text, errors = _text(msg.get("content"))
            if text.strip() and not text.lstrip().startswith(("<", "[Request interrupted")):
                cur = {"prompt": text.strip(), "assistant": [], "errors": [], "start": ts, "end": ts}
                segments.append(cur)
            elif cur is not None:
                cur["errors"] += errors
        elif e.get("type") == "assistant" and cur is not None:
            text, _ = _text(msg.get("content"))
            if text.strip():
                if len(cur["assistant"]) >= CHUNK:   # continue the same prompt in a fresh chunk
                    cur = {"prompt": cur["prompt"], "assistant": [], "errors": [], "start": ts, "end": ts,
                           "continued": True}
                    segments.append(cur)
                cur["assistant"].append(text.strip())
            cur["end"] = ts or cur["end"]
    for s in segments:
        s["prompt"] = scrub(s["prompt"])[:2000]
        s["assistant"] = [scrub(a)[:1500] for a in s["assistant"]]
        s["errors"] = [scrub(x)[:300] for x in s["errors"]][:10]
    return segments


def _ts(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())
    except Exception:
        return None


def propose(seg: dict) -> list[dict]:
    digest = (f"USER ASKED{' (earlier; this is a later stretch of the same work)' if seg.get('continued') else ''}:\n"
              f"{seg['prompt'][:1200]}\n\nAGENT SAID (in order):\n"
              + "\n---\n".join(seg["assistant"])[:9000]
              + ("\n\nERRORS HIT:\n" + "\n".join(seg["errors"][:6]) if seg["errors"] else ""))
    out = llm.chat_json(
        "You extract reusable engineering knowledge from an AI coding session for a company memory graph. "
        "Only keep things another engineer could reuse: a problem that was solved, how, and what was learned. "
        "Skip chit-chat, planning, and anything trivial. Never include secrets or personal data.",
        digest + '\n\nReturn {"memories": [{"task": str (the problem, one sentence), "title": str (<=90 chars), '
                 '"summary": str (2-4 sentences: what worked and why), "lessons": [{"text": str, "kind": '
                 '"pitfall"|"tip"|"dead_end"}], "libraries": [{"name": str, "version": str}]}]} '
                 "with 0-3 memories. Prefer concrete technical gotchas and fixes (exact error, root cause, fix).")
    if out and isinstance(out.get("memories"), list):
        return [m for m in out["memories"] if m.get("task") and m.get("title") and m.get("summary")]
    # heuristic fallback (no LLM): only segments where the agent clearly concluded something
    final = seg["assistant"][-1] if seg["assistant"] else ""
    if len(seg["prompt"]) < 25 or len(final) < 120:
        return []
    return [{"task": seg["prompt"][:300], "title": seg["prompt"][:90], "summary": final[:800],
             "lessons": [{"text": f"Hit: {e[:150]}", "kind": "dead_end"} for e in seg["errors"][:2]], "libraries": []}]


def import_transcript(path: Path, org: Org, dev: str, project: str | None, components: list[str],
                      dry_run: bool = False, limit: int = 40) -> list[dict]:
    results = []
    for seg in parse(path)[:limit]:
        for m in propose(seg):
            if dry_run:
                results.append({"dry_run": True, **m})
                continue
            start = _ts(seg["start"])
            s = start_session(org, dev, m["task"], components, project, agent="claude-code (imported)",
                              started_at=start, status="done")
            res = save_solution(org, SaveRequest(
                session_id=s["session_id"], title=m["title"], summary=m["summary"],
                lessons=m.get("lessons", []), libraries=m.get("libraries", []), errors=seg["errors"][:3],
                created_at=_ts(seg["end"]) or start))
            end_session(org, s["session_id"], ended_at=_ts(seg["end"]))
            results.append({"title": m["title"], **res})
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("--org", default="graphhq")
    ap.add_argument("--dev", required=True)
    ap.add_argument("--project")
    ap.add_argument("--components", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=40)
    a = ap.parse_args()
    res = import_transcript(Path(a.transcript), Org(a.org), a.dev, a.project,
                            [c for c in a.components.split(",") if c], a.dry_run, a.limit)
    print(json.dumps(res, indent=1)[:6000])
    print(f"{len(res)} memories {'proposed' if a.dry_run else 'imported'}; llm={'on' if llm.available() else 'off'}")


if __name__ == "__main__":
    main()
