# Custom domain on Cloudflare Free (cheapest) — Cloudflare does SSL

Serve **https://commercialbrainz.org** with:

- Cloudflare **Free** (edge HTTPS, CDN, DDoS)
- Existing GCE free-tier VM as origin
- **Cloudflare Origin CA** cert on Caddy (also free)

No paid Cloudflare products. DuckDNS can stay as a secondary URL during cutover.

## Cost

| Item | Cost |
|------|------|
| Cloudflare Free | $0 |
| Cloudflare Origin CA | $0 |
| Domain `commercialbrainz.org` | whatever you paid |
| GCE e2-micro (free tier) | $0 in free-tier regions |

## Architecture

```
Browser --HTTPS--> Cloudflare (Free SSL) --HTTPS--> Caddy (Origin CA) --> api/web
```

SSL/TLS mode on Cloudflare: **Full (strict)**.  
DNS: **Proxied** (orange cloud) from the start — Cloudflare terminates visitor SSL.

## Steps

### 1. Cloudflare dashboard

1. [Add a site](https://dash.cloudflare.com) → `commercialbrainz.org` → **Free**.
2. At your registrar, set the two Cloudflare nameservers shown.
3. DNS → A records (**Proxied / orange**):

   | Type | Name | Content | Proxy |
   |------|------|---------|-------|
   | A | `@` | your VM external IP | Proxied |
   | A | `www` | same IP | Proxied |

   VM IP:

   ```bash
   gcloud compute instances describe commercialbrainz-vm \
     --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
   ```

4. **SSL/TLS → Overview** → **Full (strict)**.
5. **SSL/TLS → Origin Server → Create Certificate**:
   - Hostnames: `commercialbrainz.org` and `*.commercialbrainz.org`
   - Validity: 15 years is fine
   - Download / copy **Origin Certificate** and **Private Key** to your laptop, e.g.:
     - `~/cb-origin.crt`
     - `~/cb-origin.key`  
     (keep the key private; never commit it)

6. (Optional) SSL/TLS → **Always Use HTTPS** = On.

### 2. Configure the VM

From your laptop (after the zone is Active and Origin cert files exist):

```bash
chmod +x scripts/setup-cloudflare-domain.sh
GCP_PROJECT_ID=your-project \
DOMAIN=commercialbrainz.org \
ACME_EMAIL=commercialbrainz@outlook.com \
ORIGIN_CERT=$HOME/cb-origin.crt \
ORIGIN_KEY=$HOME/cb-origin.key \
  ./scripts/setup-cloudflare-domain.sh
```

This uploads the Origin CA files, sets `.env` (`DOMAIN`, CORS, public URLs, `CADDY_TLS_MODE=origin`), regenerates Caddy, and probes `https://commercialbrainz.org/health`.

Defaults also keep `www` → apex redirect and `commercialbrainz.duckdns.org` as a Let's Encrypt alias during cutover.

### 3. App env (what the script sets)

On the VM `/opt/commercialbrainz/.env`:

```env
DOMAIN=commercialbrainz.org
DOMAIN_ALIASES=www.commercialbrainz.org,commercialbrainz.duckdns.org
CADDY_TLS_MODE=origin
ACME_EMAIL=you@example.com
APP_PUBLIC_URL=https://commercialbrainz.org
API_PUBLIC_URL=https://commercialbrainz.org
CORS_ORIGINS=https://commercialbrainz.org,https://www.commercialbrainz.org,https://commercialbrainz.duckdns.org
```

Origin cert files live at `/opt/commercialbrainz/data/caddy/certs/` (not in git; mounted into Caddy at `/etc/caddy/certs`).  
`fix-gcloud-vm.sh` regenerates the Caddyfile from `DOMAIN` + `DOMAIN_ALIASES` + `CADDY_TLS_MODE` on each deploy.

## Why not Flexible SSL?

**Flexible** (HTTPS to Cloudflare, HTTP to origin) is weaker and fights Caddy’s HTTPS redirects. Prefer **Full (strict) + Origin CA** — still $0.

## Troubleshooting

- **526 Invalid SSL certificate:** Origin CA missing/expired, or SSL mode not Full (strict); check files on the VM under `data/caddy/certs/`.
- **522 / 523:** firewall or VM down — ports **80** and **443** must allow Cloudflare (and the world for DuckDNS).
- **Wrong IP after VM recreate:** update Cloudflare A records (ephemeral IP) or reserve a static IP later (not free).
- **Caddy logs:**  
  `sudo docker compose --env-file infra/compose.env -f infra/docker-compose.yml -f infra/docker-compose.vm.yml logs caddy --tail=80`
- **Renew Origin CA:** Cloudflare Origin certs last up to 15 years; recreate in the dashboard and re-run the setup script with new files before expiry.
