# NoteTask / todo.baski.pro — context

Updated: 2026-08-08

## Live

- **Primary URL:** https://baski.pro/todo/ (valid Let's Encrypt cert)
- **Subdomain todo.baski.pro:** blocked until public A record `todo → 5.144.98.126` in reg.ru + `./deploy/enable-todo-https.sh`
- reg.ru API rate-limited 2026-08-08 (`IP_EXCEEDED_ALLOWED_CONNECTION_RATE`)

## Product

Personal tracker (not TreckBas):
- Tasks + Ideas/Someday
- Notes
- Workout diary
- ActionLog + soft-delete — **все действия на сервере** (`action_log`)
  - CRUD задач/заметок/тренировок/проектов с `changes` в payload
  - UI: `POST /api/events` — экраны, шорткаты, logout, app_opened
  - login, backup → тоже в лог
  - `GET /api/history?entity_type=&action=&since=&until=`
- Stats (streak, 30d)
- Auth: shared password
- **Ctrl+Space** → Today + task form (`#view-tasks`), focus input
- Default view on open: **Today** (not Inbox)

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

## Todoist import

- Script: `scripts/import_todoist.py`
- Token: `TODOIST_API_TOKEN` in `.env` (gitignored), **never commit**
- Run: `docker compose exec notetask python /app/scripts/import_todoist.py [--completed]`
- Idempotent: `source=todoist` + `external_id` on tasks/projects
- Maps: projects, due dates, priority (P1↔4), labels/sections → notes
- After import: revoke Todoist token in Settings → Integrations


Phase 2: Flutter/Kotlin client against same API + App Widget.

## Ops

```bash
cd /home/kon/Projects/notetask && docker compose up -d --build
cd /home/kon/Projects/baski-pro && docker compose up -d --force-recreate web
```
