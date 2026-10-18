# Brief for Yash's Claude Code session: build `web/`

Paste this into your Claude Code session from the repo root. You own **only `web/`**. Ishika's session owns everything else, so don't edit files outside `web/`.

## What Mycelium is (one paragraph)
Mycelium connects every AI agent in a company through one shared context graph in FalkorDB.
- **Across time:** agents recall what anyone solved before. Recall skips stale or broken fixes via `SUPERSEDES`, ranks hard-won fixes higher, and credits the author.
- **Across the org, live:** agents see who is working on related things right now, ask questions that the graph routes to the right agent, and get warned when a component they depend on changes.

The web app is how judges *see* this. It must look polished and make the graph visible.

## Stack
- Next.js (App Router) + TypeScript + Tailwind + shadcn/ui.
- `react-force-graph-2d` for graphs.
- Deploy on Vercel.
- `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`); demo org `graphhq`.

## Live API
`NEXT_PUBLIC_API_URL=https://api-production-377ba.up.railway.app`. This is the deployed public demo, with the fleet of simulated agents running live.

Public mode rules:
- `GET`s, `/recall`, `/compare`, `/ask` and `/notices` work on `graphhq` (rate-limited).
- Agent-identity writes (sessions, saving memory, answers) are reserved for agents. For a "try it yourself" flow, `POST /api/sandbox` returns a private copy of the org (`{org}`) where everything is writable.

## Data
- The API contract is `docs/api-contract.md`.
- Real captured responses are in `docs/mocks/*.json`; SSE samples are in `docs/mocks/events.jsonl`.
- Start against the mocks (a `USE_MOCKS` flag), then switch to the live API. To run it locally:
  ```
  docker compose up -d && uv sync && PYTHONPATH=. uv run uvicorn api.main:app --port 8000
  ```

## Pages, in priority order
1. **`/` Live org** (the hero screen; judges see it first):
   - A force graph with Teams as big nodes, Components (colored by team) and `DEPENDS_ON` arrows, plus live Session nodes attached to the components they `TOUCHES`. Data comes from `GET /graph?view=org` and `/live`.
   - A right sidebar shows the live activity feed from SSE `/events`.
   - Animations:
     - `overlap`: dashed line pulse between two sessions.
     - `question_routed`: a particle travels from asker to target.
     - `notice`: ripple across dependents.
     - `reuse`: a glow from author to reuser.
   - Header counters come from `/overview` counts: sessions, memories, live agents, tokens saved.
2. **`/ask`, Recall:**
   - A persona picker (devs from `/overview`) and a text box.
   - Each recall card shows:
     - title, author and team badge, project, "N days ago"
     - an **effort badge** ("3 days · 14 attempts")
     - "skipped stale fix" callouts from `skipped`
     - lessons, styled by kind (pitfall = amber, dead_end = red, tip = green)
     - code
     - "~168k tokens saved"
   - A small path graph highlights `path`, and a collapsible **Show Cypher** panel lists `trace`.
   - The same page has an **Ask the org** mode (`POST /ask`):
     - `mode: memory`: the answer card.
     - `mode: routed`: who it was routed to, the reason, the candidate ranking, and the path graph.
3. **`/compare`, Vector vs Mycelium:** two columns for the same query. Preset query buttons: "access token expired returns 401, refresh it and retry the request" (vector-only returns the *superseded* fix first; highlight that red).
4. **`/threads`:** agent-to-agent Q&A threads with routing reason and answer, plus "became memory" chips.
5. **`/brain`, Company brain:**
   - Experts by PageRank.
   - Knowledge at risk (hard-won fixes only one person touched).
   - Tokens saved per team (bar).
   - Team→team help flows (sankey or chord).
   - who_knows search.
6. **`/lineage/[id]`:** a timeline of how a fix evolved across projects (`BUILDS_ON` / `SUPERSEDES`). Example: `sol_idem_v4`.
7. **Notice composer** (a modal on `/`): pick a component and announce a change; show the impact list and the ripple.

## Design
- Dark-first, calm, "living network" feel: mycelium or bioluminescent accents (teal/green on near-black). Make sure light mode still works.
- One accent color per team, used consistently everywhere (node colors, badges).
- Every graph-backed answer has a visible **path**. Explainability is a judging point.
- Fast first paint. No spinners longer than 300 ms on mock data.
- Mobile-width friendly enough for screenshots, but optimize for a 1440px laptop (the demo video).
