# Branching and environments

| Branch | Role | Site URL | GCP project | GCE VM |
|--------|------|----------|-------------|--------|
| **`testing`** | Testing / integration. **Default for all PRs.** | **https://commercialbrainz.duckdns.org/** | `commercialbrainz` | `commercialbrainz-vm` |
| **`public`** | Public production site | **https://commercialbrainz.org/** | **`commercialbrainz-public`** | `commercialbrainz-public` |

`main`, `google`, and `cloudflare` are legacy aliases; prefer `testing` and `public`.

## Workflow

1. Open PRs against **`testing`** (not `public`).
2. Merge into `testing` → CI → auto-deploy to **`commercialbrainz-vm`** (DuckDNS testing).
3. When testing looks good, promote **`testing` → `public`** → auto-deploy to **`commercialbrainz-public`** (public).

On each deploy, `fix-gcloud-vm.sh` sets hostname / TLS from `APP_BRANCH`:

| `APP_BRANCH` | VM | `DOMAIN` | TLS |
|--------------|-----|----------|-----|
| `testing` | `commercialbrainz-vm` | `commercialbrainz.duckdns.org` | Let's Encrypt (`auto`) |
| `public` | `commercialbrainz-public` | `commercialbrainz.org` (+ `www`) | Cloudflare Origin CA (`origin`) |

Create the public **GCP project** once, then the VM:

- **Project + WIF:** [`scripts/setup-public-gcp-project.sh`](../scripts/setup-public-gcp-project.sh) — see [`docs/public-gcp-project.md`](public-gcp-project.md)
- **VM via Actions:** Actions → **Setup GCE VM** → target `public` (needs `GCP_*_PUBLIC` or legacy `GCP_*_CLOUDFLARE` repo variables)
- **VM via laptop:** `GCP_PROJECT_ID=commercialbrainz-public ./scripts/setup-cloudflare-vm.sh`

Then Cloudflare DNS + Origin CA via [`docs/cloudflare-domain.md`](cloudflare-domain.md).

**Cost note:** GCP Always Free includes only one e2-micro. The public project’s e2-micro + static IP are billed.

## Versioning (public)

Format: **`major.minor.bug`** (e.g. `1.0.0`, `1.0.1`, `1.2.0`).

Each merge into **`public`** runs [.github/workflows/bump-public-version.yml](../.github/workflows/bump-public-version.yml):

- Bumps from the latest `v*` tag (merges from `testing` cannot rewind the version)
- Default bump is **bug** (+1 on the last number)
- Updates `frontend/src/version.ts`, `frontend/package.json`, `backend/pyproject.toml`
- Creates tag `v1.0.1`, `v1.0.2`, …

Manual / larger bumps: Actions → **Bump public version** → choose `bug`, `minor`, or `major`.

The UI badge shows `v{APP_VERSION}`. Testing (`testing`) does not auto-bump.

## Promote testing → public

```bash
git fetch origin
git checkout public
git merge origin/testing
git push origin public
```

Or open a GitHub PR from `testing` into `public`.
