# Demo video script (target 2:50, hard cap 3:00)

Judges should see it **working within the first 60 seconds**. One story runs throughout: the token-refresh bug, past and present.

## Pre-flight (15 min before recording)
- [ ] `curl https://api-production-377ba.up.railway.app/api/health` returns `ok: true`, and the orgs list includes `acme` and `mycelium`.
- [ ] The fleet is running: `railway logs --service fleet` shows recent `started` / `answered` lines. The live org shows about 8–10 live agents.
- [ ] **Ishika's terminal:** Claude Code open in `~/Documents/Projects/mycelium-demo-mobile` (connected as Ishika, Mobile team). Fresh session, so `.mycelium/session.json` is deleted.
- [ ] **Yash's terminal:** Claude Code in any project, connected as Yash (Payments) via `scripts/install_claude.sh ... Yash acme <api> "Realtime Ledger"` with the write token.
- [ ] The web app (https://web-production-76872.up.railway.app) is open on the **Live org** view at 1440px, with dark mode and notifications off. Click **Fit** if the graph isn't centered.
- [ ] Reset the demo state if needed. Reseeding is safe and takes 20 s:
  ```bash
  set -a; . ./.env.cloud; set +a; PYTHONPATH=. uv run python -m seed.acme
  ```
- [ ] Record at 1440×900 or 1920×1080. Zoom the terminal font to 16pt+.

## Shots

**0:00–0:15 · Hook** *(web: Live org view, agents pulsing)*
> "This is a company: 5 teams, 17 services, and every dot is an AI agent working right now. Each one used to be an island. They forget what the company already learned, and they can't see each other. Mycelium connects them through one graph in FalkorDB."

**0:15–0:55 · Across time: the fix nobody remembered** *(Ishika's Claude Code)*
- Prompt: `Users get logged out randomly when several requests hit 401 at the same time. Fix api.ts.`
- Show the injected context, `[Mycelium] The org has solved similar problems before`, with Yash's single-flight fix: **3 working days, 14 attempts**, the skipped stale fix, the dead ends, and ~168k tokens saved.
- Claude applies the fix and credits Yash.
> "Six weeks ago, on another team, in another project, Yash spent three days on this exact bug. Mycelium hands Ishika's agent his fix, credited, along with the dead ends he hit, so they don't get repeated."

**0:55–1:20 · Graph beats vector** *(web: Compare view, preset query)*
- Query: `access token expired returns 401, refresh it and retry the request`
- Left column (vector only): the **superseded** "retry once" fix in red. Right column (Mycelium): the real fix, with "skipped: failed with 429 refresh storm".
> "Plain vector search returns the fix that caused the outage. The graph knows it was superseded, so it walks past it and warns you."

**1:20–1:55 · Across the org: agents talking to agents** *(split: Ishika's Claude Code + web Live org)*
- Prompt in Ishika's Claude Code: `Ask the org whether anyone is rotating the token-service signing keys right now. Our app caches the JWKS.`
- Web: a particle travels from Ishika to **Meera's live agent**. Then show the reason ("live on token-service right now") and the path.
- Within about 30–60 s, Meera's agent answers. Show it in the Threads view, then in Ishika's next prompt context (`[Mycelium] Inbox: ANSWER ...`).
> "Nobody had written this down yet. The graph found the agent working on token-service at this moment, and the answer is now memory for everyone."

**1:55–2:15 · Change propagation** *(web: notice composer, or Yash's Claude Code)*
- Yash (Payments): `Announce a change: the ledger balance API now returns integer minor units.`
- Ripple across `DEPENDS_ON`: Rohan's refunds agent (depth 1) and Tom's mobile agent (depth 2, via checkout-api) are warned. Kabir and Meera are not.
> "Only the agents whose work actually depends on the ledger hear about it. That's the graph walking DEPENDS_ON, not keyword matching."

**2:15–2:35 · Company brain + proof** *(web: Brain view → Show Cypher → results table)*
- Who knows Kafka (PageRank), knowledge at risk, tokens saved per team.
- Flash the Show Cypher panel, then the benchmark table (12/12 vs 0/12, 8/8 vs 4/8, change impact 1.0/1.0) and "50 concurrent agents, 0 errors".

**2:35–2:50 · Close** *(web: org switcher → `mycelium` org)*
> "We even imported our own Claude Code sessions from building this. Mycelium remembers how Mycelium was built, including the wrong guess we made at 4 AM and the fix that replaced it. FalkorDB Cloud, an MCP server, Claude Code hooks. Mycelium."

## Backup lines (if something is slow live)
- If Meera's answer is slow, cut to the Threads view, where earlier answered threads exist (seeded Q&A plus the fleet).
- If Claude Code doesn't call tools, the injected `[Mycelium]` context from the hook is the proof. Show that.
