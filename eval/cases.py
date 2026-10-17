"""Benchmark cases over the synthetic 'acme' org. Written by us, alongside the seed (see eval/results.md caveats)."""

# Queries phrased like the *stale* fix. Expected: the current fix (graph should walk SUPERSEDES).
STALE_TRAP = [
    ("access token expired returns 401, refresh it and retry the request", "sol_refresh_v2", "sol_refresh_v1"),
    ("on 401 refresh the oauth token then replay the original call once", "sol_refresh_v2", "sol_refresh_v1"),
    ("build linux/arm64 docker images in CI using buildx and qemu", "sol_arm_native", "sol_arm_qemu"),
    ("set up QEMU emulation to produce arm64 images on x86 runners", "sol_arm_native", "sol_arm_qemu"),
    ("kafka consumers get kicked out of the group, should we raise session.timeout.ms", "sol_kafka_rebalance", "sol_kafka_rebalance_v1"),
    ("consumer group rebalances constantly; increase the session timeout", "sol_kafka_rebalance", "sol_kafka_rebalance_v1"),
    ("iOS pushes not delivered, regenerate the APNs certificate", "sol_push_ios", "sol_push_ios_v1"),
    ("apns certificate expired? push notifications stopped on iPhone", "sol_push_ios", "sol_push_ios_v1"),
    ("postgres too many connections, raise max_connections", "sol_pg_pool", "sol_pg_pool_v1"),
    ("increase the postgres connection limit for the reporting service", "sol_pg_pool", "sol_pg_pool_v1"),
    ("drop duplicate rows from customer csv using pandas drop_duplicates on email", "sol_csv_dedupe", "sol_csv_dedupe_v1"),
    ("dedupe a CSV of customers by email column in pandas", "sol_csv_dedupe", "sol_csv_dedupe_v1"),
]

# Paraphrased problems from *another team / project* than the author. Expected top-1 solution.
CROSS_PROJECT = [
    ("Ishika", "mobile app randomly logs users out when several API calls refresh the token at once", "sol_refresh_v2"),
    ("Leo", "stripe sends duplicate webhook events and we charge twice", "sol_idem_v1"),
    ("Tom", "refund events applied twice to the ledger after the worker restarts", "sol_idem_v4"),
    ("Priya", "traces are broken between the producer and the kafka consumer", "sol_otel_kafka"),
    ("Neha", "JWT rejected as not yet valid on some phones", "sol_jwt_leeway"),
    ("Kabir", "photo uploads fail with signature does not match on devices with wrong clock", "sol_presigned_skew"),
    ("Yash", "daily report double counts transactions on the daylight saving change day", "sol_settlement_tz"),
    ("Ishika", "currency conversion leaves balances off by one cent", "sol_ledger_rounding"),
    ("Omar", "backfill job out of memory reading a year of parquet files", "sol_feature_backfill"),
    ("Sara", "edits made offline on two devices overwrite each other", "sol_offline_conflicts"),
    ("Zara", "credential stuffing attack against the login endpoint", "sol_rate_limit"),
    ("Rohan", "our dual write to postgres and kafka loses events when the producer fails", "sol_idem_v3"),
]

# Questions -> who should get them right now. Baseline router: author of the most similar past task.
# Live sessions come from seed LIVE (Kabir events-pipeline, Meera token-service/auth-gateway, Tom push,
# Leo reporting-api, Rohan refunds-worker).
ROUTING = [
    ("Yash", "Is anyone changing the token-service signing keys right now?", "Meera"),
    ("Ishika", "Our app caches the JWKS public key; is a key rotation happening today?", "Meera"),
    ("Ananya", "Is the ledger events schema about to change? my ETL parses the amount field", "Kabir"),
    ("Sara", "Who is working on the events-pipeline right now? we need a new topic", "Kabir"),
    ("Neha", "Is someone changing how push notifications are batched?", "Tom"),
    ("Sara", "Is anyone touching the refunds worker retries this week?", "Rohan"),
    ("Kabir", "Who is changing the reporting-api queries right now?", "Leo"),
    ("Tom", "Is anyone working on the auth-gateway login flow right now?", "Meera"),
]

# Change notices -> live agents that must be warned (they work on something that depends on the component)
# and live agents that must NOT be bothered. (component, text, announcer, expected, not_expected)
IMPACT = [
    ("token-service", "Signing keys rotate today; refetch JWKS on unknown kid", "Priya",
     {"Meera", "Tom"}, {"Kabir", "Leo", "Rohan"}),
    ("ledger", "Balance API returns integer minor units", "Sara", {"Rohan", "Tom"}, {"Kabir", "Leo", "Meera"}),
    ("events-pipeline", "ledger.events v2 renames amount to amount_minor", "Ananya",
     {"Kabir", "Rohan", "Leo", "Tom"}, {"Meera"}),
    ("warehouse-etl", "Hourly load moves to 15 minute micro-batches", "Ananya", {"Leo"}, {"Tom", "Meera", "Rohan", "Kabir"}),
]
