# Demo video script: the tour *is* the story (~2:50, hard cap 3:00)

Record the whole video by pressing **Next** through the built-in tour. Each step highlights one part of the product and is one beat of the story: **Neha's AI agent is about to repeat a 3-day mistake, and Mycelium stops it.** Two steps play their animation by themselves (6 and 10), so you only ever click where the script says.

**Deadline: tonight, Oct 18, 11:59 PM IST.**

## Before you hit record (5 minutes)
- [ ] Open https://web-production-76872.up.railway.app in a **private/incognito window**. That gives fresh state: the tour button pulses and the Playground opens on Neha.
- [ ] Window at 1440×900 (or 1920×1080), zoom 100%, bookmarks bar hidden, notifications off.
- [ ] Glance at `/live`: the header should show about 10 **agents live**. Then go back to the Overview (`/`).
- [ ] Optional reset if the demo data looks messy (20 s, safe):
  ```bash
  set -a; . ./.env.cloud; set +a; PYTHONPATH=. uv run python -m seed.graphhq
  ```
- [ ] Navigate with **Next** or the **→** key. **Don't press Esc** (it closes the tour). Close the change dialog with its **×**.

## The script

| # | Time | On screen (tour step) | You do | You say |
|---|---|---|---|---|
| — | 0:00–0:08 | Overview headline | Nothing yet | "Every engineer now works with an AI agent. And every one of those agents starts each session knowing nothing about what the company already learned." |
| 1 | 0:08–0:18 | **The problem** | Click **Start the tour** | "So agents keep solving problems their company already solved, and they can't see what other agents are doing right now." |
| 2 | 0:18–0:30 | **Graph HQ, our demo company** | Next | "Meet Graph HQ: 14 engineers, five teams, 17 services, four months of agent history, all in one graph in FalkorDB. Let's follow Neha, on the Mobile team." |
| 3 | 0:30–0:40 | **Agents about to repeat work** | Next | "Right now, six agents here are about to solve something a teammate has already solved. Neha's is one of them." |
| 4 | 0:40–0:55 | **What the agent plans to do** (the chat) | Next | "Users are getting logged out. Her agent's plan: retry on 401. What it doesn't know is that ten weeks ago that exact fix caused an outage, and Yash on Payments spent three days and 14 attempts fixing it." |
| 5 | 0:55–1:10 | **Your choice** | Next, then click **Solve from scratch**; let two attempts play | "Without Mycelium, the agent walks straight into the same dead ends. That's the three days and 200,000 tokens Yash already spent, about to be spent again." |
| 6 | 1:10–1:35 | **How the memory is found** (plays by itself) | Next; wait for the green answer, then click **Implement this** | "With Mycelium, the agent asks the company first. It finds similar problems, skips the fix that broke, and brings back who solved it and what not to do. One click, and it implements Yash's fix, with credit." |
| 7 | 1:35–1:47 | **The company, live** | Next | "Now zoom out. Every dot is an AI agent working at Graph HQ at this moment, attached to the services it touches." |
| 8 | 1:47–2:05 | **Change something** | Next, click **Announce a change** → **Send to affected agents**; show the list, then **×** | "Meera is rotating the token-signing keys. Mycelium follows the dependencies and warns only the agents whose work depends on it: one, two, three hops away. Nobody else gets interrupted." |
| 9 | 2:05–2:15 | **Agents asking agents** (activity feed) | Next | "Agents ask each other too. A question goes to whoever is working on that service right now, and every answer becomes memory." |
| 10 | 2:15–2:32 | **Why it needs a graph** (plays by itself) | Next; let the animation run | "Why a graph? Vector search grabs the closest look-alike, which is the broken fix. The graph knows it was replaced, and walks to the fix that works." |
| 11 | 2:32–2:40 | **Who knows what** | Next | "Over time the company learns who really knows what, and which hard-won fixes only one person holds." |
| 12 | 2:40–2:52 | **Measured, not claimed** | Next; then **Finish** | "Measured: the right fix 12 times out of 12, versus zero for vector search. Any company can onboard with one API call. Mycelium: one memory for every AI agent, built on FalkorDB." |

## If something goes wrong
- **Step 6 is slow:** keep talking over the steps lighting up. If *Implement this* takes more than ~5 s, skip it; the green "already solved this" message makes the point.
- **The graph on step 7 looks crowded:** the tour card's area is fine to talk over, or click **Fit** after the step.
- **The activity feed (step 9) is quiet:** the fleet acts every ~15 s; just describe it, the earlier events are already listed.
- **You closed the tour by accident:** click **Start the tour** and press → until you're back at the step (they're fast).

## Optional extra shot (after the tour, ~20 s): it works in real tools
Claude Code in `~/Documents/Projects/mycelium-demo-mobile`, prompt: `Users get logged out randomly when several requests hit 401 at the same time. Fix api.ts.` Show the injected `[Mycelium] The org has solved similar problems before` context.
> "And it's the same inside Claude Code: an MCP server and hooks put the company's memory straight into the agent."

Only add it if the main video is under 2:40, so the total stays under 3:00.
