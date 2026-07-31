# Branching and environments

| Branch | Role | Site URL | GCE VM |
|--------|------|----------|--------|
| **`google`** | Testing / integration. **Default for all PRs.** | **https://commercialbrainz.duckdns.org/** | `commercialbrainz-vm` |
| **`cloudflare`** | Public production site | **https://commercialbrainz.org/** | `commercialbrainz-org` |

`main` is legacy; prefer `google` and `cloudflare`.

## Workflow

1. Open PRs against **`google`** (not `cloudflare`).
2. Merge into `google` → CI → auto-deploy to **`commercialbrainz-vm`** (DuckDNS testing).
3. When testing looks good, promote **`google` → `cloudflare`** → auto-deploy to **`commercialbrainz-org`** (public).

On each deploy, `fix-gcloud-vm.sh` sets hostname / TLS from `APP_BRANCH`:

| `APP_BRANCH` | VM | `DOMAIN` | TLS |
|--------------|-----|----------|-----|
| `google` | `commercialbrainz-vm` | `commercialbrainz.duckdns.org` | Let's Encrypt (`auto`) |
| `cloudflare` | `commercialbrainz-org` | `commercialbrainz.org` (+ `www`) | Cloudflare Origin CA (`origin`) |

Create the public VM once:

- **GitHub Actions (recommended):** Actions → **Setup GCE VM** → target `cloudflare` → Run workflow  
  (uses the same Workload Identity as Deploy; prints the static IP in the job log)
- **Laptop:** [`scripts/setup-cloudflare-vm.sh`](../scripts/setup-cloudflare-vm.sh)

Then Cloudflare DNS + Origin CA via [`docs/cloudflare-domain.md`](cloudflare-domain.md).

**Cost note:** GCP Always Free includes only one e2-micro. The second VM (`commercialbrainz-org`) is billed (still low on e2-micro). Use a static IP on the public VM so Cloudflare A records stay stable.

## Versioning (cloudflare / public)

Format: **`major.minor.bug`** (e.g. `1.0.0`, `1.0.1`, `1.2.0`).

Each merge into **`cloudflare`** runs [.github/workflows/bump-cloudflare-version.yml](../.github/workflows/bump-cloudflare-version.yml):

- Bumps from the latest `v*` tag (merges from `google` cannot rewind the version)
- Default bump is **bug** (+1 on the last number)
- Updates `frontend/src/version.ts`, `frontend/package.json`, `backend/pyproject.toml`
- Creates tag `v1.0.1`, `v1.0.2`, …

Manual / larger bumps: Actions → **Bump cloudflare version** → choose `bug`, `minor`, or `major`.

The UI badge shows `v{APP_VERSION}`. Testing (`google`) does not auto-bump.

## Promote testing → public

```bash
git fetch origin
git checkout cloudflare
git merge origin/google
git push origin cloudflare
```

Or open a GitHub PR from `google` into `cloudflare`.
