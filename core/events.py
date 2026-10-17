"""Org event stream. FalkorDB runs on Redis, so we use its pub/sub as the bus:
any process (API, fleet, tests) that changes the graph publishes, and the API's
SSE endpoint streams them to the live org view."""
from __future__ import annotations

import json

from .db import client


def channel(org: str) -> str:
    return f"mycelium:{org}:events"


def publish(org: str, type_: str, **data) -> None:
    try:
        client().connection.publish(channel(org), json.dumps({"type": type_, **data}, default=str))
    except Exception:
        pass  # events are best-effort; the graph is the source of truth
