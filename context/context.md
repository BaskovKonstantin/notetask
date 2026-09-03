# NoteTask / todo.baski.pro — context

Updated: 2026-09-03 (~22:10 MSK)

## NLP cost parser 2026-09-03 (~22:10 MSK)

- Composer NLP extracts money from title → chip «Сумма», strip on submit (`cleanTitle`).
- Formats: `-N`/`+N` (expense/income), `N₽`/`N р`/`Nмлн`/`N тыс`, bare trailing large number (≥1000, ≥4 digits).
- Highlight `.hl-cost`. Cache: `app.js?v=60`, `styles.css?v=42`, SW `notetask-v13`.
- **Inline rename** (`startInlineTitleEdit`): same NLP — cost/priority/due/repeat/remind/project + strip from title. Cache `app.js?v=61`, SW `notetask-v14`.

## Priority chip colors 2026-09-03 (~22:05 MSK)

- Чип `P1`–`P4` в списке задач и композере: класс `prio-N`, цвета как у picker/badge (P1 красный, P2 оранж, P3 олива, P4 muted).
- Cache: `styles.css?v=41`, `app.js?v=59`, SW `notetask-v12`.

## LAN Access & Hairpin Fix 2026-09-03 (~21:25 MSK)

- Симптом скриншота: «Нет связи с сервером. Проверь сеть и попробуй снова.» + кнопка «Повторить».
- Причина: PWA / Service Worker (`sw.js`) отдаёт кэш на `https://todo.baski.pro/`. Скрипт `boot()` шлёт `api("/api/health")`. В домашней Wi-Fi DNS отдаёт WAN IP `5.144.98.126`. Роутер TP-Link EC227 не имеет NAT Loopback (hairpin) и сбрасывает пакеты. Запрос падает с 503 offline, UI зависает на экране ошибки.
- Что сделано:
  1. В Caddy (`/home/kon/Projects/baski-pro/Caddyfile`) добавлены блоки `http://192.168.0.6` (порт 80) и `https://192.168.0.6` (порт 443 internal TLS) с прокси на `127.0.0.1:8100`. Больше нет 308-редиректа на несуществующий TLS cert! Теперь `http://192.168.0.6/` открывается на стандартном порту 80 без ввода `:8100` (проверено во встроенном браузере, HTTP 200 OK).
  2. В `static/app.js` и `static/index.html` обновлён `LAN_ORIGIN = "http://192.168.0.6"`.
  3. Экран ошибки `showBootError()` теперь показывает заметную кнопку «Открыть через Wi‑Fi (192.168.0.6)» с авто-передачей токена через `#restore=`.
  4. Кэш обновлён: `sw.js` -> `notetask-v11`, `app.js?v=58`, `login.js?v=12`, `pwa.js?v=7`.
- Решение для домена `https://todo.baski.pro/` внутри Wi-Fi:
  - Вариант 1: В настройках Wi-Fi на телефоне/планшете вручную указать DNS 1 = `192.168.0.6`, DNS 2 = `1.1.1.1`.
  - Вариант 2: В роутере TP-Link (`http://192.168.0.1`) в настройках DHCP выставить Primary DNS `192.168.0.6` (серверный dnsmasq уже резолвит `todo.baski.pro` в `192.168.0.6`).
  - Вариант 3: Просто открывать `http://192.168.0.6` в браузере (порт 80 теперь работает прямо).

## Stage 2 partial 2026-09-03 (~15:45 MSK)

Shipped:
- Notify worker (`app/notify.py`): remind_at / due / evening overdue digest → `app_notifications` + Telegram
- Telegram via mihomo `TELEGRAM_PROXY=http://127.0.0.1:7890`; compose `network_mode: host`
- NLP remind in composer: `через 15 минут`, `за 1 час`, `напомни в 15:00`
- Browser Notification poll every 45s
- `/capture` compact overlay page; Photino `--overlay` + Ctrl+Space launches overlay process; Tauri capture window
- Smoke: remind task → in-app notification id=1 + Telegram test OK

Pending: rebuild Windows `.exe` / Tauri on Windows machine; rotate exposed bot token.

## Stage 1 shipped 2026-09-03 (~15:00 MSK) — Approach 1

Live on `http://127.0.0.1:8100` (docker rebuilt). Cache: `styles.css?v=39`, `app.js?v=55`.

1. **Task cards + sort** — `.item` card chrome; sort bar Due/Priority/Project/Amount + asc/desc; `localStorage` key `notetask_task_sort`.
2. **Inline title edit** — click `.item-title` → input; Enter/blur PATCH; Esc cancel.
3. **Work payments** — table `work_project_payments`; API list/create/delete under `/api/work-projects/{id}/payments`; work panel progress = paid_sum/budget.
4. **Health body** — 22 regions (teeth, neck, eyes, jaw, shoulders, elbows, knees, feet…); old regions still valid; SVG detailed map.
5. **Also** — clear due «Без срока» (composer + chip); NLP `в 15:30` / `15:30` → due time + strip from title; title input contrast fix kept.

