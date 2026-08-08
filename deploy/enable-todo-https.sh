#!/usr/bin/env bash
# Enable proper HTTPS for todo.baski.pro (Let's Encrypt)
set -euo pipefail
ROOT="/home/kon/Projects"
CADDY="$ROOT/baski-pro/Caddyfile"

echo "Adding DNS A todo -> 5.144.98.126 ..."
/home/kon/bin/regru-dns.sh add-a todo 5.144.98.126

echo "Waiting for authoritative DNS ..."
for i in $(seq 1 30); do
  if dig @ns1.reg.ru todo.baski.pro A +short | grep -q '5.144.98.126'; then
    echo "DNS OK"
    break
  fi
  sleep 10
done

if ! dig @ns1.reg.ru todo.baski.pro A +short | grep -q '5.144.98.126'; then
  echo "DNS still missing. Add manually in reg.ru: A todo 5.144.98.126" >&2
  exit 1
fi

echo "Switching Caddy to public LE cert ..."
python3 - <<'PY'
from pathlib import Path
p = Path("/home/kon/Projects/baski-pro/Caddyfile")
text = p.read_text()
text = text.replace("\ttls internal\n", "", 1)
p.write_text(text)
PY

cd "$ROOT/baski-pro"
docker compose up -d --force-recreate web
sleep 8
curl -fsS https://todo.baski.pro/api/health && echo && echo "OK: https://todo.baski.pro"
