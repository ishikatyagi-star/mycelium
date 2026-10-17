# Concurrency: many agents, one org graph

N simulated agents run the full agent loop in parallel through the HTTP API (FastAPI, single uvicorn worker) against one FalkorDB graph (local Docker, Apple Silicon laptop). Latency is end-to-end per HTTP call, so it includes embedding the text (CPU, in the API process) and JSON. Reproduce: `PYTHONPATH=. uv run python -m fleet.load`.

| Agents | Ops | Ops/s | Errors | start_session p50/p95 | recall p50/p95 | save_solution p50/p95 | ask_org p50/p95 |
|---|---|---|---|---|---|---|---|
| 10 | 3235 | 215.7 | 0 | 71.6 / 142.6 ms | 49.5 / 97.8 ms | 24.7 / 61.2 ms | 93.5 / 150.8 ms |
| 25 | 3478 | 231.9 | 0 | 176.9 / 309.9 ms | 110.9 / 202.5 ms | 86.4 / 163.1 ms | 156.5 / 265.1 ms |
| 50 | 3108 | 207.2 | 0 | 322.5 / 624.4 ms | 209.0 / 510.1 ms | 186.0 / 482.1 ms | 274.7 / 576.7 ms |

Notes: writes are short single-purpose Cypher statements (MERGE-based), so concurrent agents never hold long transactions. The bottleneck at high N is the single API worker computing embeddings, not FalkorDB: graph query times stay in the low milliseconds (see the `trace` in any API response).