Verify: Today sort bar; click title; Работа panel payments; Здоровье click «Зубы».

Stage 2 (Telegram/desktop overlay) — not started.

## Due clear on list chip (2026-09-03)

- List task due popover: кнопка **«Без срока»** (`data-task-clear-due`) → `PATCH { due_at: null, repeat_rule: null }`.
- UX: кнопка сразу под date/time (не внизу под repeat); класс `.chip-clear-due`.
- Commit: `b0b1f86` `feat(web): surface clear due on task chip` (app.js / styles.css / index cache bump).
- Уже работало раньше; проблема discoverability — кнопка была под длинным списком «Расписание».

## User requirements confirmed 2026-09-03 (~14:30 MSK)

1. **Inline-edit названия задачи**:
   - Одинарный клик по `.item-title` -> инпут на месте.
   - Enter / blur -> PATCH `/api/tasks/{id}`, Esc -> отмена.

2. **Карточки задач и сортировка**:
   - Каждая задача — отдельный блок-карточка (`.item` как карточка: фон, граница, радиус, отступ, тень).
   - Панель сортировки: Срок, Приоритет, Раздел, Сумма (направление asc/desc, сохранение в localStorage).

3. **Рабочие проекты: частичные оплаты**:
   - Список платежей (дата, сумма, комментарий) у проекта.
   - Прогресс-бар оплаты: `(sum(payments) / budget * 100)%`.
   - UI в `work-item`: шкала, сумма «получено X из Y (Z%)», форма добавления платежа.

4. **Карта тела (Здоровье) — высокая детализация**:
   - Высокая детализация: зубы, шея, глаза, нос, уши, челюсть, плечи, локти, колени, стопы и т.д. (20+ зон).

