"""Indexes for an org graph. Idempotent: safe to call on every startup."""
from __future__ import annotations

import time

from .db import Org
from .embed import DIM

VECTOR_INDEXES = [("Task", "embedding"), ("Question", "embedding")]
RANGE_INDEXES = [
    ("Team", "name"), ("Component", "name"), ("Dev", "name"), ("Project", "name"),
    ("Session", "id"), ("Session", "status"), ("Task", "id"), ("Solution", "id"),
    ("Library", "name"), ("Error", "signature"), ("Question", "id"), ("Notice", "id"),
    ("Handoff", "id"),
]


def ensure_schema(org: Org) -> None:
    existing = {(r["label"], p) for r in org.read("schema.indexes",
                "CALL db.indexes() YIELD label, properties RETURN label, properties")
                for p in r["properties"]}
    for label, prop in RANGE_INDEXES:
        if (label, prop) not in existing:
            org.write("schema.range", f"CREATE INDEX FOR (n:{label}) ON (n.{prop})")
    for label, prop in VECTOR_INDEXES:
        if (label, prop) not in existing:
            org.write("schema.vector",
                      f"CREATE VECTOR INDEX FOR (n:{label}) ON (n.{prop}) "
                      f"OPTIONS {{dimension:{DIM}, similarityFunction:'cosine'}}")
    # On FalkorDB 4.22 (incl. Cloud free) vector queries fail until the index is
    # OPERATIONAL, so wait for it instead of failing the first recall.
    for _ in range(50):
        rows = org.read("schema.status", "CALL db.indexes() YIELD label, status RETURN label, status")
        if all(r["status"] == "OPERATIONAL" for r in rows):
            return
        time.sleep(0.1)
