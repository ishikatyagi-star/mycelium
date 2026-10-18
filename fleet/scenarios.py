"""What the simulated agents in the 'graphhq' org work on. Real people (Ishika, Yash) join with real Claude Code.

Each fleet agent cycles through its tasks. Some tasks carry a question it will ask the org,
or a change it will announce, so the live view always has coordination happening.
"""

FLEET = {
    "Meera": [
        dict(task="Rotate the token signing keys and publish a new JWKS", components=["token-service", "auth-gateway"],
             announce=("token-service", "Signing keys rotate today; clients must refetch JWKS when they see an unknown kid"),
             knows="New signing keys go live at 14:00 UTC. Old keys stay in the JWKS for 24h. Clients should refetch "
                   "/.well-known/jwks.json on an unknown kid instead of caching forever."),
        dict(task="Add device binding to refresh tokens for the partner SDK", components=["token-service"]),
    ],
    "Kabir": [
        dict(task="Add schema versioning to ledger events (breaking field rename amount -> amount_minor)",
             components=["events-pipeline", "ledger"],
             announce=("events-pipeline", "ledger.events v2: field 'amount' renamed to 'amount_minor' (integer). v1 "
                                          "published in parallel for 2 weeks"),
             knows="ledger.events v2 renames amount to amount_minor (integer minor units). v1 and v2 are dual-published "
                   "for two weeks; consumers should switch on the schema_version header."),
        dict(task="Kafka consumer lag spikes on the warehouse loader during month end", components=["events-pipeline"],
             ask="Did anyone tune max.poll.records for the warehouse loader before?"),
    ],
    "Tom": [
        dict(task="Batch push notifications to cut APNs costs", components=["push-notifications", "mobile-app"],
             knows="We batch pushes per user in 30s windows now; silent pushes are not batched."),
        dict(task="Deep links from push notifications open the wrong screen on Android 15",
             components=["push-notifications", "mobile-app"]),
    ],
    "Leo": [
        dict(task="Daily active users chart is off by one day around midnight", components=["reporting-api"],
             ask="How did we fix the day-boundary timezone bug in the settlement report?"),
        dict(task="Speed up the cohort retention query in reporting-api", components=["reporting-api", "warehouse-etl"]),
    ],
    "Rohan": [
        dict(task="Refund worker retries flood the ledger after an outage", components=["refunds-worker", "ledger"],
             ask="Is there a standard way we make Kafka consumers idempotent here?"),
        dict(task="Partial refunds for split-tender orders", components=["refunds-worker", "checkout-api"]),
    ],
    "Priya": [
        dict(task="Login page gets hammered by credential stuffing from a botnet", components=["auth-gateway"]),
        dict(task="Add WebAuthn passkeys to auth-gateway", components=["auth-gateway", "user-profile"],
             announce=("auth-gateway", "New /webauthn endpoints; /login now returns 'mfa_required' for passkey users")),
    ],
    "Ananya": [
        dict(task="Dedupe the customer export file from the partner CRM before loading", components=["warehouse-etl"]),
        dict(task="Postgres connections exhausted when the ETL fans out", components=["warehouse-etl"]),
    ],
    "Zara": [
        dict(task="arm64 builds of the reporting-api image fail installing psycopg wheels", components=["ci-pipeline"]),
        dict(task="Move staging to the arm64 node pool", components=["k8s-deploy"]),
    ],
    "Neha": [
        dict(task="Offline edits lost when two tablets sync the same note", components=["offline-sync"]),
        dict(task="App logs users out after resuming from background", components=["mobile-app", "auth-gateway"],
             ask="Who knows how our token refresh is supposed to work on mobile?"),
    ],
    "Sara": [
        dict(task="Ledger balance drift of one cent after FX conversion", components=["ledger"]),
        dict(task="Stripe webhook retries double-credit wallet top-ups", components=["payment-webhooks", "ledger"]),
    ],
}
