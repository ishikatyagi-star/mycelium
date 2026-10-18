---
title: "Mycelium: Your Agents Keep Re-Solving Last Quarter's Bugs. We Gave the Whole Company One Graph."
published: false
tags: falkordb, ai, agents, graphdatabase
cover_image: # TODO: screenshot of the live org view
---

> **TL;DR:** Mycelium is one shared context graph, on FalkorDB, for every AI agent in a company.
> - Agents recall what anyone solved before, in any project, and the graph walks past fixes that later broke.
> - Agents see who is working on related things *right now*, ask questions the graph routes to the right live agent, and get warned when something they depend on changes.
> - It plugs into Claude Code through MCP and hooks.
> - On our benchmark, plain vector search hands back a broken, superseded fix on 12/12 "stale-fix trap" queries. Mycelium: 0/12.
>
> 🔗 **Live demo:** _TODO web URL_ · **API:** https://api-production-377ba.up.railway.app/docs · **Code:** https://github.com/ishikatyagi-star/mycelium · **Video:** _TODO_
>
> Built for **Graph Hacks: Context for AI Agents** (WeMakeDevs × FalkorDB), Track 2 (Agent Memory & Coordination) and Track 3 (Company Brain).

## The bug you already fixed

Six weeks ago, Yash on the Payments team spent three days on a token-refresh race. Parallel requests all got `401`, each fired its own refresh, and because refresh tokens rotate on use, the refreshes invalidated each other and users got logged out at random. He tried 14 things. Jittered retries only delayed the storm. Raising the token endpoint's rate limit hid it in staging and not in prod. The fix was a single-flight refresh.

Today Ishika, on the Mobile team, opens Claude Code and types: *"users get logged out randomly when several requests hit 401 at the same time."*

Her agent has never heard of Yash's three days. Neither has she. The repo docs were never updated. So the agent starts from zero, and it confidently suggests "retry once after refreshing the token on 401". That is exactly the naive fix that caused the storm in the first place, and it's sitting in the team's history marked as the thing that failed.

That's one direction of the problem: **across time, engineering history repeats, and agents can't see it.**

The other direction is happening right now. While Ishika's agent works, Meera's agent on the Identity team is rotating the token-signing keys that Ishika's app caches. Kabir's agent on Data is renaming a field in the event schema that three other teams parse. **Across the org, every agent is an island.** Duplicate work goes unnoticed, breaking changes go unannounced, and the agent that has the answer is on another team.

## What Mycelium does

Mycelium (named after the fungal networks that connect trees in a forest) gives every agent in the company **one shared context graph**:

- **Recall across time and teams, with credit.** *"Yash (Payments) solved this in Checkout v2: 3 days, 14 attempts. Here's the fix, the dead ends to skip, and roughly 168k tokens you don't need to spend."*
- **Memory that corrects itself.** Recall follows `SUPERSEDES` past fixes that later failed, and tells you what it skipped and why.
- **Hard-won knowledge ranks first.** Effort is part of the score. Every reuse credits the author.
- **Knowledge compounds.** `BUILDS_ON` lineage shows how a fix evolved across projects and teams.
- **Live awareness.** Which agents are running now, on which components. Overlapping work across teams is detected, and both agents are told.
- **Agents talk to agents.** `ask_org` answers from memory first. Otherwise the graph routes the question to the agent that's **live on the relevant component right now**, or to the owners or past solvers, and shows the path. The answer becomes memory, so nobody has to ask again.
- **Change propagation.** Announce a change to `token-service`, and every live agent whose work *depends on it* is warned. Nobody else is.
- **Company brain.** Who knows X (PageRank over who credits whom), knowledge at risk (hard fixes only one person has ever touched), tokens saved per team.

And it lives **inside the tools developers already use**: an MCP server with 13 tools plus Claude Code hooks, so memories and incoming messages show up in the agent's context without anyone asking.

## Why it has to be a graph

