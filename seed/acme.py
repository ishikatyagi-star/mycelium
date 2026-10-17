"""Synthetic org 'acme': 5 teams, 17 components, 14 devs, 5 projects over ~4 months.

All data is synthetic (hackathon Rule 6). Times are relative to *now* so that
"six weeks ago" stays true whenever the demo runs.

Planted stories (used by the demo, tests and eval):
  * token refresh: a naive fix that later FAILED, superseded by a 3-day hard-won fix
  * webhook idempotency: a BUILDS_ON lineage across 3 projects and 3 teams
  * ARM builds: a QEMU dead end superseded by native arm64 runners
  * hard-won fixes nobody else has touched (knowledge at risk)
  * cross-team reuse and answered questions (feeds PageRank / help flows)
  * live sessions right now, including a cross-team overlap
"""
from __future__ import annotations

from core import memory as M
from core import messaging as Msg
from core import org as O
from core import presence as P
from core.db import Org, now
from core.schema import ensure_schema

DAY = 86400

TEAMS = {
    "Identity": {"components": [("auth-gateway", "service"), ("token-service", "service"), ("user-profile", "service")],
                 "devs": [("Priya", "lead"), ("Arjun", "backend"), ("Meera", "backend")]},
    "Payments": {"components": [("checkout-api", "service"), ("payment-webhooks", "service"), ("ledger", "service"),
                                ("refunds-worker", "worker")],
                 "devs": [("Yash", "backend"), ("Rohan", "backend"), ("Sara", "lead")]},
    "Data": {"components": [("events-pipeline", "streaming"), ("warehouse-etl", "batch"), ("reporting-api", "service"),
                            ("feature-store", "ml")],
             "devs": [("Kabir", "lead"), ("Ananya", "data eng"), ("Leo", "analytics eng")]},
    "Mobile": {"components": [("mobile-app", "client"), ("push-notifications", "service"), ("offline-sync", "client lib")],
               "devs": [("Ishika", "mobile"), ("Neha", "mobile"), ("Tom", "lead")]},
    "Platform": {"components": [("ci-pipeline", "infra"), ("k8s-deploy", "infra"), ("observability", "infra")],
                 "devs": [("Zara", "sre"), ("Omar", "sre")]},
}

DEPENDS_ON = [
    ("auth-gateway", "token-service"), ("user-profile", "auth-gateway"),
    ("checkout-api", "auth-gateway"), ("checkout-api", "ledger"), ("payment-webhooks", "ledger"),
    ("refunds-worker", "ledger"), ("refunds-worker", "events-pipeline"), ("ledger", "events-pipeline"),
    ("mobile-app", "auth-gateway"), ("mobile-app", "checkout-api"), ("mobile-app", "push-notifications"),
    ("mobile-app", "offline-sync"), ("offline-sync", "user-profile"), ("push-notifications", "user-profile"),
    ("warehouse-etl", "events-pipeline"), ("reporting-api", "warehouse-etl"), ("feature-store", "events-pipeline"),
    ("k8s-deploy", "ci-pipeline"),
]

PROJECTS = [  # name, repo, components, start (days ago)
    ("Checkout v2", "acme/checkout", ["checkout-api", "payment-webhooks", "auth-gateway", "token-service"], 120),
    ("Realtime Ledger", "acme/ledger", ["ledger", "events-pipeline", "payment-webhooks", "refunds-worker"], 85),
    ("ARM Migration", "acme/infra", ["ci-pipeline", "k8s-deploy"], 65),
    ("Mobile 3.0", "acme/mobile", ["mobile-app", "push-notifications", "offline-sync", "auth-gateway"], 45),
    ("Insights Dashboard", "acme/insights", ["reporting-api", "warehouse-etl", "feature-store"], 32),
]

