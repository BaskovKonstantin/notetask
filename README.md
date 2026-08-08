# NoteTask

Personal task / ideas / workout diary with action history.

**Live:** https://baski.pro/todo/  
**Subdomain (after DNS):** https://todo.baski.pro

## Stack

- FastAPI + SQLite
- Vanilla SPA (`static/`)
- systemd user unit + Caddy `todo.baski.pro` → `:8100`

## Local run

```bash
cd /home/kon/Projects/notetask
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
set -a && source .env && set +a
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8100
```

## Deploy (konBas)

```bash
mkdir -p ~/.config/systemd/user
cp deploy/notetask.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now notetask
# Caddy (from baski-pro):
cd /home/kon/Projects/baski-pro && docker compose exec web caddy reload --config /etc/caddy/Caddyfile
# DNS:
/home/kon/bin/regru-dns.sh add-a todo 5.144.98.126
```

Password / secret: `.env` (not committed). See `context/context.md`.
