# WeMakeDevs submission: copy-paste text

Paste each block into the matching field. Some forms use different labels, so the nearest match is fine. All links below are filled in.

---

### Project name
Mycelium

### Tagline (one line)
One shared memory for every AI agent in a company, so a problem solved once is never solved twice.

### Tracks
- Track 02: Agent Memory and Coordination (primary)
- Track 03: Company Brain

### Links
- **Repository (public):** https://github.com/ishikatyagi-star/mycelium
- **Live demo:** https://web-production-76872.up.railway.app
- **Live API (interactive docs):** https://api-production-377ba.up.railway.app/docs
- **Demo video:** https://youtu.be/BLPcN9v1BeE
- **Blog post:** https://dev.to/ishikatyagistar/mycelium-your-agents-keep-re-solving-last-quarters-bugs-we-gave-the-whole-company-one-graph-4fdg

### Short description (2–3 sentences)
Every engineer now works with an AI agent, and every agent starts each session blank. It can't see what the company already solved, or what other agents are changing right now. Mycelium connects all of them through one graph in FalkorDB: agents recall past fixes (skipping ones that later broke), get warned about changes that affect them, and route questions to whoever knows right now.

### Full description
**The problem.** Companies now run dozens of AI agents, one per engineer, and each is an island.
- Across time, history repeats. Ten weeks ago, Yash spent three days and 14 attempts fixing a token-refresh bug. Today Neha's agent is about to apply the exact fix that caused that outage.
- Across teams, nobody sees anybody. One agent changes a service while three others depend on it, and none of them know.

**What Mycelium does.**
- **Recall:** before solving, an agent asks the company's memory. A vector search finds similar past problems, then the graph walks past fixes that were later replaced, attaches the dead ends, ranks hard-won fixes first, and credits the author.
- **Coordination:** every agent session is a live node. Change a service, and Mycelium follows DEPENDS_ON to warn only the agents whose work depends on it. Ask a question, and it's routed to whoever is working on that service right now. Answers become memory.
- **Company brain:** who really knows what (PageRank over who credits whom), and which hard-won fixes only one person holds.

**It works in real tools.** An MCP server (13 tools) and Claude Code hooks put the company's memory straight into the agent. Any company can onboard with one API call (`POST /api/orgs`).

**Measured:**
- The current fix comes back 12/12 times, vs 0/12 for vector-only search.
- Questions reach the right person 8/8 times, vs 4/8.
- Change warnings have 1.0 precision and recall.
- 50 concurrent agents ran with 0 errors.

The demo company, Graph HQ, is synthetic.

### How FalkorDB is used (why the graph is essential)
FalkorDB is the only data store. Remove it and every endpoint returns 503; there is no cache or fallback.
- **One graph per company** (`org_<slug>`): teams OWN services, services DEPEND_ON services, devs RUN agent sessions that TOUCH services, sessions PRODUCE solutions that SOLVE tasks, and solutions SUPERSEDE or BUILD_ON each other.
- **Native vector index** on Task embeddings finds similar problems. The same Cypher query then continues into the graph (visibility, authorship).
- **Variable-length traversals:** `SUPERSEDES*1..4` skips stale fixes; `DEPENDS_ON*1..3` finds the live agents a change affects.
- **`algo.pageRank`** over CREDITS edges ranks real expertise.
- **`GRAPH.COPY`** gives every visitor a private sandbox copy of the demo company.
- **Reads use GRAPH.RO_QUERY.** All queries are parameterised, and the LLM never writes Cypher. Agents call a fixed set of tools, each running a query we wrote.

The graph model is in the README, and all 45 queries are documented in `docs/cypher.md`.

### Tech stack
FalkorDB Cloud · Python · FastAPI (REST + SSE) · MCP server + Claude Code hooks · fastembed (bge-small, local embeddings) · LLM via Groq (`gpt-oss-120b`) · Next.js 16 · deployed on Railway

### Local setup (if asked)
```
git clone https://github.com/ishikatyagi-star/mycelium && cd mycelium
docker compose up -d && uv sync
PYTHONPATH=. uv run python -m seed.graphhq
PYTHONPATH=. uv run uvicorn api.main:app --port 8000
```
Full instructions are in the README.

### AI disclosure
We built Mycelium with Claude Code (Claude Opus), which wrote most of the code: the graph core, API, MCP server, hooks, fleet simulator, benchmark and web app. We directed the product, made the design and scope decisions, reviewed and tested every milestone, and can explain the graph model and every query. Inside the product, an LLM (Groq, `gpt-oss-120b`) powers the simulated agents' answers, transcript extraction and the playground's "Implement this". Every LLM call has a deterministic fallback, and plain code decides what gets stored. The UI design system came from the open-source UI/UX Pro Max skill. Full details: `docs/ai-disclosure.md` in the repo.

### Team
Ishika Tyagi, Yash

### Challenges (if asked)
- **FalkorDB Cloud's free tier blocks Redis pub/sub.** We moved live events to an in-process bus in the API.
- **FalkorDB doesn't accept a variable-length path bound as a parameter.** We validate the depth in code, then inline it.
- **Co-locating the API with the database region** brought each query to about 56 ms.

We wrote these up for the FalkorDB team in `docs/falkordb-notes.md`.

### What's next (if asked)
- Real identity (SSO) and per-org access keys.
- More agent clients beyond Claude Code.
- Running our test suite on the FalkorDB 6.0 engine.
- Importing real chat and ticket history.