# Each memory: one finished agent session that produced a solution.
# (key, dev, project, components, task, days_ago, effort_min, attempts, tokens, solution dict)
MEMORIES = [
    # ---- story 1: token refresh (stale fix -> hard-won fix) ----
    dict(key="refresh_v1", dev="Arjun", project="Checkout v2", components=["auth-gateway", "checkout-api"],
         task="Users get 401 Unauthorized when the access token expires mid-checkout; refresh the OAuth token and retry",
         days_ago=104, effort=90, attempts=2, tokens=18000,
         title="Retry once after refreshing the access token on 401",
         summary="Axios response interceptor: on 401 call POST /oauth/token with the refresh token, store the new pair, "
                 "replay the original request once.",
         code="api.interceptors.response.use(null, async (err) => {\n  if (err.response?.status === 401 && !err.config._retry) {\n"
              "    err.config._retry = true;\n    const t = await refreshToken();\n    setTokens(t);\n    return api(err.config);\n  }\n  throw err;\n});",
         libraries=[{"name": "axios", "version": "1.6"}],
         lessons=[{"text": "Mark the retried request (_retry) or a bad refresh token loops forever", "kind": "pitfall"}]),
    dict(key="refresh_v2", dev="Yash", project="Checkout v2", components=["checkout-api", "auth-gateway", "token-service"],
         task="Token refresh race: parallel requests all get 401 and each triggers its own refresh, causing a refresh storm, "
              "429s from the token endpoint and random logouts",
         days_ago=72, effort=1440, attempts=14, tokens=210000,
         title="Single-flight token refresh (one shared in-flight refresh, queue and replay 401s)",
         summary="Keep a single in-flight refresh promise. Every request that hits 401 awaits that same promise, then replays "
                 "with the new token. Refresh tokens rotate on use, so two concurrent refreshes invalidate each other and log "
                 "the user out. Persist the rotated pair atomically before releasing waiters.",
         code="let inflight: Promise<Tokens> | null = null;\nexport function refreshOnce() {\n  if (!inflight) inflight = refreshToken()\n"
              "    .then(async t => { await saveTokensAtomically(t); return t; })\n    .finally(() => { inflight = null; });\n  return inflight;\n}\n"
              "api.interceptors.response.use(null, async (err) => {\n  if (err.response?.status !== 401 || err.config._retry) throw err;\n"
              "  err.config._retry = true;\n  const t = await refreshOnce();\n  err.config.headers.Authorization = `Bearer ${t.access}`;\n  return api(err.config);\n});",
         libraries=[{"name": "axios", "version": "1.6"}],
         lessons=[{"text": "Refresh tokens rotate on use: two parallel refreshes invalidate each other and log the user out", "kind": "pitfall"},
                  {"text": "Jittered retries on 401 only delay the refresh storm, they do not prevent it", "kind": "dead_end"},
                  {"text": "Increasing the token endpoint rate limit hid the bug in staging but not in prod", "kind": "dead_end"},
                  {"text": "Save the rotated token pair atomically before waking the queued requests", "kind": "tip"}],
         supersedes=["refresh_v1"], failed=("refresh_v1", "Yash", "429 Too Many Requests from /oauth/token (refresh storm under parallel 401s)")),

    # ---- story 2: webhook idempotency lineage (BUILDS_ON across projects and teams) ----
    dict(key="idem_v1", dev="Rohan", project="Checkout v2", components=["payment-webhooks"],
         task="Stripe sends the same webhook event more than once and we double-capture payments",
         days_ago=96, effort=240, attempts=4, tokens=40000,
         title="Dedupe Stripe webhooks with a processed_events table",
         summary="Insert event.id into processed_events (unique) in the same DB transaction as the side effect; skip if it exists.",
         code="INSERT INTO processed_events(id) VALUES ($1) ON CONFLICT DO NOTHING RETURNING id;",
         libraries=[{"name": "stripe", "version": "14"}, {"name": "postgres", "version": "15"}],
         lessons=[{"text": "Stripe retries for 3 days; dedupe on event.id, never on payload hash", "kind": "pitfall"}]),
    dict(key="idem_v2", dev="Sara", project="Realtime Ledger", components=["payment-webhooks", "ledger"],
         task="Make payment webhook handling idempotent across multiple consumers without a DB round-trip per event",
         days_ago=61, effort=480, attempts=6, tokens=70000,
         title="Idempotency keys with TTL in Redis for webhook consumers",
         summary="SET key NX EX 259200 on the event id before processing; on failure delete the key so retries work. Builds on "
                 "the processed_events approach but works across consumers.",
         code="ok = r.set(f'idem:{event.id}', 1, nx=True, ex=259200)\nif not ok: return 'duplicate'\ntry: handle(event)\nexcept: r.delete(f'idem:{event.id}'); raise",
         libraries=[{"name": "redis", "version": "7"}],
         lessons=[{"text": "TTL must exceed the provider's retry window (Stripe: 3 days)", "kind": "pitfall"}],
         builds_on=["idem_v1"]),
    dict(key="idem_v3", dev="Kabir", project="Realtime Ledger", components=["ledger", "events-pipeline"],
         task="Ledger writes and the Kafka event must both happen or neither; we lose events when the producer fails after commit",
         days_ago=47, effort=960, attempts=9, tokens=140000,
         title="Transactional outbox for ledger writes plus idempotent consumer",
         summary="Write the ledger row and an outbox row in one transaction; a relay publishes outbox rows to Kafka with the "
                 "row id as message key; consumers keep Redis idempotency keys (from the webhook work).",
         libraries=[{"name": "kafka", "version": "3.6"}, {"name": "postgres", "version": "15"}],
         lessons=[{"text": "Dual writes (DB then Kafka) silently lose events on producer failure", "kind": "dead_end"},
                  {"text": "Use the outbox row id as the Kafka key so consumers can dedupe", "kind": "tip"}],
         builds_on=["idem_v2"]),
    dict(key="idem_v4", dev="Rohan", project="Realtime Ledger", components=["refunds-worker", "ledger"],
         task="Refund events are sometimes applied twice to the ledger after a worker restart",
         days_ago=16, effort=300, attempts=3, tokens=45000,
         title="Exactly-once refunds via outbox and committed consumer offsets",
         summary="Reuse the ledger outbox; commit consumer offsets only after the idempotent apply; refunds keyed by refund id.",
         libraries=[{"name": "kafka", "version": "3.6"}],
         builds_on=["idem_v3"]),

    # ---- story 3: ARM builds (dead end -> fix), knowledge at risk ----
    dict(key="arm_qemu", dev="Omar", project="ARM Migration", components=["ci-pipeline"],
         task="Build linux/arm64 Docker images in CI for the Graviton migration",
         days_ago=60, effort=180, attempts=3, tokens=30000,
         title="Build arm64 images under QEMU emulation with docker buildx",
         summary="Enable binfmt/QEMU and run docker buildx --platform linux/arm64 on the existing x86 runners.",
         libraries=[{"name": "docker", "version": "25"}]),
    dict(key="arm_native", dev="Zara", project="ARM Migration", components=["ci-pipeline", "k8s-deploy"],
         task="arm64 Docker builds time out in CI and Python wheels like onnxruntime and psycopg fail to install on arm64",
         days_ago=52, effort=1200, attempts=11, tokens=160000,
         title="Native arm64 runners plus prebuilt manylinux aarch64 wheels",
         summary="Move arm64 builds to native Graviton runners (buildx remote builder), pin manylinux2014_aarch64 wheels, "
                 "build multi-arch manifests by merging per-arch images.",
         libraries=[{"name": "docker", "version": "25"}, {"name": "onnxruntime", "version": "1.17"}],
         lessons=[{"text": "QEMU emulation makes Python wheel compiles 10-20x slower; CI hits the 60 min limit", "kind": "dead_end"},
                  {"text": "psycopg[binary] has no musl aarch64 wheel; use the slim (glibc) base image", "kind": "pitfall"}],
         supersedes=["arm_qemu"], failed=("arm_qemu", "Zara", "CI job timeout after 60 min (QEMU emulation)")),

    # ---- other hard-won knowledge ----
    dict(key="kafka_rebalance", dev="Kabir", project="Realtime Ledger", components=["events-pipeline"],
         task="Kafka consumers keep rebalancing in a loop and lag explodes during large batches",
         days_ago=55, effort=960, attempts=9, tokens=120000,
         title="Stop rebalance storms: cooperative-sticky assignor, static membership, bounded batch time",
         summary="max.poll.interval.ms was shorter than the slowest batch so consumers were kicked out. Switch to "
                 "CooperativeStickyAssignor, set group.instance.id (static membership), cap max.poll.records.",
         libraries=[{"name": "kafka", "version": "3.6"}],
         lessons=[{"text": "Raising session.timeout.ms does not help; the poll interval is what evicts slow consumers", "kind": "dead_end"}]),
    dict(key="push_ios", dev="Tom", project="Mobile 3.0", components=["push-notifications", "mobile-app"],
         task="iOS push notifications never arrive in production builds of the React Native app",
         days_ago=36, effort=720, attempts=8, tokens=95000,
         title="Register for APNs after permission and ship the production aps-environment entitlement",
         summary="We registered the device token before the permission prompt and the release build had the development "
                 "aps-environment. Request permission first, then registerForRemoteNotifications; fix the entitlement.",
         libraries=[{"name": "react-native", "version": "0.74"}, {"name": "notifee", "version": "7"}],
         lessons=[{"text": "Push works in debug but not TestFlight: check aps-environment=production", "kind": "pitfall"}]),
    dict(key="offline_conflicts", dev="Neha", project="Mobile 3.0", components=["offline-sync", "user-profile"],
         task="Offline edits made on two devices overwrite each other when they sync",
         days_ago=26, effort=600, attempts=5, tokens=80000,
         title="Per-field hybrid logical clocks instead of last-write-wins",
         summary="Track an HLC timestamp per field; merge field-wise on sync; server rejects stale writes with 409 and the "
                 "client rebases.",
         lessons=[{"text": "Device clocks drift; wall-clock last-write-wins loses edits", "kind": "pitfall"}]),
    dict(key="presigned_skew", dev="Ishika", project="Mobile 3.0", components=["mobile-app"],
         task="Photo uploads fail with SignatureDoesNotMatch / Request has expired on some phones",
         days_ago=30, effort=360, attempts=6, tokens=50000,
         title="Generate presigned S3 URLs server-side with server time; retry with a fresh URL",
         summary="Some devices had skewed clocks, so client-side signed URLs were already expired. Sign on the server, short TTL, "
                 "and on 403 fetch a fresh URL once.",
         libraries=[{"name": "aws-sdk", "version": "3"}],
         lessons=[{"text": "Never sign URLs on the device: clock skew breaks SigV4", "kind": "pitfall"}]),
    dict(key="pg_pool", dev="Ananya", project="Insights Dashboard", components=["reporting-api", "warehouse-etl"],
         task="Postgres 'too many connections' errors when reporting-api scales out on serverless",
         days_ago=24, effort=420, attempts=5, tokens=60000,
         title="PgBouncer in transaction mode and disable server-side prepared statements",
         summary="Each lambda opened its own pool. Route through PgBouncer (transaction pooling), set pool size 1 per "
                 "instance, disable prepared statements in the driver.",
         libraries=[{"name": "pgbouncer", "version": "1.22"}, {"name": "psycopg", "version": "3.1"}],
         lessons=[{"text": "Prepared statements break under PgBouncer transaction pooling", "kind": "pitfall"}]),
    dict(key="settlement_tz", dev="Leo", project="Realtime Ledger", components=["ledger", "warehouse-etl"],
         task="Daily settlement report double-counts transactions on the DST change day",
         days_ago=40, effort=360, attempts=4, tokens=45000,
         title="Compute day boundaries in the business timezone, store and compare in UTC",
         summary="We cut days at local midnight using fixed offsets. Convert business-day boundaries with zoneinfo, then filter "
                 "on UTC timestamps.",
         libraries=[{"name": "python", "version": "3.12"}],
         lessons=[{"text": "Fixed UTC offsets break twice a year; always use zoneinfo", "kind": "pitfall"}]),
    dict(key="csv_dedupe", dev="Ananya", project="Insights Dashboard", components=["warehouse-etl"],
         task="Remove duplicate customers from the CRM CSV export before loading it",
         days_ago=20, effort=120, attempts=3, tokens=20000,
         title="Dedupe CSV rows on normalized email, keep latest by updated_at",
         summary="Normalize email (lowercase, strip, gmail dots), sort by updated_at, drop_duplicates(keep='last').",
         code="df['email_n'] = df.email.str.strip().str.lower()\ndf = df.sort_values('updated_at').drop_duplicates('email_n', keep='last')",
         libraries=[{"name": "pandas", "version": "2.2"}],
         lessons=[{"text": "pandas 2.x copy-on-write: chained assignment with inplace=True silently does nothing", "kind": "pitfall"}]),
    dict(key="rate_limit", dev="Priya", project="Checkout v2", components=["auth-gateway"],
         task="Credential stuffing on the login endpoint; need per-IP and per-account rate limiting",
         days_ago=88, effort=300, attempts=3, tokens=40000,
         title="Sliding-window rate limit with an atomic Redis Lua script",
         summary="ZADD/ZREMRANGEBYSCORE/ZCARD in one Lua script per key (ip and account), 429 with Retry-After.",
         libraries=[{"name": "redis", "version": "7"}],
         lessons=[{"text": "MULTI/EXEC is not enough: read-then-write races without Lua", "kind": "pitfall"}]),
    dict(key="otel_kafka", dev="Omar", project="Realtime Ledger", components=["observability", "events-pipeline"],
         task="Distributed traces break at Kafka: consumer spans are not linked to the producer request",
         days_ago=44, effort=240, attempts=3, tokens=35000,
         title="Propagate W3C traceparent through Kafka headers",
         summary="Inject the context into record headers on produce, extract on consume and start the span as a child.",
         libraries=[{"name": "opentelemetry", "version": "1.24"}]),
    dict(key="jwt_leeway", dev="Meera", project="Mobile 3.0", components=["auth-gateway", "token-service"],
         task="Fresh JWTs are rejected as 'not yet valid' (nbf) for some mobile clients",
         days_ago=33, effort=150, attempts=2, tokens=22000,
         title="Allow 60s clock-skew leeway when validating nbf/iat",
         summary="Server and some issuers drift by tens of seconds; validate with leeway=60.",
         libraries=[{"name": "pyjwt", "version": "2.8"}]),
    dict(key="feature_backfill", dev="Leo", project="Insights Dashboard", components=["feature-store"],
         task="Feature store backfill job runs out of memory on a year of events",
         days_ago=12, effort=480, attempts=5, tokens=70000,
         title="Stream the backfill with a pyarrow dataset scanner, partition by day",
         summary="pandas.read_parquet loaded everything. Use pyarrow.dataset with filters and to_batches(), write per partition.",
         libraries=[{"name": "pyarrow", "version": "15"}],
         lessons=[{"text": "Loading parquet into pandas needs 5-10x the file size in RAM", "kind": "pitfall"}]),
    dict(key="ledger_rounding", dev="Sara", project="Realtime Ledger", components=["ledger"],
         task="Ledger balances drift by a cent after currency conversion",
         days_ago=58, effort=300, attempts=4, tokens=40000,
         title="Store minor units as integers and round once with banker's rounding",
         summary="Floats + rounding at every step. Use integer minor units, Decimal for conversion, round half-even once.",
         libraries=[{"name": "python", "version": "3.12"}]),
    dict(key="ishika_private", dev="Ishika", project="Mobile 3.0", components=["mobile-app"], visibility="private",
         task="My local Android emulator cannot reach the dev API on localhost",
         days_ago=10, effort=30, attempts=2, tokens=5000,
         title="Use 10.0.2.2 instead of localhost from the Android emulator",
         summary="The emulator's localhost is itself; the host machine is 10.0.2.2. Personal setup note."),
    dict(key="payments_team_note", dev="Sara", project="Realtime Ledger", components=["ledger"], visibility="team",
         task="Rotate the ledger database credentials without downtime",
         days_ago=14, effort=90, attempts=1, tokens=10000,
         title="Dual-credential rotation for the ledger DB",
         summary="Create the new user, deploy with both, switch, then revoke the old one. Team-internal runbook."),
]

