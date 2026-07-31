# Custom domain on Cloudflare Free (cheapest)

Use **Cloudflare Free** in front of the existing GCE VM. No Cloudflare paid plans, no static IP purchase required.

Target: **https://commercialbrainz.org** (and `www` → apex redirect).

## Cost

| Item | Cost |
|------|------|
| Cloudflare Free plan | $0 |
| Domain `commercialbrainz.org` | whatever you already paid |
| GCE e2-micro (free tier) | $0 in free-tier regions |
| Let's Encrypt via Caddy | $0 |

## Steps

### 1. Cloudflare DNS (dashboard)

1. [Add a site](https://dash.cloudflare.com) → enter `commercialbrainz.org` → **Free**.
2. At your registrar, set the two Cloudflare nameservers Cloudflare shows you.
3. DNS records (**Proxy = DNS only / grey cloud** until certificates work):

   | Type | Name | Content | Proxy |
   |------|------|---------|-------|
   | A | `@` | your VM external IP | DNS only |
   | A | `www` | same IP | DNS only |

   Find the IP:

   ```bash
   gcloud compute instances describe commercialbrainz-vm \
     --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
   ```

4. SSL/TLS → **Full** (use **Full (strict)** after HTTPS works).

Grey cloud matters: Let's Encrypt HTTP-01 must hit Caddy on the VM. Orange cloud (proxied) often breaks issuance until the cert already exists.

### 2. Configure the VM

From your laptop (after DNS is active):

```bash
chmod +x scripts/setup-cloudflare-domain.sh
GCP_PROJECT_ID=your-project \
DOMAIN=commercialbrainz.org \
ACME_EMAIL=commercialbrainz@outlook.com \
  ./scripts/setup-cloudflare-domain.sh
```

Defaults also keep `www.commercialbrainz.org` (redirect) and `commercialbrainz.duckdns.org` as an alias so the old URL keeps working during the cutover.

### 3. Optional: enable Cloudflare proxy

After `https://commercialbrainz.org/health` works:

1. Cloudflare DNS → set `@` and `www` to **Proxied** (orange).
2. SSL/TLS → **Full (strict)**.

You get free CDN / DDoS filtering. Stay on Free — skip Workers, Argo, paid WAF, etc.

### 4. App env (what the script sets)

On the VM `/opt/commercialbrainz/.env`:

```env
DOMAIN=commercialbrainz.org
DOMAIN_ALIASES=www.commercialbrainz.org,commercialbrainz.duckdns.org
ACME_EMAIL=you@example.com
APP_PUBLIC_URL=https://commercialbrainz.org
API_PUBLIC_URL=https://commercialbrainz.org
CORS_ORIGINS=https://commercialbrainz.org,https://www.commercialbrainz.org,https://commercialbrainz.duckdns.org
```

`fix-gcloud-vm.sh` regenerates the Caddyfile from `DOMAIN` + `DOMAIN_ALIASES` on each deploy.

## Troubleshooting

- **Cert stuck:** ensure grey cloud, port 80/443 open, and `curl -I http://commercialbrainz.org` reaches the VM.
- **Caddy logs:** on the VM  
  `sudo docker compose -f infra/docker-compose.yml -f infra/docker-compose.vm.yml logs caddy --tail=80`
- **Wrong origin IP:** update Cloudflare A records if the VM ephemeral IP changed (or reserve a static IP later — not free).
- **Orange cloud too early:** flip back to DNS only, wait for cert, then re-enable proxy.