Every question an agent needs answered here is a relationship:

| The agent needs to know | The graph answers with |
|---|---|
| Has anyone solved this? | vector KNN on `Task` → `(Solution)-[:SOLVES]->(Task)` |
| ...is that fix still good? | `SUPERSEDES*`, `FAILED_WITH` |
| ...what did they try that didn't work? | `(Solution)-[:TAUGHT]->(:Lesson {kind:'dead_end'})` |
| Am I allowed to see it? | `visibility` + `MEMBER_OF` |
| Who's working on something similar right now? | live `Session` → `WORKED_ON` → similar `Task` |
| Who should I ask? | `(live Session)-[:TOUCHES]->(Component)`, `(Team)-[:OWNS]->`, PageRank over `CREDITS` |
| Who breaks if I change this? | `(dep)-[:DEPENDS_ON*1..3]->(changed)` ← `TOUCHES` ← live sessions |

A vector store can find text that *looks* related. It cannot know that a fix was superseded, who is live on what, or what depends on what, because that information *is* the relationships.

We also ran the "removal test" the rules ask for: take FalkorDB away and Mycelium does nothing. Every endpoint returns `503`, and there's a test for it. There's no cache and no fallback store.

## The graph model

One FalkorDB graph per organisation (`org_<slug>`). That's the tenant boundary.

```
(:Team)-[:OWNS]->(:Component)-[:DEPENDS_ON]->(:Component)
(:Dev)-[:MEMBER_OF]->(:Team)
(:Dev)-[:RAN]->(:Session {status: live|done, last_seen})-[:TOUCHES]->(:Component)
(:Session)-[:WORKED_ON]->(:Task {embedding: vecf32(384)})<-[:SOLVES]-(:Solution {status, visibility, effort_minutes, attempts})
(:Solution)-[:SUPERSEDES|BUILDS_ON]->(:Solution)
(:Solution)-[:TAUGHT]->(:Lesson {kind: pitfall|tip|dead_end})
(:Session)-[:REUSED {tokens_saved}]->(:Solution)       (:Dev)-[:CREDITS]->(:Dev)
(:Dev)-[:ASKED]->(:Question)-[:ROUTED_TO {reason}]->(:Session)    (:Answer)-[:BECAME]->(:Solution)
(:Notice)-[:AFFECTS]->(:Component)   (:Notice)-[:DELIVERED_TO]->(:Session)
(:Session)-[:OVERLAPS]->(:Session)   (:Session)-[:HANDED_OFF]->(:Handoff)
```

A **Session** is one run of one agent. It's both the unit of episodic memory and the unit of *presence*. Live sessions heartbeat, and a janitor closes the ones that go quiet. The same node that later carries the memory ("this session produced this fix") is what makes live coordination work ("this session is touching `token-service` right now").

## The queries that do the work

**Recall, step 1: similar problems, with access control done in the graph.**
```cypher
CALL db.idx.vector.queryNodes('Task','embedding',$n,vecf32($emb)) YIELD node AS t, score
WITH t, 1 - score AS sim WHERE sim >= $min_sim
MATCH (s:Solution)-[:SOLVES]->(t)
MATCH (s)<-[:PRODUCED]-(:Session)<-[:RAN]-(a:Dev)-[:MEMBER_OF]->(at:Team)
MATCH (v:Dev {name:$viewer})-[:MEMBER_OF]->(vt:Team)
WHERE s.visibility = 'org' OR (s.visibility = 'team' AND at = vt) OR a = v
RETURN t.id, t.text, sim, s.id, s.status
```

**Recall, step 2: walk past stale fixes.**
```cypher
UNWIND $ids AS sid
MATCH (s0:Solution {id:sid})
OPTIONAL MATCH p = (newer:Solution)-[:SUPERSEDES*1..4]->(s0)
WITH s0, p ORDER BY length(p) DESC
WITH s0, collect(p)[0] AS longest
RETURN s0.id, CASE WHEN longest IS NULL THEN [s0.id] ELSE reverse([n IN nodes(longest) | n.id]) END AS chain
```
Then one more query attaches lessons, dead ends, the author, team, project, lineage and reuse count. Ranking is `similarity × status × effort × proven reuse`.

