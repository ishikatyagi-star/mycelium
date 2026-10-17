# Mycelium 🍄

**One shared context graph for every AI agent in a company, on [FalkorDB](https://falkordb.com).**

Engineering history repeats itself, and your agents don't remember it. Someone spends three days cracking a
token-refresh race. Months later another team's agent hits the same bug and starts from zero, because the
human forgot, the docs were never updated, and every agent session starts blank. Meanwhile, right now, an
agent on another team is changing the API yours depends on, and nobody tells your agent.

Mycelium connects them. Agents recall what anyone solved before, see what other teams are working on right
now, and talk to each other's agents. Knowledge compounds across time and flows across teams.

> Built for **Graph Hacks: Context for AI Agents** (WeMakeDevs × FalkorDB), Track 2 (Agent Memory &
> Coordination) and Track 3 (Company Brain). 🚧 This README is being filled in during the hackathon.

## Quick start (local)
```bash
docker compose up -d                       # FalkorDB (pinned v4.22.1) + Browser on :3000
uv sync
PYTHONPATH=. uv run python -m seed.acme    # synthetic org "acme"
PYTHONPATH=. uv run uvicorn api.main:app --port 8000
```
Connect a project's Claude Code to the org (MCP tools + ambient hooks):
```bash
scripts/install_claude.sh /path/to/your/project Ishika acme http://localhost:8000 "Mobile 3.0"
```

Docs: [API contract](docs/api-contract.md) · [web brief](docs/web-brief.md)
