"""Integration tests against a real FalkorDB (docker compose up -d). Each run uses its own org graph."""
from __future__ import annotations

import pytest

from core import brain as B
from core import memory as M
from core import messaging as Msg
from core import presence as P
from core.db import Org, list_orgs
from seed.graphhq import seed

ORG = "test_graphhq"


@pytest.fixture(scope="module")
def org():
    seed(ORG)
    yield Org(ORG)
    Org(ORG).delete()


def test_recall_crosses_teams_and_credits_author(org):
    res = M.recall(org, "mobile app logs users out when parallel API calls refresh the token", "Ishika", k=3)
    top = res[0]
    assert top["solution"]["id"] == "sol_refresh_v2"
    assert top["author"] == {"name": "Yash", "team": "Payments"}      # other team
    assert top["project"]["name"] == "Checkout v2"                     # other project
    assert top["solution"]["effort_minutes"] == 1440 and top["solution"]["attempts"] == 14
    assert top["tokens_saved_estimate"] > 100_000


def test_graph_skips_stale_fix_that_vector_search_returns(org):
    q = "access token expired returns 401, refresh it and retry the request"
    vector = M.recall(org, q, "Ishika", k=3, graph=False)
    graph = M.recall(org, q, "Ishika", k=3)
    assert vector[0]["solution"]["id"] == "sol_refresh_v1"             # stale, superseded fix wins on similarity
    assert vector[0]["solution"]["status"] == "superseded"
    assert graph[0]["solution"]["id"] == "sol_refresh_v2"              # graph walks SUPERSEDES to the fix
    assert graph[0]["skipped"][0]["id"] == "sol_refresh_v1"
    assert "429" in graph[0]["skipped"][0]["reason"]
    assert {l["kind"] for l in graph[0]["lessons"]} >= {"pitfall", "dead_end"}
    assert all(r["solution"]["id"] != "sol_refresh_v1" for r in graph)


def test_visibility_private_and_team(org):
    q_private = "android emulator cannot reach the dev api on localhost"
    assert any(r["solution"]["id"] == "sol_ishika_private" for r in M.recall(org, q_private, "Ishika"))
    assert all(r["solution"]["id"] != "sol_ishika_private" for r in M.recall(org, q_private, "Yash"))
    q_team = "rotate the ledger database credentials without downtime"
    assert any(r["solution"]["id"] == "sol_payments_team_note" for r in M.recall(org, q_team, "Rohan"))
    assert all(r["solution"]["id"] != "sol_payments_team_note" for r in M.recall(org, q_team, "Ishika"))


def test_task_dedupe_merges_near_identical_problems(org):
    a = M.start_session(org, "Neha", "Remove duplicate customers from the CRM CSV export before loading it",
                        status="done")
    assert a["task_merged"] is True


def test_write_gate_rejects_and_keeps_receipts(org):
    s = M.start_session(org, "Neha", "write gate probe task about flaky snapshot tests", status="done")
    bad = M.save_solution(org, M.SaveRequest(session_id=s["session_id"], title="x", summary="too short"))
    assert bad["decision"] == "REJECT"
    good = M.save_solution(org, M.SaveRequest(session_id=s["session_id"], title="Freeze time in snapshot tests",
                                              summary="Snapshot tests were flaky because of timestamps; freeze time.",
                                              lessons=[{"text": "bad", "kind": "nonsense"}],
                                              builds_on=["sol_does_not_exist"]))
    assert good["decision"] == "ACCEPT"
    assert any("dropped invalid lesson" in r for r in good["reasons"])
    assert any("ignored unknown solution refs" in r for r in good["reasons"])
    receipts = org.read("t", "MATCH (:Session {id:$s})-[:WROTE]->(r:Receipt) RETURN r.decision AS d",
                        {"s": s["session_id"]})
    assert sorted(r["d"] for r in receipts) == ["ACCEPT", "REJECT"]


def test_lineage_spans_projects_and_teams(org):
    chain = M.lineage(org, "sol_idem_v4")["chain"]
    assert [c["id"] for c in chain] == ["sol_idem_v1", "sol_idem_v2", "sol_idem_v3", "sol_idem_v4"]
    assert {c["author"]["team"] for c in chain} == {"Payments", "Data"}
    assert {c["project"] for c in chain} == {"Checkout v2", "Realtime Ledger"}


def test_failed_outcome_marks_broken_and_warns(org):
    s = M.start_session(org, "Tom", "push notifications missing in release build on iOS 18", status="done")
    M.report_outcome(org, s["session_id"], "sol_push_ios", worked=False, error="APNs BadDeviceToken on iOS 18")
    res = M.recall(org, "iOS push notifications never arrive in production builds", "Neha", k=3)
    hit = next(r for r in res if r["solution"]["id"] == "sol_push_ios")
    assert hit["solution"]["status"] == "broken"
    assert any("BadDeviceToken" in e["signature"] for e in hit["errors"])


def test_overlap_detected_across_teams(org):
    s = M.start_session(org, "Ishika", "Refund retries overwhelm the ledger after downtime", ["mobile-app"])
    ov = P.detect_overlaps(org, s["session_id"])
    assert ov and ov[0]["dev"]["name"] == "Rohan" and ov[0]["cross_team"] is True
    M.end_session(org, s["session_id"])


