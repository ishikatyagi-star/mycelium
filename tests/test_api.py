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


ONBOARD = {
    "slug": "test_onboard_co",
    "teams": [
        {"name": "Core", "services": [{"name": "api", "category": "service"}, {"name": "db", "category": "infra"}],
         "people": [{"name": "Asha", "role": "backend"}, {"name": "Ben"}]},
        {"name": "Apps", "services": [{"name": "web"}], "people": [{"name": "Chen", "role": "frontend"}]},
    ],
    "dependencies": [{"service": "web", "depends_on": "api"}, {"service": "api", "depends_on": "db"}],
    "projects": [{"name": "Launch", "services": ["web", "api"]}],
}


def test_create_org_then_use_it(client, monkeypatch):
    import copy
    spec = copy.deepcopy(ONBOARD)
    spec["slug"] = "onboard_co"           # tests may not create reserved test_* slugs
    Org("onboard_co").delete()
    try:
        r = client.post("/api/orgs", json=spec)
        assert r.status_code == 201, r.text
        ov = r.json()["overview"]
        assert {t["name"] for t in ov["teams"]} == {"Core", "Apps"}
        assert client.post("/api/orgs", json=spec).status_code == 409          # no overwrite
        # the new org works immediately: a session, a saved fix, a recall, and DEPENDS_ON impact
        s = client.post("/api/orgs/onboard_co/sessions", json={"dev": "Chen", "task": "Web app shows stale data after deploy",
                                                                "components": ["web"]}).json()
        saved = client.post(f"/api/orgs/onboard_co/sessions/{s['session_id']}/solutions",
                            json={"title": "Bust the CDN cache on deploy", "summary": "Purge the CDN after each web deploy so users get fresh assets."})
        assert saved.json()["decision"] == "ACCEPT"
        hit = client.post("/api/orgs/onboard_co/recall", json={"query": "users see old web assets after a deploy", "as_dev": "Asha"}).json()
        assert hit["results"][0]["solution"]["title"] == "Bust the CDN cache on deploy"
        n = client.post("/api/orgs/onboard_co/notices", json={"component": "db", "text": "db migrates to v2 schema", "as_dev": "Asha"}).json()
        assert {d["component"] for d in n["affected_components"]} == {"db", "api", "web"}   # 2 hops up DEPENDS_ON
    finally:
        Org("onboard_co").delete()


def test_create_org_rejects_bad_specs(client):
    import copy
    bad = copy.deepcopy(ONBOARD)
    bad["slug"] = "onboard_bad"
    bad["dependencies"].append({"service": "web", "depends_on": "payments"})
    bad["teams"][1]["people"].append({"name": "Asha"})
    r = client.post("/api/orgs", json=bad)
    assert r.status_code == 422
    problems = r.json()["detail"]["problems"]
    assert any("unknown service 'payments'" in p for p in problems)
    assert any("person 'Asha' is in both" in p for p in problems)
    assert "onboard_bad" not in api_main.list_orgs()                         # nothing half-created
    assert client.post("/api/orgs", json={**ONBOARD, "slug": "Bad Slug!"}).status_code == 422
    assert client.post("/api/orgs", json={**ONBOARD, "slug": "sandbox_x1"}).status_code == 400