# Smaller, routine sessions (texture for the org; mostly low effort)
ROUTINE = [
    ("Rohan", "Checkout v2", ["checkout-api"], "Add pagination to the orders list endpoint", 110, 45),
    ("Priya", "Checkout v2", ["auth-gateway"], "Add CORS allowlist for the new checkout domain", 108, 20),
    ("Yash", "Checkout v2", ["checkout-api"], "Validate currency codes against ISO 4217 in checkout requests", 99, 30),
    ("Arjun", "Checkout v2", ["token-service"], "Shorten access token lifetime to 15 minutes", 92, 25),
    ("Sara", "Realtime Ledger", ["ledger"], "Add a read replica for ledger balance queries", 70, 60),
    ("Kabir", "Realtime Ledger", ["events-pipeline"], "Create the ledger.events Kafka topic with 12 partitions", 78, 20),
    ("Leo", "Realtime Ledger", ["warehouse-etl"], "Load ledger events into the warehouse hourly", 66, 90),
    ("Zara", "ARM Migration", ["k8s-deploy"], "Add arm64 node pool and taints in the cluster", 57, 60),
    ("Omar", "ARM Migration", ["ci-pipeline"], "Cache Docker layers between CI runs", 54, 40),
    ("Tom", "Mobile 3.0", ["mobile-app"], "Upgrade React Native to 0.74", 44, 120),
    ("Neha", "Mobile 3.0", ["mobile-app"], "Add dark mode theme tokens", 41, 50),
    ("Ishika", "Mobile 3.0", ["mobile-app"], "Add image compression before upload", 34, 40),
    ("Meera", "Mobile 3.0", ["user-profile"], "Expose profile avatar URL in the profile API", 31, 25),
    ("Ananya", "Insights Dashboard", ["reporting-api"], "Add CSV export endpoint to reporting-api", 28, 45),
    ("Leo", "Insights Dashboard", ["reporting-api"], "Cache dashboard queries for 5 minutes", 22, 35),
    ("Kabir", "Insights Dashboard", ["feature-store"], "Define feature schema for churn model", 18, 60),
    ("Priya", "Mobile 3.0", ["auth-gateway"], "Add device-bound refresh tokens for mobile clients", 27, 90),
    ("Omar", "Insights Dashboard", ["observability"], "Dashboard for reporting-api p95 latency", 15, 30),
]

