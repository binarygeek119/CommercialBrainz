# Custom domain on Cloudflare Free — public VM

Serve **https://commercialbrainz.org** with:

- Cloudflare **Free** (edge HTTPS, CDN, DDoS)
- Dedicated GCE VM **`commercialbrainz-public`** as origin (GCP project **`commercialbrainz-public`**)
- **Cloudflare Origin CA** cert on Caddy (also free)

Testing stays on project **`commercialbrainz`** / VM **`commercialbrainz-vm`** + DuckDNS.  
New public project: [public-gcp-project.md](public-gcp-project.md). See [branches.md](branches.md).

## Cost

| Item | Cost |
|------|------|
| Cloudflare Free | $0 |
| Cloudflare Origin CA | $0 |
| Domain `commercialbrainz.org` | whatever you paid |
| Testing VM `commercialbrainz-vm` (e2-micro free tier) | $0 in free-tier regions |
| Public VM `commercialbrainz-public` (second e2-micro) | **billed** (Always Free = one e2-micro only) |
| Static IP on public VM | small monthly charge (recommended) |

## Architecture

```
Browser --HTTPS--> Cloudflare (Free SSL) --HTTPS--> Caddy on commercialbrainz-public (Origin CA) --> api/web
```

SSL/TLS mode on Cloudflare: **Full (strict)**.  
DNS: **Proxied** (orange cloud) — Cloudflare terminates visitor SSL.

## Steps

### 0. Public GCP project (once)

Create project **`commercialbrainz-public`**, WIF, and deploy SA:

```bash
./scripts/setup-public-gcp-project.sh
```

Then set GitHub variables `GCP_*_CLOUDFLARE` from the script output ([public-gcp-project.md](public-gcp-project.md)).

### 1. Create the public VM (once)

**Option A — GitHub Actions (no local gcloud):**

1. Repo → **Actions** → **Setup GCE VM** → **Run workflow**
2. Target: **`cloudflare`**
3. Optional secrets (Settings → Secrets): `VM_ADMIN_EMAIL`, `VM_ADMIN_USERNAME`, `VM_ADMIN_PASSWORD`, `ACME_EMAIL`
4. When the job finishes, copy the printed **External IP** from the log

**Option B — laptop** (`gcloud` authenticated, billing on public project):

```bash
GCP_PROJECT_ID=commercialbrainz-public \
ACME_EMAIL=you@example.com \
ADMIN_EMAIL=you@example.com \
ADMIN_USERNAME=admin \
ADMIN_PASSWORD='…' \
  ./scripts/setup-cloudflare-vm.sh
```

This wraps `setup-gcloud-vm.sh` with:

- `VM_NAME=commercialbrainz-public`
- `REPO_BRANCH=cloudflare`
- `CREATE_STATIC_IP=1`
- DuckDNS **unset** (testing VM keeps DuckDNS)

Note the printed **External IP** (static). Wait until startup finishes (~10–20 min):

```bash
gcloud compute ssh commercialbrainz-public --zone=ZONE \
  --command='sudo tail -f /var/log/commercialbrainz-startup.log'
```

The Actions workflow already grants `github-deploy` OS Login on the new instance. From a laptop, do it once:

```bash
PROJECT_ID=commercialbrainz-public
ZONE=us-central1-a   # whatever zone the VM landed in

gcloud compute instances add-iam-policy-binding commercialbrainz-public \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --member="serviceAccount:github-deploy@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/compute.osAdminLogin"
```

### 2. Cloudflare dashboard

1. [Add a site](https://dash.cloudflare.com) → `commercialbrainz.org` → **Free**.
2. At your registrar, set the two Cloudflare nameservers shown.
3. DNS → A records (**Proxied / orange**):

   | Type | Name | Content | Proxy |
   |------|------|---------|-------|
   | A | `@` | **commercialbrainz-public** external IP | Proxied |
   | A | `www` | same IP | Proxied |

   ```bash
   gcloud compute instances describe commercialbrainz-public \
     --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
   ```

   Do **not** point these at `commercialbrainz-vm`.

4. **SSL/TLS → Overview** → **Full (strict)**.
5. **SSL/TLS → Origin Server → Create Certificate**:
   - Hostnames: `commercialbrainz.org` and `*.commercialbrainz.org`
   - Validity: 15 years is fine
   - Save **Origin Certificate** and **Private Key** on your laptop, e.g.:
     - `~/cb-origin.crt`
     - `~/cb-origin.key`  
     (never commit the key)

6. (Optional) SSL/TLS → **Always Use HTTPS** = On.

### 3. Install Origin CA on the public VM

```bash
GCP_PROJECT_ID=your-project \
DOMAIN=commercialbrainz.org \
ACME_EMAIL=you@example.com \
ORIGIN_CERT=$HOME/cb-origin.crt \
ORIGIN_KEY=$HOME/cb-origin.key \
VM_NAME=commercialbrainz-public \
  ./scripts/setup-cloudflare-domain.sh
```

Defaults: `VM_NAME=commercialbrainz-public`, `KEEP_DUCKDNS=0` (DuckDNS stays on the testing VM only).

This uploads Origin CA files, sets `.env` (`DOMAIN`, CORS, public URLs, `CADDY_TLS_MODE=origin`), regenerates Caddy, and probes `https://commercialbrainz.org/health`.

### 4. App env (what the script sets)

On **`commercialbrainz-public`** `/opt/commercialbrainz/.env`:

```env
DOMAIN=commercialbrainz.org
DOMAIN_ALIASES=www.commercialbrainz.org
CADDY_TLS_MODE=origin
ACME_EMAIL=you@example.com
APP_PUBLIC_URL=https://commercialbrainz.org
API_PUBLIC_URL=https://commercialbrainz.org
CORS_ORIGINS=https://commercialbrainz.org,https://www.commercialbrainz.org
```

Origin cert files: `/opt/commercialbrainz/data/caddy/certs/` (not in git; mounted at `/etc/caddy/certs`).  
`fix-gcloud-vm.sh` regenerates the Caddyfile from `DOMAIN` + `DOMAIN_ALIASES` + `CADDY_TLS_MODE` on each deploy.

### 5. Deploys

| Branch | VM | URL |
|--------|-----|-----|
| `google` | `commercialbrainz-vm` | https://commercialbrainz.duckdns.org/ |
| `cloudflare` | `commercialbrainz-public` | https://commercialbrainz.org/ |

After CI, [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml) picks the VM from the branch. Optional repo variables: `VM_NAME_GOOGLE`, `VM_NAME_CLOUDFLARE`.

## Why not Flexible SSL?

**Flexible** (HTTPS to Cloudflare, HTTP to origin) is weaker and fights Caddy’s HTTPS redirects. Prefer **Full (strict) + Origin CA** — still $0 on Cloudflare.

## Troubleshooting

- **526 Invalid SSL certificate:** Origin CA missing/expired, or SSL mode not Full (strict); check `data/caddy/certs/` on **commercialbrainz-public**.
- **522 / 523:** firewall or VM down — ports **80** and **443** must allow Cloudflare; confirm A records use the **org** VM IP.
- **Wrong IP:** update Cloudflare A records to the static IP on `commercialbrainz-public-ip`.
- **Deploy can’t SSH:** grant `github-deploy` `roles/compute.osAdminLogin` on **commercialbrainz-public** (step 1).
- **Caddy logs:**  
  `sudo docker compose --env-file infra/compose.env -f infra/docker-compose.yml -f infra/docker-compose.vm.yml logs caddy --tail=80`
- **Renew Origin CA:** recreate in the dashboard and re-run `setup-cloudflare-domain.sh` before expiry.
