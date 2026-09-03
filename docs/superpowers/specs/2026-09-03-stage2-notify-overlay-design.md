# Stage 2 — Notifications + Ctrl+Space overlay

Date: 2026-09-03

## Notifications

**Triggers**
- `remind_at` reached → in-app + Telegram
- `due_at` with time reached → in-app + Telegram
- `due_at` date-only → 09:00 Europe/Moscow that day
- Evening digest (~20:00 MSK): all open overdue tasks in one Telegram/in-app message

**Channels**
- In-app: table `app_notifications` + `GET /api/notifications` poll; browser `Notification` when permitted
- Telegram: bot token + chat id from `.env`; HTTP(S) via `TELEGRAM_PROXY` (mihomo `127.0.0.1:7890`)

**Infra**
- Container uses `network_mode: host` so proxy on loopback works
- Dedup table `notification_log(kind, task_id, key)` unique

**Composer NLP (remind)**
- Absolute: `напомни в 15:00`, `напомни завтра в 10`
- Relative: `через 15 минут`, `через 2 часа`, `за 1 час` (before due)

## Ctrl+Space overlay

- Photino + Tauri: second always-on-top compact window (~420×120) loading `/widget?capture=1` or `/capture`
- Esc / submit → hide overlay; main window stays as-is
- Global hotkey shows overlay only, not full app

## Out of scope here

- Changing router hairpin / DNS (ops only)
