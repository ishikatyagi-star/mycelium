# Demo video script (target 2:45, hard cap 3:00)

Judges want to see it **working, not slides**, within the first 60 seconds. One story runs throughout: Neha's agent is about to repeat Yash's 3-day token-refresh bug.

**Deadline: tonight, Oct 18, 11:59 PM IST.** Record by about 19:30.

## Pre-flight (10 minutes before recording)
- [ ] `curl https://api-production-377ba.up.railway.app/api/health` returns `ok: true`.
- [ ] Open https://web-production-76872.up.railway.app/live and check that the header shows about 10 **agents live** (the fleet is running).
- [ ] Optional reset, if the demo data looks messy. It takes about 20 s and is safe:
  ```bash
  set -a; . ./.env.cloud; set +a; PYTHONPATH=. uv run python -m seed.graphhq
  ```
- [ ] Browser at 1440×900 (or 1920×1080), zoom 100%, bookmarks bar hidden, notifications off.
- [ ] Optional real-tool shot: Claude Code open in `~/Documents/Projects/mycelium-demo-mobile` (connected to Graph HQ), with `.mycelium/session.json` deleted for a fresh session. Terminal font 16pt+.

## Shots

**0:00–0:12 · Hook** *(Overview page `/`)*
- Show the headline, then the "3 days" card.
> "Every engineer now has an AI agent, and every agent starts blank. So agents keep solving problems the company already solved."

**0:12–0:55 · The fix nobody remembered** *(Playground → Neha, already selected)*
1. Scroll the chat. The agent's plan is "retry on 401".
   > "Neha's agent is about to retry on 401. Ten weeks ago that exact fix caused an outage, and Yash spent 3 days fixing it."
2. Click **Solve from scratch**. Let 2 attempts play while the token and time counters climb.
   > "Without Mycelium, it repeats the dead ends."
3. Pick Neha again (resets), then click **Ask Mycelium first**. Let the right panel play. Pause on the path strip: Neha's problem → similar task → **stale fix (struck out)** → current fix → Yash.
   > "With Mycelium, it checks the company's memory first. It finds the problem, skips the fix that broke, and brings back who solved it and what not to do."
4. Click **Implement this**.
   > "And it implements Yash's fix, with credit."

**0:55–1:20 · Why it needs a graph** *(Vector vs graph → first example chip)*
- Let the animation play to step 5.
> "Same question, same index. Vector search grabs the closest look-alike, which is the broken fix. The graph knows it was replaced, follows SUPERSEDES to the working one, and attaches the error and the dead ends."

**1:20–1:45 · It works in real tools** *(optional: Claude Code terminal; skip if not set up)*
- Prompt: `Users get logged out randomly when several requests hit 401 at the same time. Fix api.ts.`
- Show the injected `[Mycelium] The org has solved similar problems before` context, with Yash's fix and the dead ends.
> "Same thing inside Claude Code. An MCP server and hooks put the company's memory straight into the agent."
- **If you skip this shot,** spend the time on the Live org instead.

**1:45–2:15 · Agents coordinating, live** *(Live org `/live`)*
1. > "Every dot is an agent working right now."
2. Click **Announce a change** → `token-service` (prefilled) → **Send to affected agents**. Show the list: same service, 1 hop, 2 hops, 3 hops. Close; the red ripple shows on the graph.
   > "Change a service, and only the agents whose work depends on it are warned. The graph walks DEPENDS_ON."
3. Point at the Activity feed: agents asking each other, answers arriving.

**2:15–2:35 · Proof** *(Overview → "Measured, not claimed")*
> "12 out of 12 current fixes versus 0 for vector search. Questions reach the right person 8 out of 8 times. Fifty agents at once, zero errors."
- Optional: on any result, open **Show Cypher** for 2 seconds.

**2:35–2:45 · Close** *(Overview hero)*
> "Any company can onboard with one API call. Mycelium: one memory for every AI agent, built on FalkorDB."

## Backup lines (if something is slow live)
- If *Implement this* is slow, cut after the green "already solved this" message. It already makes the point.
- If the Live graph looks crowded, click **Fit**.
- If no agent activity shows in the feed, wait about 15 s (the fleet acts every ~15 s), or switch to **Threads** for earlier answered questions.
