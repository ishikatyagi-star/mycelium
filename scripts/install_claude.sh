#!/usr/bin/env bash
# Connect a project's Claude Code (CLI or desktop app) to Mycelium: MCP tools (.mcp.json) + ambient hooks.
# usage: scripts/install_claude.sh <project_dir> <dev_name> [org=graphhq] [api=http://localhost:8000] [project_name]
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$(cd "${1:?project dir}" && pwd)"; DEV="${2:?dev name}"; ORG="${3:-graphhq}"; API="${4:-http://localhost:8000}"; PROJ="${5:-}"
UV="$(command -v uv)"
python3 - "$REPO" "$TARGET" "$DEV" "$ORG" "$API" "$PROJ" "$UV" "${MYC_WRITE_TOKEN:-}" <<'PY'
import json, os, shlex, sys
repo, target, dev, org, api, proj, uv, token = sys.argv[1:]
env = {"MYC_DEV": dev, "MYC_ORG": org, "MYC_API": api, "MYC_PROJECT": proj, "MYC_WRITE_TOKEN": token}
# 1) MCP server (project scope)
p = os.path.join(target, ".mcp.json")
cfg = json.load(open(p)) if os.path.exists(p) else {}
cfg.setdefault("mcpServers", {})["mycelium"] = {
    "command": uv, "args": ["run", "--project", repo, "python", f"{repo}/mcp_server/server.py"], "env": env}
json.dump(cfg, open(p, "w"), indent=2)
# 2) hooks (local settings, not committed)
os.makedirs(os.path.join(target, ".claude"), exist_ok=True)
p = os.path.join(target, ".claude", "settings.local.json")
s = json.load(open(p)) if os.path.exists(p) else {}
envs = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
base = f"cd {shlex.quote(target)} && {envs} {shlex.quote(uv)} run --project {shlex.quote(repo)} python {shlex.quote(repo + '/hooks/mycelium_hook.py')}"
def h(arg, matcher=None):
    e = {"hooks": [{"type": "command", "command": f"{base} {arg}", "timeout": 20}]}
    if matcher is not None:
        e["matcher"] = matcher
    return [e]
s.setdefault("hooks", {}).update({"SessionStart": h("session-start"), "UserPromptSubmit": h("prompt"),
                                  "PostToolUse": h("post-tool", "*"), "Stop": h("stop"), "SessionEnd": h("session-end")})
s.setdefault("enabledMcpjsonServers", [])
if "mycelium" not in s["enabledMcpjsonServers"]:
    s["enabledMcpjsonServers"].append("mycelium")
json.dump(s, open(p, "w"), indent=2)
print(f"Mycelium connected for {dev} in {target} (org={org}, api={api})")
PY
grep -qs "^.mycelium/" "$TARGET/.gitignore" || echo ".mycelium/" >> "$TARGET/.gitignore"
