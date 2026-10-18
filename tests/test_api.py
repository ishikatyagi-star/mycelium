"""API-level tests, including the 'removal test': without FalkorDB the product does not work (503), by design."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import api.main as api_main
from core.db import Org
from seed.graphhq import seed

ORG = "test_api"


@pytest.fixture(scope="module")
def client():
    seed(ORG)
    with TestClient(api_main.app) as c:
        yield c
    Org(ORG).delete()


def test_compare_endpoint_has_trace(client):
    r = client.post(f"/api/orgs/{ORG}/compare", json={"query": "access token expired returns 401, refresh it and retry the request",
                                                      "as_dev": "Ishika", "k": 3})
    d = r.json()
    assert r.status_code == 200
    assert d["vector_only"][0]["solution"]["status"] == "superseded"
    assert d["mycelium"][0]["solution"]["status"] == "active"
    assert any("SUPERSEDES" in t["cypher"] for t in d["trace"])


def test_agent_lifecycle(client):
    s = client.post(f"/api/orgs/{ORG}/sessions", json={"dev": "Ishika", "task": "Image uploads fail on phones with wrong clocks",
                                                       "components": ["mobile-app"], "project": "Mobile 3.0"}).json()
    assert s["memories"][0]["solution"]["id"] == "sol_presigned_skew"
    sid = s["session_id"]
    assert client.post(f"/api/orgs/{ORG}/sessions/{sid}/outcome",
                       json={"solution_id": "sol_presigned_skew", "worked": True}).status_code == 200
    saved = client.post(f"/api/orgs/{ORG}/sessions/{sid}/solutions",
                        json={"title": "Retry upload with fresh presigned URL on 403", "summary":
                              "Extended the server-side signing fix with an automatic single retry on 403.",
                              "builds_on": ["sol_presigned_skew"]}).json()
    assert saved["decision"] == "ACCEPT"
    lin = client.get(f"/api/orgs/{ORG}/lineage/{saved['solution_id']}").json()
    assert [c["id"] for c in lin["chain"]][0] == "sol_presigned_skew"
    assert client.post(f"/api/orgs/{ORG}/sessions/{sid}/end").status_code == 200


def test_unknown_org_404(client):
    assert client.get("/api/orgs/nope_nope/overview").status_code == 404


def test_removal_test_db_down_gives_503(client, monkeypatch):
    from core import db
    from core.db import DatabaseUnavailable

    def boom(*a, **k):
        raise DatabaseUnavailable("connection refused")
    monkeypatch.setattr(db.Org, "_run", boom)
    monkeypatch.setattr(api_main, "list_orgs", lambda: [ORG])
    monkeypatch.setattr(api_main, "ping", lambda: False)
    assert client.get("/api/health").status_code == 503
    r = client.post(f"/api/orgs/{ORG}/recall", json={"query": "token refresh storm", "as_dev": "Ishika"})
    assert r.status_code == 503


def test_janitor_deletes_old_sandboxes_and_expires_sessions(client, monkeypatch):
    import time as _t
    from core import memory as M
    fresh = client.post("/api/sandbox").json()["org"]
    old = f"sandbox_{int(_t.time()) - 4 * 3600:x}_dead"
    Org(ORG).copy_to(old)
    stale = M.start_session(Org(ORG), "Tom", "stale janitor probe task", started_at=int(_t.time()) - 3 * 3600)
    r = api_main.janitor_once()
    assert old in r["deleted_sandboxes"] and fresh not in r["deleted_sandboxes"]
    assert r["expired_sessions"] >= 1
    st = Org(ORG).read("t", "MATCH (s:Session {id:$s}) RETURN s.status AS st", {"s": stale["session_id"]})
    assert st[0]["st"] == "done"
    Org(fresh).delete()


def test_event_bus_fans_out_to_subscribers():
    import asyncio
    import json
    from core import events

    async def run():
        sub = events.subscribe("bus_test")
        await asyncio.to_thread(events.publish, "bus_test", "notice", component="ledger")  # from a worker thread
        msg = await asyncio.wait_for(sub[1].get(), timeout=2)
        events.unsubscribe("bus_test", sub)
        return json.loads(msg)
    assert asyncio.run(run()) == {"type": "notice", "component": "ledger"}
