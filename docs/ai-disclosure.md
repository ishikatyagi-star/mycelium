# AI assistance disclosure

Graph Hacks rules require disclosing AI coding assistance. I used it heavily, and here is exactly how.

## Tools used
- **Claude Code (Claude Opus)** wrote most of the code for `core/`, `api/`, `mcp_server/`, `hooks/`, `fleet/`, `seed/`, `eval/`, `tests/`, `web/` and the docs, working in Ishika's session.
- **An LLM via Groq (`openai/gpt-oss-120b`)** runs *inside the product*. It does four jobs:
  - It answers questions as simulated fleet agents.
  - It drafts memory entries for fleet agents.
  - It extracts reusable knowledge from imported transcripts.
  - It writes the *Implement this* answer in the web playground.

  Every one of these calls has a deterministic fallback. The LLM proposes; the write gate (plain code) decides what is stored.
- **UI/UX Pro Max** (an open-source Claude skill) generated the design system the web app follows: style, palette, type scale and accessibility checklist.

## What I did (Ishika Tyagi, solo)
- **Problem framing and product direction:**
  - Memory across time *and* live coordination across teams.
  - Agents talking to other users' agents.
  - Hard-won knowledge ranking higher.
- **Judgment calls:**
  - Track choice.
  - Scope ("no cuts for the time crunch").
  - Naming.
  - Deployment.
  - What the demo must prove.
- **Review and verification:** I read the graph model and the queries, and ran the tests and benchmark. Every milestone was walked through and explained before moving on.
- **The demo video, blog and submission.**

## What I can explain without the AI
- The graph model (`docs/graph-model.md`) and why each relationship exists.
- Every query (`docs/cypher.md`).
- Why recall is vector plus graph, and what the graph adds:
  - SUPERSEDES walking
  - visibility
  - effort ranking
  - credit
- How routing scores candidates.
- Why change impact uses `DEPENDS_ON*1..3` with an inlined, validated depth.
- What the benchmark does and doesn't show.

## Development history
The Claude Code session transcripts from building Mycelium were imported into Mycelium itself (`core/importer.py`, with secrets and PII scrubbed). The project's own build history is part of its memory.
