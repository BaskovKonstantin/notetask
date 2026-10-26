#!/usr/bin/env bash
# Add todo.baski.pro A record via reg.ru API
set -euo pipefail
IP="${1:-5.144.98.126}"
/home/kon/bin/regru-dns.sh add-a todo "$IP"
echo "Done. Wait 1-5 min, then: curl -sS https://todo.baski.pro/api/health"
echo "If ACCESS_DENIED_FROM_IP: reg.ru → Настройки → API → allowlist $IP"