5. **Уведомления и напоминания**:
   - В момент срока + вечерний дайджест просроченных.
   - Ввод задачи: указание времени напоминания (абсолютное "15:00", "завтра в 10", относительное "через 15 минут", "за 1 час").
   - Канал: In-app + Telegram bot (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` в `.env`).
   - Примечание: серверный хост сейчас имеет timeout до `api.telegram.org` (нужен proxy/VPN/bypass для отправки наружу).

## Full server audit 2026-09-03 (~13:45 MSK) — «почему недоступно с другого устройства»

- Backend `notetask` жив: 127.0.0.1:8100 и 192.168.0.6:8100 (200 OK).
- Внешняя сеть (4G/LTE / WAN): `https://todo.baski.pro/` и `/api/health` 200 OK (проверено через внешний isolated runner). Снаружи сайт полностью доступен.
- Локальная сеть Wi-Fi: устройство (напр. телефон `192.168.0.4` пингуется 1.6ms), но 0 HTTP/HTTPS запросов доходят до Caddy/NoteTask.
- Причина 1 (домен): `todo.baski.pro` на Wi-Fi резолвится в публичный IP `5.144.98.126`. Роутер TP-Link (`192.168.0.1`) без NAT Loopback/hairpin сбрасывает пакеты LAN→WAN IP. На ПК `.5` работало только из-за записи в `hosts`.
- Причина 2 (DHCP DNS): dnsmasq на `192.168.0.6` работает и отдает `192.168.0.6`, но роутер раздает клиентам свой DNS `192.168.0.1` / провайдерский, поэтому другие устройства не знают локальный IP.
- Причина 3 (прямой IP): `http://192.168.0.6/` дает 308 redirect на `https://192.168.0.6/`, где Caddy падает с TLS alert (нет сертификата на IP). `192.168.0.6:8100` браузеры (Safari/Chrome) авто-апрейдят в HTTPS и получают TLS wrong version.


## Screenshot 2026-09-03 (~13:35) — Edge «Страница недоступна»

Клиент: `https://todo.baski.pro/download` → Chromium ERR (чёрный экран «Страница недоступна»).
Сервер: `/download` 200 за ~15ms (LAN + HTTPS + public resolve с самой машины).
Запросов с `.5` к todo нет → пакеты до Caddy не доходят. Тот же hairpin/DoH.

## Outage check 2026-09-03 (~13:32 MSK) — «как не грузился так и не грузится»

**Backend жив.** Клиент дома бьёт в `5.144.98.126` (DoH/8.8.8.8), TP-Link без hairpin → timeout. Старый Photino (`NoteTask-Setup.exe` 2026-08-29) **не** умеет LAN-first — HTTPS страница не доезжает → JS-fallback бесполезен.

Сделано сейчас:
- index.html: early Photino/desktop redirect на `http://192.168.0.6:8100` если `/api/health` мёртв; `Cache-Control: no-store` на index
- app.js v53 / login.js v11: UA `Photino` = desktop; boot auto-LAN
- Samba: `OPEN-NOTETASK.bat`, `ЗАПУСТИ-NOTETASK.bat`, `OTKROY-TODO.bat`
- Photino source уже LAN-first, **dotnet на сервере нет** — пересобрать Setup нельзя отсюда; нужен Windows publish

Доказательства:
- health 200 LAN + HTTPS с сервера
- `.5` ARP REACHABLE, ping/SSH закрыты; к todo с `.5` почти нет запросов
- `95.24.212.142` ходит в GitLab на baski.pro (внешка жива)

**Юзеру сейчас:** `\\192.168.0.6\homeserver\ЗАПУСТИ-NOTETASK.bat` или браузер `http://192.168.0.6:8100/`

## Outage check 2026-09-03 (~13:26 MSK) — «не грузится»

Повторная проверка после «приложение NoteTask не грузится».

**Вердикт тот же: backend жив. Ломается путь клиент→сервер.**

Доказательства тогда:
- `notetask` Up; `/api/health` 200 LAN+HTTPS
- dnsmasq: `todo` → `192.168.0.6`; `8.8.8.8` → `5.144.98.126`
- Assets: app.js v52, login.js v10 (позже → v53/v11)

## Outage check 2026-09-03 (~13:00 MSK)

Симптом пользователя: «везде Нет связи с сервером».

**Вердикт: приложение/сервер живы. Ломается путь клиент→сервер (DNS/hairpin), не backend.**

### Access unlock (same day)

User: «сними все ограничения — со всех устройств».

- Caddy: удалён мёртвый `(allowed_operator)` 403; `todo.baski.pro/todo*` → 301 `/`
- Web app.js v52 / login.js v10: LAN fallback `http://192.168.0.6:8100/` + `#restore=` JWT
- Photino PickStartUrl + Flutter `resolveApiBase`
- IP-ограничений на todo не было; снаружи уже открыто; защита = пароль

Доказательства сервер OK:
- `notetask` Up (restart 08:32 UTC clean Exit=0), RestartCount=0
- `/api/health` 200: `127.0.0.1:8100`, `192.168.0.6:8100`, `https://todo.baski.pro`
- login + `/api/projects` + `/api/tasks` 200 с паролем из `.env`
- Caddy `baski-web` host-network, `todo.baski.pro` → `127.0.0.1:8100`
- cert LE до 2026-11-06; dnsmasq active; split-DNS `todo`→`192.168.0.6`
- Playwright: логин-экран, base `/`, без boot-error
- Ошибок/traceback в `docker logs notetask` нет

Клиентская картина:
- Текст UI = `showBootError()` в `app.js` (есть токен, `fetch`/`json` упал → не auth)
- Photino с `192.168.0.5` в **08:21 UTC** полностью работал (health/projects/tasks 200)
- После рестарта контейнера **08:32 UTC** — **0** API-запросов Photino к todo (либо не открывали, либо пакеты не доходят)
- WireGuard peers `10.66.0.2/3` — **нет handshake** (WG offline)
- iptables REDIRECT hairpin `5.144.98.126:443` ≈ 1 пакет за жизнь — не спасает LAN→роутер
- UFW не режет 443/8100 с LAN; BLOCK только IGMP multicast с `.5`

Root cause (тот же что 2026-08-29): домашний Wi‑Fi + резолв в публичный `5.144.98.126` (DoH/Secure DNS/8.8.8.8) + **нет NAT hairpin на TP-Link** → timeout → «Нет связи». Лечится split-DNS `192.168.0.6` / hosts / отключить Secure DNS. Обход LAN: `http://192.168.0.6:8100/` (порт открыт в compose+UFW).

Вторично: на `todo.baski.pro` путь `/todo/api/*` отдаёт HTML (strip только на `baski.pro/todo*` via `handle_path`) — при ошибочном `NOTETASK_BASE=/todo` boot тоже покажет «Нет связи».

## Brand
- Logo: forest green rounded square + list/check — `https://todo.baski.pro/icons/logo.png` (also `logo.svg`, `logo-192.png`, `logo-512.png`). PWA icons `icon-192/512` synced.

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
- **LAN caveat:** с домашней сети публичный IP без hairpin. Split-DNS: `todo.baski.pro` → `192.168.0.6` → **Caddy HTTPS**. Порт `:8100` на `127.0.0.1` + `192.168.0.6` (LAN bypass). Клиент нормально `https://todo.baski.pro/`.
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
- **NLP срока:** дни недели (в понедельник…), месяцы (сентябрь / 15 октября), относительные даты; кириллица через unicode word-boundary (`app.js` v54)
- **NLP времени (2026-09-03):** `в 15:30` / `в 15.30` / `15:30` / `в 9:00` → `dueTime` + merge в `due_at` (дата из токена/чипа/сегодня), strip из title, подсветка `hl-date`; composer `#task-due-time`; `mergeTaskDue` пишет локальное `YYYY-MM-DDTHH:MM:00` (не UTC)
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
- Telegram: `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` in `.env` (added 2026-09-03). **Never commit.** Token was pasted in chat — rotate via @BotFather if leak risk.
- Note: from this host `api.telegram.org` may timeout (egress block) — verify from network that reaches TG.

## Planned (brainstorming 2026-09-03)

1. **Ctrl+Space capture overlay** — Photino + Tauri: маленькое always-on-top окно с вводом задачи, не полное приложение.
2. **Due/overdue notifications** — in-app + Telegram; DB already has `remind_at`.

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
