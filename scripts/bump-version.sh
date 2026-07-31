#!/usr/bin/env bash
# Bump CommercialBrainz public (cloudflare) app version.
#
# Scheme: major.minor.bug  ("bug" is the patch number)
# Prefers the latest git tag (v…) so merges from testing cannot rewind the
# version. Writes frontend/src/version.ts, frontend/package.json, and
# backend/pyproject.toml.
#
# Usage:
#   ./scripts/bump-version.sh              # bump bug (default)
#   ./scripts/bump-version.sh minor
#   ./scripts/bump-version.sh major
#   ./scripts/bump-version.sh bug --dry-run
#   BUMP=minor ./scripts/bump-version.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DRY_RUN=0
BUMP="${BUMP:-bug}"

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    major|minor|bug|patch) BUMP="$arg" ;;
    *)
      echo "ERROR: unknown argument: $arg (use major|minor|bug)" >&2
      exit 1
      ;;
  esac
done

if [[ "$BUMP" == "patch" ]]; then
  BUMP="bug"
fi

latest_tag="$(git tag -l 'v*' --sort=-v:refname | head -1 || true)"
if [[ -z "$latest_tag" ]]; then
  if [[ -f frontend/src/version.ts ]]; then
    latest_tag="$(grep -E "APP_VERSION\s*=" frontend/src/version.ts | head -1 | sed -E 's/.*"([^"]+)".*/\1/')"
  fi
  latest_tag="${latest_tag:-0.0.0}"
fi

current="${latest_tag#v}"
if [[ ! "$current" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+) ]]; then
  echo "ERROR: unsupported version format: $current (want major.minor.bug)" >&2
  exit 1
fi

major="${BASH_REMATCH[1]}"
minor="${BASH_REMATCH[2]}"
bug="${BASH_REMATCH[3]}"
base="${major}.${minor}.${bug}"

case "$BUMP" in
  major)
    major=$((major + 1))
    minor=0
    bug=0
    ;;
  minor)
    minor=$((minor + 1))
    bug=0
    ;;
  bug)
    bug=$((bug + 1))
    ;;
  *)
    echo "ERROR: BUMP must be major, minor, or bug (got: $BUMP)" >&2
    exit 1
    ;;
esac

next="${major}.${minor}.${bug}"
echo "current=${current} (tag ${latest_tag}, base ${base})"
echo "bump=${BUMP}"
echo "next=${next}"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "NEXT_VERSION=${next}"
  echo "NEXT_TAG=v${next}"
  exit 0
fi

cat > frontend/src/version.ts <<EOF
export const APP_VERSION = "${next}";
EOF

python3 - <<PY
import json
from pathlib import Path
path = Path("frontend/package.json")
data = json.loads(path.read_text())
data["version"] = "${next}"
path.write_text(json.dumps(data, indent=2) + "\n")
PY

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
