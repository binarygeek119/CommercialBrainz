# Branching and environments

| Branch | Role | Public URL (typical) |
|--------|------|----------------------|
| **`google`** | Testing / integration. **Default for all PRs.** | `https://commercialbrainz.duckdns.org` |
| **`cloudflare`** | Public production site | `https://commercialbrainz.org` |

`main` is legacy; prefer `google` and `cloudflare`.

## Workflow

1. Open PRs against **`google`** (not `cloudflare`).
2. CI runs on the PR; merge into `google` → images tagged `google` + commit SHA → auto-deploy to the GCE VM (testing).
3. When testing looks good, open a PR **`google` → `cloudflare`** (or merge locally) → images tagged `cloudflare` + `latest` → auto-deploy production config.

Both environments currently share the **same GCE VM**. Deploys are serialized; the VM checks out the branch being deployed (`APP_BRANCH`) and pulls matching GHCR tags. Production should use Cloudflare Origin CA (`CADDY_TLS_MODE=origin`); testing can stay on DuckDNS + Let's Encrypt (`CADDY_TLS_MODE=auto`).

## Promote testing → public

```bash
git fetch origin
git checkout cloudflare
git merge origin/google
git push origin cloudflare
```

Or open a GitHub PR from `google` into `cloudflare`.
