# NoteTask / todo.baski.pro — context

Updated: 2026-09-03

## Stability audit 2026-08-29

Симптом: у клиента старая версия фронта из кэша висла на «Загрузка задач…» (строки нет в текущем коде). Сервер локально и через Caddy быстрый (API 1–10мс, БД 233KB, 150 задач, integrity ok, WAL, busy_timeout 5000).

Найденные слабые места:
- **Backend:** одно shared aiosqlite-соединение на все запросы (`app.state.db`); нет rollback при исключении mid-transaction → открытая транзакция отравляет следующие записи; конкурентные транзакции перемешиваются; нет глобального exception handler; нет индексов на tasks; action_log растёт вечно (пишется на каждый UI event).
- **Frontend:** fetch 12s timeout на все запросы (`app.js`/`widget.js`); `network` → boot-error / list retry, не logout; `refresh().catch(showListError)`; boot() auth vs network split.
- **SW:** ~~assets cache-first~~ fixed 2026-08-29: `notetask-v8`, assets network-first, API offline JSON 503.
- **Infra:** ~~Caddy HTTP/3 0-RTT → 425~~ fixed 2026-08-29 (`protocols h1 h2`); ~~нет автобэкапа~~ daily cron 04:00 → `scripts/backup-db.sh` (14d retention); нет внешнего мониторинга /api/health.
- Контейнер пересоздан 2026-08-29 14:16 (restart=unless-stopped, Restarts=0).

### Fixes applied 2026-08-29 (all live, verified)
- **Backend:** connection-per-request (`get_db` async generator: new aiosqlite conn, busy_timeout=5000, foreign_keys, rollback on exc, close); нет больше `app.state.db`; global exception handler → 500 JSON + log; retention action_log 180д в lifespan; индексы `idx_tasks_list`, `idx_tasks_due`, `idx_workout_sets_session`.
- **Frontend:** `api()` 12s timeout на ВСЕ запросы, network errors → `Error("network")`; boot(): auth→login, сеть→`#boot-error` «Нет связи» + «Повторить» (без сброса токена); `setView` → `refresh().catch(showListError)` — ошибка с retry в списке; widget.js так же. Версии: app.js v51, login v9, styles v37, pwa v4, pwa-install v3.
- **Fonts self-host:** `static/fonts/` (Manrope cyrillic+latin 400/500/650/700, Fraunces latin-only 600/700 — кириллицы у Fraunces нет и у Google тоже, fallback как раньше) + `fonts.css`; Google Fonts убран из index.html.
- **SW v8** (`notetask-v8`): assets network-first (быстрое обновление у клиентов), API → 503 JSON при offline; pwa.js регистрирует `sw.js?v=8`.
- **Backup:** `scripts/backup-db.sh` (python Connection.backup, retention 14д) в cron `0 4 * * *` → `data/backups/`; первый бэкап проверен (150 tasks).
- **Caddy:** HTTP/3 выключен глобально (`protocols h1 h2`) — ушли 425 Too Early на QUIC resume; baski-web пересоздан, todo+baski 200.
- **Verified в браузере:** fonts loaded, 0 запросов к googleapis, SW active, 50 задач отрендерено, API 3–6мс.
- Код-бэкап до изменений: `/tmp/notetask-pre-stability-2026-08-29.tar.gz`.
- **Git:** репо инициализирован (было не git); коммит НЕ сделан — нет git identity, config не трогаем.

## Availability audit 2026-08-29 (вечер)

Симптом: «todo.baski.pro вообще не открывается» у клиента. **Сервер здоров** — доказано: после 18:02 от машины пользователя (192.168.0.5) в Caddy не дошло НИ ОДНОГО пакета.

