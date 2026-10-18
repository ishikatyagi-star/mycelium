"""Playground scenarios: employees at Graph HQ whose AI agents are mid-conversation and about to (re)solve a
problem that someone else in the org already solved. Stored in the graph as Sessions with status 'waiting'
(an agent waiting for its developer's decision) and the chat transcript as a property.

Each scenario maps to planted memory in seed/graphhq.py, often across teams, projects and months, and several
hit a stale fix that the graph must skip.
"""
from __future__ import annotations

import json

from core import memory as M
from core.db import Org, now

DAY = 86400

SCENARIOS = [
    dict(key="neha_logout", dev="Neha", project="Mobile 3.0", components=["mobile-app", "auth-gateway"],
         title="Users logged out after the app resumes",
         problem="Fix random logouts when several requests refresh the token at the same time",
         query="mobile app randomly logs users out when several API calls refresh the token at the same time",
         chat=[
             ("user", "Support says users on Android get logged out randomly, mostly right after the app comes back from background. Can you look?"),
             ("agent", "Looking at the network logs from the bug report… On resume the app fires 6 requests at once. All six get 401 because the access token expired while backgrounded."),
             ("agent", "Each 401 then calls /oauth/token with the same refresh token. The first call succeeds; the other five fail with invalid_grant and we clear the session. That's the logout."),
             ("user", "Ugh. Ok, fix it. Can we just retry once after refreshing?"),
             ("agent", "I can write a retry-on-401 interceptor. Before I start: this looks like a concurrency problem around token refresh. It might take a few iterations to get right."),
         ]),
    dict(key="ananya_dst", dev="Ananya", project="Insights Dashboard", components=["reporting-api", "warehouse-etl"],
         title="Daily totals wrong around daylight saving",
         problem="Dashboard daily revenue double-counts on the DST change day",
         query="dashboard daily totals double count transactions on the daylight saving change day",
         chat=[
             ("user", "Finance flagged that the daily revenue chart shows a spike on Oct 27 and Mar 30. Totals are ~4% higher than the ledger."),
             ("agent", "Those are both daylight-saving transition days. I suspect we bucket transactions into days using a fixed UTC offset."),
             ("agent", "On the transition day one hour lands in two buckets. I'll need to rework how day boundaries are computed in the reporting query."),
             ("user", "Go ahead, it needs to be right before the board deck on Friday."),
         ]),
    dict(key="tom_uploads", dev="Tom", project="Mobile 3.0", components=["mobile-app"],
         title="Photo uploads fail on some phones",
         problem="S3 uploads fail with SignatureDoesNotMatch / Request has expired on some devices",
         query="photo uploads fail with SignatureDoesNotMatch request has expired on some phones",
         chat=[
             ("user", "Crash reports: profile photo upload fails for ~3% of users. Error from S3 is 'Request has expired' or SignatureDoesNotMatch."),
             ("agent", "The failing devices have nothing in common on OS version or network. Uploads use URLs signed on the device with the temporary credentials."),
             ("agent", "I could add retries with exponential backoff and log more device info to narrow it down."),
             ("user", "Let's figure out the root cause first, retries won't fix a signature error."),
         ]),
    dict(key="meera_pg", dev="Meera", project="Mobile 3.0", components=["token-service"],
         title="token-service: too many Postgres connections",
         problem="Postgres 'too many connections' errors when token-service scales out",
         query="postgres too many connections raise max_connections",
         chat=[
             ("user", "token-service is throwing FATAL: sorry, too many clients already during the morning login peak."),
             ("agent", "It autoscales to 40 instances at peak, each with a pool of 20 connections. That's 800 connections against max_connections=200."),
             ("agent", "Quickest fix: raise max_connections on the database to 1000. I can open the infra PR now."),
             ("user", "Is that safe? Feels like a band-aid."),
         ]),
    dict(key="priya_kafka", dev="Priya", project="Mobile 3.0", components=["auth-gateway", "events-pipeline"],
         title="Audit-log consumers keep rebalancing",
         problem="Kafka consumers for the auth audit log keep getting kicked out of the group",
         query="kafka consumers get kicked out of the group during big batches, should we raise session.timeout.ms",
         chat=[
             ("user", "The auth audit-log consumer lag goes to 2M every night and the group never stabilises."),
             ("agent", "Logs show continuous rebalances: members leave the group mid-batch and rejoin. Batches take up to 8 minutes during the nightly export."),
             ("agent", "Plan: raise session.timeout.ms to 45s so consumers stop being considered dead."),
         ]),
    dict(key="omar_arm", dev="Omar", project="ARM Migration", components=["ci-pipeline"],
         title="reporting-api arm64 image won't build",
         problem="arm64 build of reporting-api fails installing psycopg and onnxruntime wheels, CI times out",
         query="arm64 docker builds time out in CI and python wheels like psycopg and onnxruntime fail to install",
         chat=[
             ("user", "We need reporting-api on Graviton next sprint. The arm64 image build fails."),
             ("agent", "The build compiles psycopg and onnxruntime from source under emulation and hits the 60-minute CI limit."),
             ("agent", "I'll try building under QEMU with more CPU and a longer timeout, then pin wheel versions."),
         ]),
]


def seed_playground(org: Org) -> list[str]:
    ids = []
    t = now()
    for i, s in enumerate(SCENARIOS):
        sid = f"ses_play_{s['key']}"
        M.start_session(org, s["dev"], s["problem"], s["components"], s["project"], agent="claude-code",
                        session_id=sid, started_at=t - (i + 2) * 600, status="waiting")
        org.write("seed.playground",
                  """MATCH (s:Session {id:$sid})
                     SET s.scenario = true, s.status = 'waiting', s.title = $title, s.problem = $problem,
                         s.query = $query, s.transcript = $transcript""",
                  {"sid": sid, "title": s["title"], "problem": s["problem"], "query": s["query"],
                   "transcript": json.dumps([{"role": r, "text": x} for r, x in s["chat"]])})
        ids.append(sid)
    return ids
