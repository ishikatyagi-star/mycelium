"""FalkorDB access layer.

Every query goes through `Org.read` / `Org.write` so that:
  * reads use GRAPH.RO_QUERY (the read-only path can never mutate memory),
  * each call is recorded in a per-request trace (powers "Show Cypher" in the UI),
  * one org == one FalkorDB graph (`org_<slug>`), which is our tenant boundary.
"""
from __future__ import annotations

import contextvars
import os
import re
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
from falkordb import FalkorDB

load_dotenv()

_SLUG = re.compile(r"^[a-z0-9_]{1,40}$")

# Per-request trace of executed Cypher (contextvar so concurrent API requests don't mix).
_trace: contextvars.ContextVar[list | None] = contextvars.ContextVar("trace", default=None)


class DatabaseUnavailable(RuntimeError):
    pass


@dataclass
class TraceEntry:
    name: str
    cypher: str
    params: dict
    ms: float
    rows: int

    def as_dict(self) -> dict:
        # Embeddings are long and useless in the UI; show their length instead.
        params = {k: (f"<vector[{len(v)}]>" if isinstance(v, list) and len(v) > 32 else v)
                  for k, v in self.params.items()}
        return {"name": self.name, "cypher": " ".join(self.cypher.split()), "params": params,
                "ms": round(self.ms, 2), "rows": self.rows}


def start_trace() -> list:
    t: list = []
    _trace.set(t)
    return t


def current_trace() -> list[dict]:
    return [e.as_dict() for e in (_trace.get() or [])]


@lru_cache(maxsize=1)
def client() -> FalkorDB:
    # socket_timeout matters: FalkorDB Cloud free silently hangs on TLS, and the
    # python client has no default timeout.
    return FalkorDB(
        host=os.getenv("FALKORDB_HOST", "localhost"),
        port=int(os.getenv("FALKORDB_PORT", "6379")),
        username=os.getenv("FALKORDB_USERNAME") or None,
        password=os.getenv("FALKORDB_PASSWORD") or None,
        socket_timeout=float(os.getenv("FALKORDB_TIMEOUT", "10")),
    )


def ping() -> bool:
    try:
        return bool(client().connection.ping())
    except Exception:
        return False


def graph_name(org: str) -> str:
    if not _SLUG.match(org):
        raise ValueError(f"invalid org slug: {org!r}")
    return f"org_{org}"


def list_orgs() -> list[str]:
    return [g[4:] for g in client().list_graphs() if g.startswith("org_")]


@dataclass
class Org:
    slug: str
    _graph: Any = field(init=False, repr=False)

    def __post_init__(self):
        self._graph = client().select_graph(graph_name(self.slug))

    def _run(self, name: str, cypher: str, params: dict | None, read_only: bool) -> list[dict]:
        params = params or {}
        t0 = time.perf_counter()
        try:
            res = (self._graph.ro_query if read_only else self._graph.query)(cypher, params)
        except (ConnectionError, TimeoutError, OSError) as e:
            raise DatabaseUnavailable(str(e)) from e
        except Exception as e:
            if read_only and "empty key" in str(e):
                return []  # graph not created yet: nothing to read
            if "Connection" in type(e).__name__ or "Timeout" in type(e).__name__:
                raise DatabaseUnavailable(str(e)) from e
            raise
        ms = (time.perf_counter() - t0) * 1000
        cols = [h[1] if isinstance(h, (list, tuple)) else h for h in res.header]
        rows = [dict(zip(cols, r)) for r in res.result_set]
        tr = _trace.get()
        if tr is not None:
            tr.append(TraceEntry(name, cypher, params, ms, len(rows)))
        return rows

    def read(self, name: str, cypher: str, params: dict | None = None) -> list[dict]:
        return self._run(name, cypher, params, read_only=True)

    def write(self, name: str, cypher: str, params: dict | None = None) -> list[dict]:
        return self._run(name, cypher, params, read_only=False)

    def delete(self) -> None:
        try:
            self._graph.delete()
        except Exception:
            pass

    def copy_to(self, dest_slug: str) -> "Org":
        client().connection.execute_command("GRAPH.COPY", graph_name(self.slug), graph_name(dest_slug))
        return Org(dest_slug)


def now() -> int:
    return int(time.time())