def test_ask_org_answers_from_memory_first(org):
    r = Msg.ask_org(org, "What is the retention on the ledger.events kafka topic?", dev="Yash")
    assert r["mode"] == "memory"
    assert "7 days" in r["answer"]["solution"]["summary"]


def test_ask_org_routes_to_live_agent_with_path_then_answer_becomes_memory(org):
    s = M.start_session(org, "Ishika", "Mobile app caches the JWT public key", ["mobile-app"])
    r = Msg.ask_org(org, "Is anyone rotating the token-service signing keys right now?", session_id=s["session_id"])
    assert r["mode"] == "routed"
    assert r["routed_to"]["dev"]["name"] == "Meera" and r["routed_to"]["kind"] == "session"
    assert any(n["label"] == "Component" and n["name"] == "token-service" for n in r["path"]["nodes"])
    inbox = Msg.inbox(org, r["routed_to"]["id"])
    assert any(q["question_id"] == r["question_id"] for q in inbox["questions"])
    a = Msg.answer(org, r["question_id"], "Yes: new keys at 14:00 UTC, refetch JWKS when you see an unknown kid.",
                   session_id=r["routed_to"]["id"])
    assert a["memory_solution_id"]
    again = Msg.ask_org(org, "Is anyone rotating the token-service signing keys right now?", dev="Neha")
    assert again["mode"] == "memory" and "JWKS" in again["answer"]["solution"]["summary"]
    M.end_session(org, s["session_id"])


def test_change_propagates_to_live_dependents_only(org):
    n = Msg.announce_change(org, "ledger", "balance API now returns integer minor units", dev="Sara")
    reached = {(d["dev"]["name"], d["component"]) for d in n["impact"]}
    assert ("Rohan", "refunds-worker") in reached                       # depends on ledger, live
    assert ("Tom", "mobile-app") in reached                             # mobile-app -> checkout-api -> ledger
    assert all(d["dev"]["name"] not in ("Kabir", "Leo", "Meera") for d in n["impact"])  # not dependents
    assert {"team": "Payments", "component": "payment-webhooks"} in n["team_deliveries"]
    tom = next(d for d in n["impact"] if d["dev"]["name"] == "Tom")
    assert [x["name"] for x in tom["path"]["nodes"] if x["label"] == "Component"] == ["mobile-app", "checkout-api", "ledger"]
    with pytest.raises(ValueError):
        Msg.announce_change(org, "ledger", "x" * 10, dev="Sara", depth=9)


def test_handoff_pickup(org):
    s = M.start_session(org, "Tom", "Migrate push sending to the new APNs token auth", ["push-notifications"])
    h = Msg.handoff(org, s["session_id"], "Keys uploaded; sender still uses certs. Next: switch sender config.",
                    to_team="Mobile")
    M.end_session(org, s["session_id"])
    n = M.start_session(org, "Neha", "Continue APNs token auth migration", ["push-notifications"])
    inbox = Msg.inbox(org, n["session_id"])
    assert any(x["handoff_id"] == h["handoff_id"] for x in inbox["handoffs"])
    got = Msg.pick_up(org, h["handoff_id"], n["session_id"])
    assert got["from_dev"] == "Tom" and "push-notifications" in got["components"]
    M.end_session(org, n["session_id"])


def test_brain(org):
    b = B.brain(org)
    assert any(r["solution_id"] == "sol_kafka_rebalance" for r in b["at_risk"])       # nobody else touched it
    assert all(r["solution_id"] != "sol_refresh_v2" for r in b["at_risk"])           # Sara reused it
    assert b["savings"] and b["experts"]
    assert B.who_knows(org, "kafka consumer group rebalancing")[0]["dev"]["name"] == "Kabir"


def test_tenant_isolation():
    other = Org("test_isolation")
    other.delete()
    seed("test_isolation", live=False)
    s = M.start_session(other, "Yash", "secret isolation marker task zebra quokka", status="done")
    M.save_solution(other, M.SaveRequest(session_id=s["session_id"], title="Zebra quokka secret",
                                         summary="This memory must never leak into another org graph."))
    try:
        res = M.recall(Org(ORG), "secret isolation marker task zebra quokka", "Yash")
        assert all("Zebra" not in r["solution"]["title"] for r in res)
        assert "test_isolation" in list_orgs()
    finally:
        other.delete()


def test_importer_scrubs_secrets_and_pii():
    from core.importer import scrub
    dirty = ("key sk-abc123def456ghi789jkl and xai-ABCDEF1234567890XYZ token=supersecretvalue "
             "mail me at someone@example.com, see /Users/alice/proj and postgres://u:pw@db:5432/x "
             "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig ghp_abcdefghijklmnopqrstuvwx")
    clean = scrub(dirty)
    for leak in ["sk-abc123", "xai-ABCDEF", "supersecretvalue", "someone@example.com", "/Users/alice",
                 "u:pw@", "eyJhbGciOiJIUzI1NiJ9", "ghp_abcdef"]:
        assert leak not in clean, leak
