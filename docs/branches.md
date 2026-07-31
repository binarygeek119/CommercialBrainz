# Branching and environments

| Branch | Role | Site URL |
|--------|------|----------|
| **`google`** | Testing / integration. **Default for all PRs.** | **https://commercialbrainz.duckdns.org/** |
| **`cloudflare`** | Public production site | **https://commercialbrainz.org/** |

`main` is legacy; prefer `google` and `cloudflare`.

## Workflow

1. Open PRs against **`google`** (not `cloudflare`).
2. Merge into `google` → CI → auto-deploy to the GCE VM as the **DuckDNS testing site**.
3. When testing looks good, promote **`google` → `cloudflare`** → auto-deploy as **https://commercialbrainz.org/**.

On each deploy, `fix-gcloud-vm.sh` sets hostname / TLS from `APP_BRANCH`:

| `APP_BRANCH` | `DOMAIN` | TLS |
|--------------|----------|-----|
| `google` | `commercialbrainz.duckdns.org` | Let's Encrypt (`auto`) |
| `cloudflare` | `commercialbrainz.org` (+ `www` redirect; DuckDNS kept as alias) | Cloudflare Origin CA (`origin`) |

Both share the **same GCE VM**; deploys are serialized. For `cloudflare`, Origin CA files must already be in `/opt/commercialbrainz/data/caddy/certs/` (see [cloudflare-domain.md](cloudflare-domain.md)).

## Versioning (cloudflare / public)

Each merge into **`cloudflare`** runs [.github/workflows/bump-cloudflare-version.yml](../.github/workflows/bump-cloudflare-version.yml):

- Bumps from the latest `v*` tag (so merges from `google` cannot rewind the version)
- Updates `frontend/src/version.ts`, `frontend/package.json`, `backend/pyproject.toml`
- Creates tag `v1.0.0-alpha`, `v1.0.0-alpha.1`, `v1.0.0-alpha.2`, …

The UI badge shows `v{APP_VERSION}`. Testing (`google`) does not auto-bump.

## Promote testing → public

```bash
git fetch origin
git checkout cloudflare
git merge origin/google
git push origin cloudflare
```

Or open a GitHub PR from `google` into `cloudflare`.
