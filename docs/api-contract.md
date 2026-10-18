# Mycelium API contract (for `web/`)

Base URL: `NEXT_PUBLIC_API_URL` (local: `http://localhost:8000`). JSON everywhere. The demo org is `graphhq`.

Every read endpoint that touches the graph returns a `trace` array. This feeds the **Show Cypher** panel.
```json
"trace": [{"name": "recall.hybrid", "cypher": "CALL db.idx.vector.queryNodes(...) ...", "params": {"k": 8}, "ms": 3.1, "rows": 5}]
```

Mock responses for every endpoint are in `docs/mocks/*.json`, captured from the real API, so where the shapes below and a mock differ, **the mock is right**. `docs/mocks/events.jsonl` has sample SSE events. Build against the mocks first, then point `NEXT_PUBLIC_API_URL` at a running API (`uv run uvicorn api.main:app` locally).

## Shared shapes
```ts
type Dev = { name: string; team: string }
type GraphNode = { id: string; label: "Team"|"Component"|"Dev"|"Project"|"Session"|"Task"|"Solution"|"Lesson"|"Error"|"Question"|"Answer"|"Notice"|"Library"|"Handoff"; name: string; team?: string; status?: string }
type GraphLink = { source: string; target: string; type: string }   // type = relationship type, e.g. "SOLVES"
type Path = { nodes: GraphNode[]; links: GraphLink[] }               // the traversal to highlight

type Memory = {               // one recall hit
  solution: { id: string; title: string; summary: string; code: string; status: "active"|"superseded"|"broken";
              effort_minutes: number; attempts: number; tokens_spent: number; visibility: "private"|"team"|"org"; created_at: number }
  task: { id: string; text: string }
  similarity: number          // 0..1 vector similarity of the task
  score: number               // final rank score (similarity × status × effort × reuse)
  author: Dev
  project: { name: string } | null
  session: { id: string; started_at: number }
  lessons: { text: string; kind: "pitfall"|"tip"|"dead_end" }[]
  errors: { signature: string }[]
  skipped: { id: string; title: string; status: string; reason: string }[]   // stale/broken versions we walked past via SUPERSEDES
  builds_on: { id: string; title: string }[]
  reuse_count: number
  tokens_saved_estimate: number
  path: Path
}
```
Timestamps are epoch seconds.

## Endpoints
| Method | Path | Body / query | Returns |
|---|---|---|---|
| POST | `/api/orgs` | `{slug, teams:[{name, services:[{name, category?}], people:[{name, role?}]}], dependencies:[{service, depends_on}], projects?:[{name, repo?, services}]}` | `201 {org, overview, next}`; `409` slug exists; `422 {problems:[...]}` |
| GET | `/api/health` | – | `{ok, falkordb: true}`. Returns **503** if FalkorDB is down |
| GET | `/api/orgs/{org}/overview` | – | `{teams:[{name, components:[...], devs:[...]}], projects:[...], counts:{sessions, solutions, live_sessions, questions, tokens_saved}}` |
| GET | `/api/orgs/{org}/graph` | `?view=org\|memory\|all` | `{nodes: GraphNode[], links: GraphLink[]}` for the force graph |
| GET | `/api/orgs/{org}/live` | – | `{sessions:[{id, dev:Dev, task, components:[...], started_at, last_seen, overlaps:[{session_id, dev:Dev, task, score}]}]}` |
| POST | `/api/orgs/{org}/recall` | `{query, as_dev, k?}` | `{results: Memory[], trace}` |
| POST | `/api/orgs/{org}/compare` | `{query, as_dev}` | `{vector_only: Memory[], mycelium: Memory[], trace}`. Same query, side by side |
| POST | `/api/orgs/{org}/ask` | `{question, as_dev, session_id?}` | `{question_id, mode: "memory"\|"routed"\|"not_found", answer?: Memory, routed_to?: {kind:"session"\|"dev", id, dev:Dev, reason, score}, candidates:[...same], path: Path, trace}` |
| GET | `/api/orgs/{org}/questions` | – | `{threads:[{id, text, asker:Dev, status, routed_to, reason, path, answer?:{text, by:Dev, at}, at}]}` |
| POST | `/api/orgs/{org}/questions/{id}/answer` | `{text, as_dev}` | `{ok, memory_solution_id}` |
| POST | `/api/orgs/{org}/notices` | `{component, text, as_dev, kind?}` | `{notice_id, impact:[{session_id, dev:Dev, component, depth, path: Path}], team_deliveries:[{team, component}], trace}` |
| GET | `/api/orgs/{org}/lineage/{solution_id}` | – | `{chain:[{id, title, project, author:Dev, created_at, rel:"BUILDS_ON"\|"SUPERSEDES"}], path: Path}` |
| GET | `/api/orgs/{org}/brain` | – | `{experts:[{dev:Dev, pagerank, helped:int}], at_risk:[{solution_id, title, owner:Dev, effort_minutes}], savings:[{team, tokens_saved, reuses}], help_flows:[{from_team, to_team, count}]}` |
| GET | `/api/orgs/{org}/who_knows` | `?topic=` | `{experts:[{dev:Dev, score, evidence:[{solution_id, title}]}], trace}` |
| POST | `/api/sandbox` | – | `{org: "sandbox_ab12cd"}`: a private copy of `graphhq` (GRAPH.COPY) that visitors can write to |
| GET | `/api/orgs/{org}/events` | SSE | stream of `Event` (see below) |

`as_dev` is a dev name from the overview (for example `"Ishika"`, `"Yash"`), used to scope visibility.

## SSE events (`/api/orgs/{org}/events`)
Each SSE message has `event: <type>` and `data: <json>`:
```ts
type Event =
 | {type:"session_started", session_id, dev:Dev, task, components:string[]}
 | {type:"session_ended",   session_id}
 | {type:"overlap",         a:{session_id, dev:Dev}, b:{session_id, dev:Dev}, score, task}
 | {type:"memory_saved",    solution_id, title, dev:Dev}
 | {type:"reuse",           solution_id, title, by:Dev, author:Dev, tokens_saved}
 | {type:"question_asked",  question_id, text, asker:Dev}
 | {type:"question_routed", question_id, to:{kind, id, dev:Dev}, reason}
 | {type:"answer",          question_id, by:Dev, text}
 | {type:"notice",          notice_id, component, text, by:Dev, delivered_to:[{session_id, dev:Dev}]}
 | {type:"handoff",         handoff_id, from:Dev, task}
```

## Suggested views (from the plan)
1. **Live org:** force graph of Teams → Components (with DEPENDS_ON) and live Sessions attached to the components they touch. Animate SSE events: pulse on overlap, a moving particle along the routing path for questions, a ripple across dependents for notices.
2. **Ask:** pick a persona (`as_dev`), type a problem, and see recall cards (credit, effort badge "3 days · 14 attempts", warnings from lessons, "skipped stale fix" callouts, tokens saved).
3. **Path + Show Cypher:** highlight `path` in a small graph; a collapsible `trace` list.
4. **Vector vs Mycelium:** two columns from `/compare`.
5. **Lineage:** timeline from `/lineage/{id}`.
6. **Threads:** agent-to-agent questions and answers with routing reasons.
7. **Company brain:** experts (PageRank), knowledge at risk, tokens saved per team, team→team help flows (chord or sankey).
