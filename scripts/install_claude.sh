#!/usr/bin/env bash
# Connect a project's Claude Code to Mycelium (MCP tools + ambient hooks).
# usage: scripts/install_claude.sh <project_dir> <dev_name> [org=acme] [api=http://localhost:8000] [project_name]
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$(cd "${1:?project dir}" && pwd)"; DEV="${2:?dev name}"; ORG="${3:-acme}"; API="${4:-http://localhost:8000}"; PROJ="${5:-}"
ENVV="MYC_DEV=$DEV MYC_ORG=$ORG MYC_API=$API MYC_PROJECT='$PROJ' MYC_WRITE_TOKEN=${MYC_WRITE_TOKEN:-}"
cd "$TARGET"
claude mcp add mycelium --scope local \
  -e MYC_DEV="$DEV" -e MYC_ORG="$ORG" -e MYC_API="$API" -e MYC_PROJECT="$PROJ" -e MYC_WRITE_TOKEN="${MYC_WRITE_TOKEN:-}" \
  -- uv run --project "$REPO" python "$REPO/mcp_server/server.py"
mkdir -p .claude
HOOK="cd \"$TARGET\" && $ENVV uv run --project \"$REPO\" python \"$REPO/hooks/mycelium_hook.py\""
python3 - "$HOOK" <<'PY'
import json, os, sys
hook = sys.argv[1]
p = ".claude/settings.local.json"
cfg = json.load(open(p)) if os.path.exists(p) else {}
def h(arg, matcher=None):
    e = {"hooks": [{"type": "command", "command": f"{hook} {arg}", "timeout": 20}]}
    if matcher is not None: e["matcher"] = matcher
    return [e]
cfg.setdefault("hooks", {}).update({
    "SessionStart": h("session-start"), "UserPromptSubmit": h("prompt"),
    "PostToolUse": h("post-tool", "*"), "Stop": h("stop"), "SessionEnd": h("session-end")})
json.dump(cfg, open(p, "w"), indent=2)
print("hooks written to", os.path.abspath(p))
PY
echo "Mycelium connected for $DEV in $TARGET (org=$ORG, api=$API)"