- **Root cause:** клиент обошёл split-DNS dnsmasq (Firefox DoH / чужой DNS) → резолв в публичный 5.144.98.126 → **на роутере нет hairpin NAT** (проверено: curl на публичный IP из LAN = timeout) → «не открывается». Chromium/YaBrowser с системным DNS → 192.168.0.6 → работает.
- **Снаружи БЫЛО 403 по дизайну → СНЯТО 2026-08-29 18:35:** `allowed_operator` убран из `todo.baski.pro` и `baski.pro/todo*` (решение пользователя). Сайт доступен из любой сети, защита = только пароль (JWT). Проверено внешним fetch: /api/health → 200. **Пароль слабый — сменить NOTEBOOK_PASSWORD в .env + перезапуск.** Snippet `(allowed_operator)` в Caddyfile остался, но нигде не используется.
- Hairpin на роутере по-прежнему нет: из LAN клиенты ОБЯЗАНЫ резолвить через dnsmasq (192.168.0.6) — Firefox DoH / чужой DNS на клиенте = timeout. Это не чинится со стороны сервера.
- **2026-08-29 18:44:** YaBrowser home = connection error (0 packets to Caddy). Root: TP-Link EC227 no hairpin + YaBrowser Secure DNS → 5.144.98.126. External + `http://192.168.0.6:8100/` = 200. Fix for domain from home: `\\192.168.0.6\homeserver\OTKROY-TODO.bat` (writes hosts). Router password still needed for true NAT loopback.
- **Риск:** мёртвые домены в Caddyfile без DNS — `duowork.baski.pro` (:71), `b-hunt.baski.pro` (:83), `innovation.baski.pro` (:107) → ACME NXDOMAIN retry-шторм → риск LE rate-limit → сорвёт продление сертов (todo cert до 2026-11-06).
- SPOF: dnsmasq + docker + Caddy на одной машине (оба enabled on boot). Мониторинга нет.
- Фикс для клиента: отключить DoH в Firefox ИЛИ hosts `192.168.0.6 todo.baski.pro` (уже упомянуто в login.js ошибке).
- **Сделано:** мёртвые домены (duowork, b-hunt, orgmind, innovation, portainer) удалены из Caddyfile → ACME-шторм остановлен (0 ошибок после recreate). Caddy управляет только: www/baski.pro, gendoc, treck, todo. Бэкап: `baski-pro/Caddyfile.bak-20260829`. Лендинги живут как subpath на baski.pro. Portainer — напрямую 192.168.0.6:9000/9443.
- treck.baski.pro с этой машины = timeout (тот же hairpin: резолв в публичный IP); с клиентов с split-DNS — ок. Upstream 127.0.0.1:8000 (TaskTracker) не проверен.

## Live

## Live
- **LAN caveat:** с домашней сети публичный IP без hairpin. Split-DNS: `todo.baski.pro` → `192.168.0.6` → **Caddy HTTPS**. Порт `:8100` только на `127.0.0.1` (не в LAN). Клиент всегда `https://todo.baski.pro/`.
- **Логин:** `login.js` v9 — домен only; soft-boot; SW `notetask-v8`; fonts self-hosted

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
- **Разделы (projects):** Inbox, Личные дела, Развлечения, Работа, Здоровье, Тренировки, Питание, Покупки, Идеи — sidebar + `@название` в задаче
  - **Покупки** (2026-09-03): обычный раздел — задача = желаемая покупка, сумма в чипе `cost`, галочка = купил; цвет `#c9892e`, sort 7
- **Разобрать (Inbox):** в сайдбаре только если есть open-задачи (`open_count` в `/api/projects`); пустой — скрыт
- **Sidebar:** кнопка «←» в topbar — сворачивает меню, состояние в `localStorage` (`notetask_sidebar_collapsed`)
- **Плашка задачи:** под каждой задачей чипы — раздел, P, срок/время, место, сумма (расход/доход)
- **Финансы:** суммы в задачах; сводка в «Статистика» — расходы/доходы/баланс за 30д + список операций
- **Downloads:** https://todo.baski.pro/download — Windows `.exe` + Android `.apk` (`data/downloads/`, `scripts/publish-downloads.sh`)
- **Desktop (Photino Win):** `desktop-win/` — WebView2 → `?client=desktop`; трей нет (окно); Ctrl+Space глобально; Startup shortcut. Build+publish: `dotnet publish …` + `scripts/publish-downloads.sh`
- **Desktop (Tauri):** `desktop/` — то же URL с `?client=desktop`; трей; Ctrl+Space; autostart; close→tray. Build: `cd desktop && npm run build` (Windows)
- **Android (Flutter):** `mobile/` — Today + виджет `TodayWidgetProvider`; API JWT. Build APK: see `mobile/README.md`
- **PWA / мобильное:** баннер «Скачать» на телефоне; manifest + service worker
- **Виджет:** https://todo.baski.pro/widget — компакт «Сегодня», после установки PWA открывается как приложение
- **Звук выполнения:** «Глухой удар» (Web Audio)
- **Логин:** отдельный `login.js` (autofill через rAF+focus, без pointerdown — ломал клик в WebView2/Photino); soft-boot через `__notetaskAfterLogin` без reload; ошибка заметная; SW `notetask-v7`
- **Desktop client:** `?client=desktop` + UA `NoteTaskDesktop` + `chrome.webview` / `__TAURI__` — прячет «Скачать» на логине и в сайдбаре; Photino URL `https://todo.baski.pro/?client=desktop`
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
