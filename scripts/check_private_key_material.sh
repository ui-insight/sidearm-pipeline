#!/usr/bin/env bash

set -euo pipefail

status=0

for file in "$@"; do
  if [[ ! -f "$file" ]]; then
    continue
  fi

  case "$file" in
    *.pem|*.key|*.p12|*.pfx|*.p8|id_rsa|id_dsa|id_ecdsa|id_ed25519)
      echo "Potential private key or certificate file staged: $file" >&2
      status=1
      continue
      ;;
  esac

  if grep -Eq -- '-----BEGIN ([A-Z0-9 ]+ )?PRIVATE KEY-----' "$file"; then
    echo "Private key material detected in staged file: $file" >&2
    status=1
  fi
done

if [[ $status -ne 0 ]]; then
  cat >&2 <<'EOF'
Remove the secret material from the commit and keep credentials in local .env
files, your deployment platform, or another secret manager instead.
EOF
fi

exit "$status"
