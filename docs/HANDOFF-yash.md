# Handoff for Yash (Oct 18, 05:00 IST; updated 12:00)

> ## ⚠️ Update, Oct 18 12:00 IST: your job changed
> Nothing had landed in `web/` by noon, so (as agreed with Ishika) **Ishika's Claude Code session is now building the web app**. Please **don't edit `web/`**, so we avoid conflicts. Your new priorities:
> 1. **Demo video**: follow [`docs/demo-script.md`](demo-script.md) shot by shot. You're the second terminal ("Yash", Payments). Ask Ishika for the agent write token to connect your Claude Code. Record once the web app is deployed (target ~19:00–20:00).
> 2. **dev.to blog**: polish [`blog/draft.md`](../blog/draft.md) (it's a full draft). Add screenshots of the web app and your own voice, and publish once the links are final. It's for the AirPods prize.
> 3. **Submission form**: collect the links and fill the WeMakeDevs form (Tracks 2 + 3).
>
> If you already started a web app locally, tell Ishika now. Don't push it to `web/`.

Hey Yash. Ishika is asleep. This page has everything you need to catch up and start on the web app.

**Deadline: Oct 19, 8:30 AM IST.** Our target is to **submit by 6:30 AM**, with **feature freeze at 01:30**.

## Links
| What | Link |
|---|---|
| **Live web app** | https://web-production-76872.up.railway.app |
| GitHub repo (public) | https://github.com/ishikatyagi-star/mycelium |
| Live API (deployed) | https://api-production-377ba.up.railway.app |
| Live health check | https://api-production-377ba.up.railway.app/api/health |
| Live org overview (JSON) | https://api-production-377ba.up.railway.app/api/orgs/graphhq/overview |
| Live event stream (SSE) | https://api-production-377ba.up.railway.app/api/orgs/graphhq/events |
| Interactive API docs | https://api-production-377ba.up.railway.app/docs |
| **Your build brief (start here)** | [`docs/web-brief.md`](web-brief.md) |
| API contract | [`docs/api-contract.md`](api-contract.md) |
| Real sample responses | [`docs/mocks/`](mocks/) (every endpoint) + `events.jsonl` (SSE) |
| Graph model | [`docs/graph-model.md`](graph-model.md) |
| Every Cypher query | [`docs/cypher.md`](cypher.md) |
| Benchmark results | [`eval/results.md`](../eval/results.md), [`eval/concurrency.md`](../eval/concurrency.md) |
| README (the pitch) | [`README.md`](../README.md) |
| Hackathon rules | https://www.wemakedevs.org/hackathons/falkordb/rules |

## What we're building (30 seconds)
**Mycelium** connects every AI agent in a company through one shared context graph in FalkorDB.

- **Across time.** An agent recalls what anyone solved before, in any project. The graph adds what plain similarity search can't:
  - It skips fixes that later broke (`SUPERSEDES`) and warns about the dead ends.
  - It ranks hard-won fixes higher.
  - It credits the author.
- **Across the org, live.** Agents see who is working on related things right now. They can ask the org (`ask_org`): the graph routes the question to the agent that is live on the relevant component and shows why. And they get warned when a component they depend on changes (`DEPENDS_ON` ripple).
- **It works in real tools.** Agents connect from inside Claude Code (MCP server plus hooks). A fleet of 10 simulated agents across 5 teams keeps the demo company busy around the clock.

**Tracks:** 02 Agent Memory & Coordination (primary) and 03 Company Brain.

## Status
| Piece | Status |
|---|---|
| Graph core (memory, recall, supersede walk, lineage, visibility, write gate) | ✅ done |
| Agent network (presence, overlaps, ask_org routing, answers become memory, change propagation, handoffs) | ✅ done |
| Company brain (PageRank experts, knowledge at risk, tokens saved, help flows) | ✅ done |
| HTTP API + SSE live events + sandbox orgs + public read-only mode | ✅ deployed on Railway |
| Database | ✅ **FalkorDB Cloud** (sponsor's cloud, free tier, Mumbai) |
| MCP server (13 tools) + Claude Code hooks + one-command installer | ✅ done; real in-app test pending (Ishika, after she wakes) |
| Fleet: 10 simulated agents, LLM-powered answers (Groq) | ✅ running live on Railway |
| Tests | ✅ 19 passing (local and on FalkorDB Cloud) |
| Benchmark: stale-fix trap 12/12 vs 0/12, routing 8/8 vs 4/8, change impact precision/recall 1.0 | ✅ `eval/results.md` |
| README, graph model, Cypher docs, AI disclosure | ✅ first versions done |
| **Web app (`web/`)** | ❌ **not started: this is yours, and it's the top priority** |
| Demo video, dev.to blog, submission form | ⏳ later today / tonight |

## Your job: the web app
1. Clone the repo and open your Claude Code session **in the repo root**:
   ```bash
   git clone https://github.com/ishikatyagi-star/mycelium && cd mycelium
   ```
2. Paste [`docs/web-brief.md`](web-brief.md) into Claude Code as your first message. It covers the stack (Next.js + Tailwind + `react-force-graph-2d`), the 7 pages in priority order, and the design.
3. **Work only inside `web/`.** Ishika's Claude Code session owns everything else, which keeps us out of merge conflicts.
4. Point it at the live API, which has real data and live agents:
   ```
   NEXT_PUBLIC_API_URL=https://api-production-377ba.up.railway.app
   ```
   No backend setup is needed. To run the backend locally instead, the steps are in the README.
5. Commit and push to `master` often (small commits, only `web/`).
6. Deploy to **Vercel** (root directory `web`). Ishika's Vercel is already logged in on her machine if you'd rather she deploys it.

**Priority if time gets tight:**
1. Live org view (the hero screen)
2. Ask/recall page with path + Show Cypher
3. Vector-vs-Mycelium compare
4. Threads
5. Company brain
6. Lineage
7. Notice composer

**Things to know about the live API:**
- On the demo org `graphhq`, anyone can call: all `GET`s, `/recall`, `/compare`, `/ask` and `/notices`.
- Writes that act as an agent (sessions, saving memory, answers) are agent-only and return **403** from the browser.
- For a "try it yourself" button, call `POST /api/sandbox`. It returns `{ "org": "sandbox_xxxx" }`, a private copy where everything is writable.
- Every graph-backed response has a `trace` array (the exact Cypher). Show it, because judges care about explainability.
- `/api/orgs/graphhq/events` is Server-Sent Events. Use `EventSource` and expect these event types: `session_started`, `overlap`, `question_asked`, `question_routed`, `answer`, `notice`, `reuse`, `memory_saved`, `handoff`, `session_ended`.

**Good demo queries to preset in the UI:**
- Compare: `access token expired returns 401, refresh it and retry the request`. Vector-only returns the *superseded, broken* fix; Mycelium returns the real one. Highlight that in red and green.
- Recall as Ishika: `mobile app randomly logs users out when several API calls refresh the token at the same time`
- Ask the org: `Is anyone rotating the token-service signing keys right now?` (routed to Meera's live agent)
- Notice: component `token-service`, text `Signing keys rotate today; refetch JWKS on unknown kid`
- Lineage: `sol_idem_v4` (4 steps across 2 projects and 2 teams)

## Later today: you in the demo video
The video's opening shows **two real Claude Code terminals**: Ishika (Mobile) and you (Payments) in the same org. To connect your Claude Code to the live org as "Yash", you need the **agent write token**. It's deliberately **not in the repo**, so ask Ishika for it privately. Then run, from the repo:
```bash
MYC_WRITE_TOKEN=<token from Ishika> scripts/install_claude.sh /path/to/any/project Yash graphhq https://api-production-377ba.up.railway.app "Realtime Ledger"
```

## Timeline (IST)
| When | What |
|---|---|
| now → ~14:00 | You: web app MVP (live org + ask + compare) on the live API |
| ~14:00–19:00 | Ishika sleeps → wakes, tests Claude Code flow; you keep polishing web |
| 19:00–23:00 | Deploy web to Vercel; integrate; end-to-end run of the demo script |
| 23:00–01:30 | Polish, fix bugs. **Feature freeze 01:30** |
| 01:30–03:30 | Record the demo video (about 3 min, working demo in the first 60 s) |
| 03:30–05:00 | dev.to blog (AirPods prize) |
| 05:00–06:30 | Submit on WeMakeDevs (Tracks 2 + 3) |

Stagger sleep with Ishika so one of you is always building. A good window for you is roughly 23:00–03:00.

## Rules we must respect
- FalkorDB must stay central. It is: remove it and everything returns 503.
- We disclose AI use. See [`docs/ai-disclosure.md`](ai-disclosure.md), and add a line about your Claude Code usage for `web/`.
- Both of us must be able to explain the graph model and queries if asked. Skim [`docs/graph-model.md`](graph-model.md).