# (reuser, reuser_project, solution_key, days_ago, task)
REUSES = [
    ("Sara", "Realtime Ledger", "refresh_v2", 60, "ledger admin UI logs out randomly when several calls refresh the token"),
    ("Rohan", "Realtime Ledger", "idem_v2", 50, "deduplicate ledger webhook retries"),
    ("Neha", "Mobile 3.0", "push_ios", 30, "Android and iOS push notifications missing in release builds"),
    ("Leo", "Insights Dashboard", "pg_pool", 19, "warehouse loader hits too many postgres connections"),
    ("Meera", "Mobile 3.0", "rate_limit", 29, "rate limit the OTP verification endpoint"),
    ("Tom", "Mobile 3.0", "presigned_skew", 25, "video upload URLs expire before the upload starts on some devices"),
    ("Omar", "Insights Dashboard", "otel_kafka", 14, "trace context missing between ETL steps"),
    ("Ananya", "Insights Dashboard", "settlement_tz", 21, "dashboard daily totals off around daylight saving"),
    ("Priya", "Mobile 3.0", "jwt_leeway", 28, "tokens not yet valid errors from the partner SDK"),
    ("Kabir", "Insights Dashboard", "idem_v3", 17, "feature events duplicated after pipeline restarts"),
]

# answered questions from the past (cross-team help)
QA = [
    ("Ananya", "What is the retention period on the ledger.events Kafka topic?", "Kabir",
     "7 days on ledger.events; the warehouse keeps the full history. Use the warehouse for backfills older than a week."),
    ("Tom", "Which header does auth-gateway expect for device-bound refresh tokens?", "Priya",
     "Send X-Device-Id with the refresh request; tokens are bound to that id and rejected from other devices."),
    ("Leo", "Is it safe to read ledger balances from the replica for reports?", "Sara",
     "Yes for reports (replica lag < 2s), never for payment decisions; those must hit the primary."),
]

