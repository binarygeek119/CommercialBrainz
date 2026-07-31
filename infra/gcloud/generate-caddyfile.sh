#!/usr/bin/env bash
# Generate Caddyfile for CommercialBrainz.
# Usage:
#   generate-caddyfile.sh <output-path> [primary-domain] [acme-email] [aliases-csv] [tls-mode]
#
# tls-mode:
#   auto   — Caddy Let's Encrypt (HTTP-01). Use for DuckDNS or grey-cloud DNS.
#   origin — Cloudflare Origin CA files at /data/certs/origin.crt + origin.key
#            (Cloudflare Free edge SSL + Full strict; orange cloud OK).
#
# aliases-csv example: www.commercialbrainz.org,commercialbrainz.duckdns.org
# www.<primary> redirects to https://<primary>{uri}.
# Other aliases: with tls-mode=auto they share the site block; with origin,
# only hosts under the primary domain use Origin CA — others get a separate
# auto-HTTPS block (e.g. DuckDNS during cutover).
set -euo pipefail

OUT="${1:?output path required}"
DOMAIN="${2:-}"
ACME_EMAIL="${3:-admin@localhost}"
ALIASES_CSV="${4:-}"
TLS_MODE="${5:-${CADDY_TLS_MODE:-auto}}"

ORIGIN_CERT="${CADDY_ORIGIN_CERT:-/etc/caddy/certs/origin.crt}"
ORIGIN_KEY="${CADDY_ORIGIN_KEY:-/etc/caddy/certs/origin.key}"

cat > "$OUT" <<EOF
{
	email ${ACME_EMAIL}
}

(commercialbrainz_proxy) {
	handle /health {
		reverse_proxy http://api:8000
	}
	handle /api/v1/site-status {
		reverse_proxy http://api:8000
	}
	handle /_maintenance/* {
		reverse_proxy http://maintenance:8080
	}

	handle {
		forward_auth http://maintenance:8080 {
			uri /_maintenance/auth
		}
		handle /api/* {
			reverse_proxy http://api:8000
		}
		handle /docs* {
			reverse_proxy http://api:8000
		}
		handle /redoc* {
			reverse_proxy http://api:8000
		}
		handle /openapi.json {
			reverse_proxy http://api:8000
		}
		handle {
			reverse_proxy http://web:80
		}
	}
}
EOF

tls_block() {
  if [[ "$TLS_MODE" == "origin" ]]; then
    cat <<EOF
	tls ${ORIGIN_CERT} ${ORIGIN_KEY}
EOF
  fi
}

if [[ -n "$DOMAIN" && -n "$ACME_EMAIL" && "$ACME_EMAIL" != "admin@localhost" ]]; then
  www_host=""
  under_primary=()
  external_hosts=()
  IFS=',' read -ra _aliases <<< "$ALIASES_CSV"
  for raw in "${_aliases[@]+"${_aliases[@]}"}"; do
    host="$(echo "$raw" | xargs)"
    [[ -z "$host" || "$host" == "$DOMAIN" ]] && continue
    if [[ "$host" == "www.${DOMAIN}" ]]; then
      www_host="$host"
    elif [[ "$TLS_MODE" == "origin" && ("$host" == *".${DOMAIN}" || "$host" == "$DOMAIN") ]]; then
      under_primary+=("$host")
    elif [[ "$TLS_MODE" == "origin" ]]; then
      external_hosts+=("$host")
    else
      under_primary+=("$host")
    fi
  done

  if [[ -n "$www_host" ]]; then
    cat >> "$OUT" <<EOF

${www_host} {
$(tls_block)
	redir https://${DOMAIN}{uri} permanent
}
EOF
  fi

  site_hosts="$DOMAIN"
  for host in "${under_primary[@]+"${under_primary[@]}"}"; do
    site_hosts="${site_hosts}, ${host}"
  done

  cat >> "$OUT" <<EOF

${site_hosts} {
$(tls_block)
	import commercialbrainz_proxy
}
EOF

  # DuckDNS (or other) hosts cannot use Cloudflare Origin CA — keep LE auto HTTPS.
  for host in "${external_hosts[@]+"${external_hosts[@]}"}"; do
    cat >> "$OUT" <<EOF

${host} {
	import commercialbrainz_proxy
}
EOF
  done
fi

cat >> "$OUT" <<'EOF'

:80 {
	import commercialbrainz_proxy
}
EOF

echo "Generated Caddyfile at $OUT (domain=${DOMAIN:-none} aliases=${ALIASES_CSV:-none} tls=${TLS_MODE})"
