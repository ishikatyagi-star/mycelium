"""Org event stream for the live UI.

Every agent (MCP server, hooks, fleet) and the web app talk to the API, so the API process is the natural
hub: events are fanned out in-process to SSE subscribers. (We first used Redis pub/sub on the FalkorDB
instance, but FalkorDB Cloud's free tier does not grant PUBLISH/SUBSCRIBE, so we don't depend on it.)
Run the API with a single worker so all subscribers share one bus.

Events are best-effort notifications; the graph is the source of truth.
"""
from __future__ import annotations

import asyncio
import json
import threading

_lock = threading.Lock()
_subs: dict[str, set[tuple[asyncio.AbstractEventLoop, asyncio.Queue]]] = {}


def subscribe(org: str) -> tuple[asyncio.AbstractEventLoop, asyncio.Queue]:
    sub = (asyncio.get_running_loop(), asyncio.Queue(maxsize=500))
    with _lock:
        _subs.setdefault(org, set()).add(sub)
    return sub


def unsubscribe(org: str, sub) -> None:
    with _lock:
        _subs.get(org, set()).discard(sub)


def _offer(q: asyncio.Queue, msg: str) -> None:
    if not q.full():
        q.put_nowait(msg)


def publish(org: str, type_: str, **data) -> None:
    """Callable from any thread (sync FastAPI endpoints run in a threadpool)."""
    msg = json.dumps({"type": type_, **data}, default=str)
    with _lock:
        subs = list(_subs.get(org, ()))
    for loop, q in subs:
        try:
            loop.call_soon_threadsafe(_offer, q, msg)
        except RuntimeError:
            pass  # loop closed: subscriber is gone
