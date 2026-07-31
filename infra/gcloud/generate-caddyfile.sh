#!/usr/bin/env bash
# Generate Caddyfile with optional Let's Encrypt for one or more hostnames.
# Usage:
#   generate-caddyfile.sh <output-path> [primary-domain] [acme-email] [aliases-csv]
#
# aliases-csv example: www.commercialbrainz.org,commercialbrainz.duckdns.org
# www.<primary> gets a permanent redirect to https://<primary>{uri}.
# Other aliases share the same site block (useful while migrating off DuckDNS).
set -euo pipefail

OUT="${1:?output path required}"
DOMAIN="${2:-}"
ACME_EMAIL="${3:-admin@localhost}"
ALIASES_CSV="${4:-}"

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

if [[ -n "$DOMAIN" && -n "$ACME_EMAIL" && "$ACME_EMAIL" != "admin@localhost" ]]; then
  www_host=""
  extra_hosts=()
  IFS=',' read -ra _aliases <<< "$ALIASES_CSV"
  for raw in "${_aliases[@]+"${_aliases[@]}"}"; do
    host="$(echo "$raw" | xargs)"
    [[ -z "$host" || "$host" == "$DOMAIN" ]] && continue
    if [[ "$host" == "www.${DOMAIN}" ]]; then
      www_host="$host"
    else
      extra_hosts+=("$host")
    fi
  done

  if [[ -n "$www_host" ]]; then
    cat >> "$OUT" <<EOF

${www_host} {
	redir https://${DOMAIN}{uri} permanent
}
EOF
  fi

  site_hosts="$DOMAIN"
  for host in "${extra_hosts[@]+"${extra_hosts[@]}"}"; do
    site_hosts="${site_hosts}, ${host}"
  done

  cat >> "$OUT" <<EOF

${site_hosts} {
	import commercialbrainz_proxy
}
EOF
fi

cat >> "$OUT" <<'EOF'

:80 {
	import commercialbrainz_proxy
}
EOF

echo "Generated Caddyfile at $OUT (domain=${DOMAIN:-none} aliases=${ALIASES_CSV:-none})"
