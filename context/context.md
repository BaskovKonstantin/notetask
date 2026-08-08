# NoteTask / todo.baski.pro — context

Updated: 2026-08-08

## Live

- **Subdomain (LAN/WG via dnsmasq):** https://todo.baski.pro
- **Fallback:** https://baski.pro/todo/
- **Public DNS:** add A `todo` → `5.144.98.126` in reg.ru (API blocked `ACCESS_DENIED_FROM_IP` 2026-08-08)
- Caddy vhost `todo.baski.pro` → `127.0.0.1:8100` (same pattern as treck.baski.pro)

## Product

Personal tracker (not TreckBas):
- Tasks + Ideas/Someday
- Notes
- Workout diary
- ActionLog + soft-delete
- Stats (streak, 30d)
- Auth: shared password

## Stack

- FastAPI + SQLite in Docker (`python:3.12-slim`) — host Python 3.14 breaks pydantic
- Repo: `/home/kon/Projects/notetask`
- Compose: `docker compose up -d` → container `notetask`, bind `127.0.0.1:8100`
- Data: `./data/notetask.db`
- Caddy: `/home/kon/Projects/baski-pro/Caddyfile` (recreate container after Caddyfile replace — bind inode)

## Credentials

- File: `/home/kon/Projects/notetask/.env` (gitignored)
- Password: `NoteTask-2026-baski`
- Change ASAP after first login if exposed in chat

## Android widget

Phase 2: Flutter/Kotlin client against same API + App Widget.

## Ops

```bash
cd /home/kon/Projects/notetask && docker compose up -d --build
cd /home/kon/Projects/baski-pro && docker compose up -d --force-recreate web
```