# sessions running right now (kept alive by the fleet in the live demo)
LIVE = [
    ("Kabir", "Insights Dashboard", ["events-pipeline"], "Add schema versioning to ledger events (breaking field rename)"),
    ("Meera", "Mobile 3.0", ["token-service", "auth-gateway"], "Rotate the token signing keys and publish a new JWKS"),
    ("Tom", "Mobile 3.0", ["push-notifications", "mobile-app"], "Batch push notifications to cut APNs costs"),
    ("Leo", "Insights Dashboard", ["reporting-api"], "Daily active users chart is off by one day around midnight"),
    ("Rohan", "Realtime Ledger", ["refunds-worker"], "Refund worker retries flood the ledger after an outage"),
]


def seed(slug: str = "acme", reset: bool = True, live: bool = True) -> dict:
    org = Org(slug)
    if reset:
        org.delete()
        org = Org(slug)
    ensure_schema(org)
    t = now()
    for team, spec in TEAMS.items():
        O.upsert_team(org, team)
        for comp, cat in spec["components"]:
            O.upsert_component(org, comp, team, cat)
        for dev, role in spec["devs"]:
            O.upsert_dev(org, dev, team, role)
    for a, b in DEPENDS_ON:
        O.add_dependency(org, a, b)
    for name, repo, comps, start in PROJECTS:
        O.upsert_project(org, name, repo, comps, started_at=t - start * DAY)

    ids: dict[str, str] = {}
    sessions: dict[str, str] = {}
    for m in MEMORIES:
        start = t - m["days_ago"] * DAY
        s = M.start_session(org, m["dev"], m["task"], m["components"], m["project"],
                            session_id=f"ses_{m['key']}", started_at=start, status="done")
        sessions[m["key"]] = s["session_id"]
        org.write("seed.session_effort", "MATCH (s:Session {id:$sid}) SET s.attempts=$a, s.tokens=$tok",
                  {"sid": s["session_id"], "a": m["attempts"], "tok": m["tokens"]})
        if m.get("failed"):
            old_key, by, err = m["failed"]
            M.report_outcome(org, s["session_id"], ids[old_key], worked=False, error=err)
        res = M.save_solution(org, M.SaveRequest(
            session_id=s["session_id"], title=m["title"], summary=m["summary"], code=m.get("code", ""),
            libraries=m.get("libraries", []), lessons=m.get("lessons", []), visibility=m.get("visibility", "org"),
            builds_on=[ids[k] for k in m.get("builds_on", [])], supersedes=[ids[k] for k in m.get("supersedes", [])],
            effort_minutes=m["effort"], attempts=m["attempts"], tokens_spent=m["tokens"],
            created_at=start + m["effort"] * 60, solution_id=f"sol_{m['key']}"))
        assert res["decision"] == "ACCEPT", res
        ids[m["key"]] = res["solution_id"]
        M.end_session(org, s["session_id"], ended_at=start + max(m["effort"], 30) * 60)

    for i, (dev, project, comps, task, days, effort) in enumerate(ROUTINE):
        start = t - days * DAY
        s = M.start_session(org, dev, task, comps, project, session_id=f"ses_routine_{i}", started_at=start, status="done")
        M.save_solution(org, M.SaveRequest(session_id=s["session_id"], title=task,
                                           summary=f"Routine change: {task.lower()}. Done and merged.",
                                           effort_minutes=effort, attempts=1, tokens_spent=effort * 400,
                                           created_at=start + effort * 60, solution_id=f"sol_routine_{i}"))
        M.end_session(org, s["session_id"], ended_at=start + effort * 60)

    for i, (dev, project, key, days, task) in enumerate(REUSES):
        start = t - days * DAY
        s = M.start_session(org, dev, task, None, project, session_id=f"ses_reuse_{i}", started_at=start, status="done")
        M.record_reuse(org, s["session_id"], ids[key], outcome="worked", at=start + 600)
        M.end_session(org, s["session_id"], ended_at=start + 1800)

    for asker, q, answerer, text in QA:
        r = Msg.ask_org(org, q, dev=asker)
        Msg.answer(org, r["question_id"], text, dev=answerer)

    live_ids = []
    if live:
        for i, (dev, project, comps, task) in enumerate(LIVE):
            s = M.start_session(org, dev, task, comps, project, agent="fleet", session_id=f"ses_live_{i}",
                                started_at=t - (i + 1) * 420)
            live_ids.append(s["session_id"])
            M.touch_session(org, s["session_id"])  # heartbeat: live right now
        for sid in live_ids:
            P.detect_overlaps(org, sid)
    return {"org": slug, "solutions": ids, "live_sessions": live_ids}


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(seed(sys.argv[1] if len(sys.argv) > 1 else "acme"), indent=1))
