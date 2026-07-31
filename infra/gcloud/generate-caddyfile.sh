#!/usr/bin/env bash
# Generate Caddyfile with optional Let's Encrypt for DOMAIN.
# All traffic is reverse-proxied to the maintenance gate.
# Usage: generate-caddyfile.sh <output-path> [domain] [acme-email]
set -euo pipefail

OUT="${1:?output path required}"
DOMAIN="${2:-}"
ACME_EMAIL="${3:-admin@localhost}"

cat > "$OUT" <<EOF
{
	email ${ACME_EMAIL}
}

(commercialbrainz_proxy) {
	handle {
		reverse_proxy http://maintenance:8080
	}
}
EOF

if [[ -n "$DOMAIN" && -n "$ACME_EMAIL" && "$ACME_EMAIL" != "admin@localhost" ]]; then
  cat >> "$OUT" <<EOF

${DOMAIN} {
	import commercialbrainz_proxy
}
EOF
fi

cat >> "$OUT" <<'EOF'

:80 {
	import commercialbrainz_proxy
}
EOF

echo "Generated Caddyfile at $OUT (domain=${DOMAIN:-none})"