**Who breaks if this component changes, and who is live on it right now?**
```cypher
MATCH (c:Component {name:$c})
MATCH p = (dep:Component)-[:DEPENDS_ON*1..3]->(c)
WITH dep, p ORDER BY length(p)
WITH dep, collect(p)[0] AS p
RETURN dep.name, length(p) AS depth, [n IN nodes(p) | n.name] AS chain
```
...followed by live sessions that `TOUCHES` any of those components. (FalkorDB can't take a variable-length bound as a parameter, so the depth is validated in code and inlined.)

**Expertise authority:**
```cypher
CALL algo.pageRank('Dev','CREDITS') YIELD node, score
```
A `CREDITS` edge is written whenever someone successfully reuses your fix or your answer resolves their question.

Every API response carries a `trace` with the exact Cypher that produced it, and the UI has a **Show Cypher** panel. All ~45 queries are listed in [`docs/cypher.md`](https://github.com/ishikatyagi-star/mycelium/blob/master/docs/cypher.md), generated from real traces.

## Rules we held ourselves to
Borrowed from the WeMakeDevs guide on graph agents, and from what we saw strong entries do:
1. **The LLM never writes Cypher.** Agents call a fixed catalogue of parameterised tools.
2. **Names are resolved against the graph.** An agent can't invent a component, a person or a solution id.
3. **Models propose; code decides.** Every write passes a plain-code gate (lengths, kinds, visibility, references) and leaves a `Receipt`, whether it was accepted or rejected.
4. **Reads use `GRAPH.RO_QUERY`.** The read path can't mutate memory.
5. **"I don't know" is a valid answer.** An agent that doesn't know says so, and that answer is delivered but *not* stored as memory.

## Making it ambient: MCP + hooks
A memory system agents forget to use is useless, so Mycelium hooks into Claude Code's lifecycle:

- **`UserPromptSubmit`:** the first prompt registers a live session for the task. The best org memories and any overlapping live work are injected into context. Later prompts heartbeat and inject the **inbox**: questions routed to you, change notices for components you touch, overlaps and handoffs.
- **`PostToolUse`:** during long autonomous runs, the agent checks the inbox at most once a minute, so messages arrive mid-task.
- **`Stop`:** once per session, the agent is nudged to save what it learned, including dead ends.

One command connects any project:
```bash
scripts/install_claude.sh ~/code/mobile-app Ishika acme https://api-production-377ba.up.railway.app "Mobile 3.0"
```

## A company that's always busy
A demo of coordination needs agents to coordinate *with*, so a fleet of 10 simulated agents across 5 teams (Identity, Payments, Data, Mobile, Platform) runs around the clock against the same API that real Claude Code sessions use.
- They start tasks, reuse what the org knows, and ask the org when they're stuck.
- They announce changes, and save what they learn.
- When a question is routed to one of them, it answers from its own task context plus org memory, using an LLM (Groq, `gpt-oss-120b`), and says so when it doesn't know.

When Ishika's real Claude Code session asks *"is anyone rotating the token-service signing keys right now?"*, the graph routes it to Meera's live agent. The path is `Question → token-service ← TOUCHES ← Meera's session`. The answer lands back in Ishika's context through the hook.

## Results
We built a small benchmark ([`eval/results.md`](https://github.com/ishikatyagi-star/mycelium/blob/master/eval/results.md)). Both sides use the same embeddings and the same FalkorDB vector index. The only difference is whether the graph is used.

| Task | Vector-only | Mycelium |
|---|---|---|
| Stale-fix trap: top-1 is the current fix | 0/12 | **12/12** |
| Stale-fix trap: top-1 is a superseded/broken fix | 12/12 | **0/12** |
| Cross-team / cross-project recall @1 | 12/12 | 12/12 |
| Question routing @1 (who should answer *now*) | 4/8 | **8/8** |
| Change impact: precision / recall of warned live agents | see results.md | **1.0 / 1.0** |

- Hybrid recall runs at about 3 ms p50 locally.
- **50 concurrent agents** running the full loop (start session, recall, ask, save, report outcome, end) through the API: **0 errors**, about 210 ops/s on a single API worker.

**Please read the caveats.** We wrote the synthetic org and the cases, and thresholds were tuned on the same org. The stale-trap queries are *deliberately* phrased like the old fix, because that's the situation the test is about. Treat this as evidence of the *mechanism*, not a general accuracy claim. Plain recall ties at 12/12, which is the honest part: the graph doesn't make similarity search better at wording. It adds what similarity can't know.

## Mycelium remembers how Mycelium was built
We pointed our transcript importer at the Claude Code sessions in which we built Mycelium.
1. Secrets, emails, hosts and home paths were scrubbed.
2. An LLM proposed memories.
3. We curated them.
4. The write gate stored them in a second org, `mycelium`.

Ask it *"Railway deploy fails after moving the service to another region"* and you get the real fix: the free plan allows a single region, so remove the old one. It also tells you it **skipped** our first wrong guess ("upload fresh builds instead of redeploying"), because that memory is marked superseded and failed. That's the same story as Yash's token refresh, about ourselves, from tonight.

## Lessons learned
- **Presence and memory are the same node.** Modeling a session once, as both "who's live" and "what was learned", made coordination and memory one system instead of two.
- **Dead ends are the most valuable memory.** The "what didn't work" lessons save the most time, and they're exactly what never makes it into docs.
- **Ambient beats available.** Without hooks, agents rarely call memory tools on their own. With hooks, memory just shows up.
- **Co-locate the app and the database.** Our agent loop is chatty. We moved the API to the Railway region nearest FalkorDB Cloud (Singapore → Mumbai), and each query now takes about 56 ms.
- More FalkorDB-specific notes, with workarounds, are in [`docs/falkordb-notes.md`](https://github.com/ishikatyagi-star/mycelium/blob/master/docs/falkordb-notes.md).

## Honest limits
- The demo company is synthetic (Rule 6). Real orgs are messier.
- Identity is configuration (`MYC_DEV`), not authentication. Production would need SSO.
- Routing is a weighted heuristic tuned on our own org.
- Embeddings are small and local (bge-small) so setup costs nothing.
- We ran on FalkorDB 4.22 (Cloud free plus a pinned Docker image) and haven't tested the 6.0 engine yet.

## Stack
- FalkorDB Cloud (vector index, Cypher, `algo.pageRank`, `GRAPH.COPY`)
- Python, FastAPI, SSE
- MCP (Python SDK) plus Claude Code hooks
- fastembed (bge-small)
- Groq for fleet agents and transcript extraction
- Next.js on Vercel
- Railway

## AI disclosure
We built Mycelium with Claude Code. Ishika's session did the core, API, MCP, fleet and eval; Yash's session did the web app. We directed the product, made the calls, reviewed and tested everything, and can explain every query. Details are in [`docs/ai-disclosure.md`](https://github.com/ishikatyagi-star/mycelium/blob/master/docs/ai-disclosure.md).

## Try it
- **Live:** _TODO web URL_. Every visitor gets a private sandbox copy of the company.
- **Run it locally:** `docker compose up -d && uv sync && PYTHONPATH=. uv run python -m seed.acme && PYTHONPATH=. uv run uvicorn api.main:app`
- **Connect your own Claude Code:** `scripts/install_claude.sh <your project> <your name>`

*Built by Ishika Tyagi and Yash for Graph Hacks 2026.*
