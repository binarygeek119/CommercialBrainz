#!/usr/bin/env bash
# Bump CommercialBrainz public (cloudflare) app version.
#
# Prefers the latest git tag (v…) so merges from google cannot rewind the
# version. Writes frontend/src/version.ts, frontend/package.json, and
# backend/pyproject.toml.
#
# Usage:
#   ./scripts/bump-version.sh           # print + write next version
#   ./scripts/bump-version.sh --dry-run # print only
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

# Latest annotated/lightweight tag that looks like a semver (optional v prefix).
latest_tag="$(git tag -l 'v*' --sort=-v:refname | head -1 || true)"
if [[ -z "$latest_tag" ]]; then
  # Fall back to APP_VERSION in the tree.
  if [[ -f frontend/src/version.ts ]]; then
    latest_tag="$(grep -E "APP_VERSION\s*=" frontend/src/version.ts | head -1 | sed -E 's/.*"([^"]+)".*/\1/')"
  fi
  latest_tag="${latest_tag:-0.0.0}"
fi

current="${latest_tag#v}"

bump_prerelease() {
  local ver="$1"
  if [[ "$ver" =~ ^([0-9]+\.[0-9]+\.[0-9]+)-([A-Za-z0-9]+)(\.([0-9]+))?$ ]]; then
    local base="${BASH_REMATCH[1]}"
    local pre="${BASH_REMATCH[2]}"
    local num="${BASH_REMATCH[4]:-}"
    if [[ -z "$num" ]]; then
      echo "${base}-${pre}.1"
    else
      echo "${base}-${pre}.$((num + 1))"
    fi
    return 0
  fi
  if [[ "$ver" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
    echo "${BASH_REMATCH[1]}.${BASH_REMATCH[2]}.$((BASH_REMATCH[3] + 1))"
    return 0
  fi
  echo "ERROR: unsupported version format: $ver" >&2
  return 1
}

next="$(bump_prerelease "$current")"
echo "current=${current} (from tag/ref ${latest_tag:-none})"
echo "next=${next}"

if [[ "$DRY_RUN" -eq 1 ]]; then
  exit 0
fi

# frontend/src/version.ts
cat > frontend/src/version.ts <<EOF
export const APP_VERSION = "${next}";
EOF

# frontend/package.json
python3 - <<PY
import json
from pathlib import Path
path = Path("frontend/package.json")
data = json.loads(path.read_text())
data["version"] = "${next}"
path.write_text(json.dumps(data, indent=2) + "\n")
PY

# backend/pyproject.toml — replace only the [project] version line
python3 - <<PY
from pathlib import Path
path = Path("backend/pyproject.toml")
text = path.read_text()
lines = text.splitlines(keepends=True)
out = []
in_project = False
replaced = False
for line in lines:
    if line.strip() == "[project]":
        in_project = True
    elif line.startswith("[") and in_project:
        in_project = False
    if in_project and line.startswith("version =") and not replaced:
        out.append('version = "${next}"\n')
        replaced = True
        continue
    out.append(line)
if not replaced:
    raise SystemExit("could not find [project] version in pyproject.toml")
path.write_text("".join(out))
PY

echo "Wrote version ${next} to version.ts, package.json, pyproject.toml"
echo "NEXT_VERSION=${next}"
echo "NEXT_TAG=v${next}"
