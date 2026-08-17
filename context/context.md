# NoteTask / todo.baski.pro — context

Updated: 2026-08-12

## Live
- **LAN caveat:** с той же сети публичный IP `5.144.98.126` часто не открывается (нет NAT hairpin). В LAN DNS (`dnsmasq` @ `192.168.0.6`) `todo.baski.pro` → `192.168.0.6`. Если ПК берёт 8.8.8.8 — будет таймаут. Фикс: DNS `192.168.0.6` или hosts `192.168.0.6 todo.baski.pro`. Аварийный вход без DNS: `http://192.168.0.6:8100/` (порт на LAN в docker-compose).

- **Primary URL:** https://todo.baski.pro/ (Let's Encrypt, A `todo` → 5.144.98.126)
- **Legacy path:** https://baski.pro/todo/
- Caddy: `todo.baski.pro` → `127.0.0.1:8100` (LE cert, no `tls internal`)

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
- **Разделы (projects):** Inbox, Личные дела, Развлечения, Работа, Здоровье, Тренировки, Питание, Идеи — sidebar + `@название` в задаче
- **Разобрать (Inbox):** в сайдбаре только если есть open-задачи (`open_count` в `/api/projects`); пустой — скрыт
- **Sidebar:** кнопка «←» в topbar — сворачивает меню, состояние в `localStorage` (`notetask_sidebar_collapsed`)
- **Плашка задачи:** под каждой задачей чипы — раздел, P, срок/время, место, сумма (расход/доход)
- **Финансы:** суммы в задачах; сводка в «Статистика» — расходы/доходы/баланс за 30д + список операций
- **Downloads:** https://todo.baski.pro/download — Windows `.exe` + Android `.apk` (`data/downloads/`, `scripts/publish-downloads.sh`)
- **Desktop (Tauri):** `desktop/` — WebView → todo.baski.pro; трей; Ctrl+Space глобально; autostart; close→tray. Build: `cd desktop && npm run build` (Windows)
- **Android (Flutter):** `mobile/` — Today + виджет `TodayWidgetProvider`; API JWT. Build APK: see `mobile/README.md`
- **PWA / мобильное:** баннер «Скачать» на телефоне; manifest + service worker
- **Виджет:** https://todo.baski.pro/widget — компакт «Сегодня», после установки PWA открывается как приложение
- **Звук выполнения:** «Глухой удар» (Web Audio)
- **Логин:** отдельный `login.js` (autofill/пустой value); без HTML required; ошибка заметная; SW `notetask-v4`
- **Расписание (repeat):** в поповере срока — каждый день / 2–3 дня / будни / неделя / месяц; `repeat_rule`; выполнение → следующий срок (Todoist-style)
- **Подсветка ввода:** распознанные токены (срок, p1–p4, @раздел, #метка, идея/план) цветные в поле задачи
- **NLP срока:** дни недели (в понедельник…), месяцы (сентябрь / 15 октября), относительные даты; кириллица через unicode word-boundary (`app.js` v45)
- **Микроанимации:** удаление/перемещение/выполнение/создание задач (+ заметки, проекты, цели); смена экрана; уважает `prefers-reduced-motion`
- **Тема раздела:** при открытии раздела UI плавно перекрашивается в `project.color` (CSS vars `--accent`, `--theme-glow*`)
- **Рабочий проект у задачи:** в разделе Работа — чип «Проект» (composer + плашка задачи), поле `work_project_id` → `work_projects`; удаление проекта: × справа + confirm, отвязка задач
- **Правая панель раздела** (клик по разделу → workspace split):
  - Личные дела → финансы (как трекер): один месяц ‹›, крупный баланс, доход/расход, полоска, список операций из задач
  - Работа → рабочие проекты (`/api/work-projects`, `work_projects`)
  - Здоровье → SVG тела + метрики (`/api/health-profile`, `health_metrics` / `health_body`)
  - Тренировки → цели и прогресс (`/api/workout-panel`, `workout_goals`)
  - Остальные разделы / Сегодня — панель скрыта
  - UI: `#section-panel`, CSS `main.with-section-panel`, `app.js` v45 / `styles.css` v35

## Stack

- FastAPI + SQLite in Docker (`python:3.12-slim`) — host Python 3.14 breaks pydantic
- Repo: `/home/kon/Projects/notetask`
- Compose: `docker compose up -d` → container `notetask`, bind `127.0.0.1:8100`
- Data: `./data/notetask.db`
- Caddy: `/home/kon/Projects/baski-pro/Caddyfile` (recreate container after Caddyfile replace — bind inode)

## Credentials

- File: `/home/kon/Projects/notetask/.env` (gitignored)
- Password: in `.env` (`NOTEBOOK_PASSWORD`), gitignored

## Todoist import

- Script: `scripts/import_todoist.py`
- Token: `TODOIST_API_TOKEN` in `.env` (gitignored), **never commit**
- Run: `docker compose exec notetask python /app/scripts/import_todoist.py [--completed]`
- Idempotent: `source=todoist` + `external_id` on tasks/projects
- Maps: projects by **P1→Работа, P2→Личные дела, P3→Тренировки, P4→без проекта**, due dates, priority, labels/sections → notes
- Remap: `docker compose exec notetask python /app/scripts/import_todoist.py --remap-projects`
- After import: revoke Todoist token in Settings → Integrations


Phase 2: Flutter/Kotlin client against same API + App Widget.

## Ops

```bash
cd /home/kon/Projects/notetask && docker compose up -d --build
cd /home/kon/Projects/baski-pro && docker compose up -d --force-recreate web
```
