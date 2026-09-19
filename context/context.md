# NoteTask / todo.baski.pro — context

Updated: 2026-09-15 (~19:15 MSK)

## Review Important fixes: finance ledger (2026-09-15 ~19:15)

- Branch: `feat/finance-ledger-table`. Do not switch. No `git config`.
- Work payment project change: PATCH `{ work_project_id }` on same row (`reassign_work_payment_project`). No POST+DELETE. Keeps id/amount/paid_at/note/status. Target must be live work project.
- `WorkPaymentPatch.work_project_id` optional. Frontend `saveLedgerField` single PATCH.
- `deleteLedgerRow`: `confirm("Удалить строку?")` for task/work/draft. Cancel = no-op.
- Cache: `styles.css?v=52`, `app.js?v=79`, `pwa.js?v=15`, SW `notetask-v31`, `sw.js?v=31`.
- Test: `WorkPaymentReassignTests.test_move_to_another_live_project_keeps_row`.
- Report: `.superpowers/sdd/final-fix-report.md`

## Task 4: Cache bump + browser verify (2026-09-15 ~19:05)

- Branch: `feat/finance-ledger-table`. Cache already at brief targets from Goals `c8c7d83`: `styles.css?v=51`, `app.js?v=78`, `pwa.js?v=14`, SW `notetask-v30`, `sw.js?v=30`. No file diff, no cache commit.
- `docker restart notetask`. Ledger API 19 rows (16 task + 3 work).
- Browser: Playwright `http://127.0.0.1:8100/` (cursor-ide-browser: no tab). Checklist 1–7 PASS. No live POST amounts. Draft «Новая строка» amount 0, Tab, Delete.
- Report: `.superpowers/sdd/task-4-report.md`

## Task 3: Inline ledger edit + draft + keyboard (2026-09-15 ~18:45)

- Branch: `feat/finance-ledger-table`. Files: `static/app.js`, `static/styles.css`. Cache **not** bumped (Task 4).
- Cells: project `<select data-fin-field="project_id">` (work: disabled «Работа»); title input or work_projects select; amount text+inputmode decimal (ru grouping); day `type=date` empty ok; status План/Подтверждено.
- Draft: `+ строка` local `{source:draft, id:-Date.now(), project Личные дела, title unique «Новая строка», amount:0, day:today, status:plan}`. POST `/api/tasks` only when amount ≠ 0. Never fake 0.01.
- Save: task PATCH title/project_id/cost+cost_type/due_at; complete POST / reopen PATCH open. Work PATCH amount (gt 0) / paid_at / planned|received; work_project_id = POST new + DELETE old.
- Delete selected: draft drop; task DELETE; work payment DELETE. Esc focuses `tr[tabindex=-1]` so Delete stays in table.
- Keyboard steal only inside `.fin-ledger-table` on `#finance-page`. Filters from Task 2 still work. Old `data-fin-cat` / drawer / month-shift handlers removed.
- Report: `.superpowers/sdd/task-3-report.md`

## Goals skill-tree shipped (2026-09-15 ~18:15)

- Commit: `c8c7d83` on `feat/finance-ledger-table`.
- Spec/plan: `docs/superpowers/specs/2026-09-15-goals-skill-tree-design.md`, `plans/2026-09-15-goals-skill-tree.md`.
- Backend: `app/goals.py` + hook in `task_complete` / PATCH/PUT done.
- UI: sidebar **Цели**, Cytoscape `breadthfirst`, `static/goals.js` + `vendor/cytoscape.min.js`. Cache `app.js?v=78`, `styles?v=51`, SW v30, `pwa.js?v=14`.
- Smoke goal id=1 «Smoke цель» in DB.

## Task 2: Ledger grid UI (2026-09-15 ~18:05)

- Branch: `feat/finance-ledger-table`. Files: `static/app.js`, `static/styles.css`.
- `#view-finance`: table **Проект | Направление | Цена | Месяц | Статус**. Filters ▾ per column. Hero **Баланс** from `ledgerVisibleRows()`. Accounts = `GET /api/finance/sheet?year_month=` current month `.accounts` only.
- State: `financeLedger`, `financeLedgerFilters` (col → Set|null), `financeDrafts=[]`. `+ строка` (`data-fin-add-ledger`) no-op until Task 3.
- No month ‹ ›, no Статья/План/Факт, no `#fin-fact-drawer`. Old `data-fin-cat` handlers remain, no such rows.
- Cache still `app.js?v=77` (Task 5). Commit blocked: Author identity unknown; UI files staged. Do not `git config`.
- Report: `.superpowers/sdd/task-2-report.md`

## Brainstorm: Finance ledger table (2026-09-15)

User Sheet columns: Проект · Направление · Цена ± · Месяц · Статус. Replace Статья/План/Факт/Δ.

Approved:
- Approach A: `GET /api/finance/ledger` over tasks-with-cost + work payments. No `finance_ledger` table.
- Row = task (Направление=title, Проект=section) or work payment (Проект locked Работа, title=work_projects.name).
- Sheet labels Спортики/Снеговоики → Работа, Жизнь/Кредитка → Личные дела (mapping only). Column shows sidebar section. Any section with cost.
- Статус: open/planned=План, done/received=Подтверждено.
- All months, Excel column filters. Месяц = real due_at/paid_at.
- Hero stays; numbers = visible filtered rows; no month arrows; accounts unchanged. No totals row.
- Inline Excel edit. `+` = local draft, POST when price ≠ 0.
- No recurring month-clone. No live money during verify.
- Spec: `docs/superpowers/specs/2026-09-15-finance-ledger-table-design.md`
- Plan: `docs/superpowers/plans/2026-09-15-finance-ledger-table.md`
- Gate: user picks execution (subagent vs inline). Do not code until then.

Sample Sheet rows: CRM +255k, Манаков −50k (Aug); Снеговики +250k, Работник −100k, Компьютер −170k, Cursor −20k, Еда −20k, Дом −60k (Sep); Cursor −20k, Еда −20k, Снеговики +506k (Oct). Sum 551k not shown in UI.

## Brainstorm: Goals game-graph (2026-09-15 ~17:07)

- User: start Goals now (Finance done; graph not built).
- Status: **shipped** (see section above). Separate from workout_goals.
- Prior note: sidebar section Цели, several tabs, game-style graph = plan to reach a goal.
- Decision: **A** skill tree — root = big goal, branches = steps, unlock as completed.
- Decision: **C** complete node = manual check OR linked NoteTask done.
- Decision: **B** sidebar «Цели» → tabs (goal = tab) + skill tree graph.
- Decision: **A** unlock: all parents done → child unlocked.
- Decision: **A** build: «+» on node → child by title; no free drag-edges in v1.
- Decision: **B** v1 already game look: medal nodes, path lines, glow/unlock anim.
- Approach: **2** Cytoscape.js (+ dagre/elk layout for tree).
- Design §1 data/API: approved (goals, goal_nodes, goal_edges; unlock all parents; complete manual|task).
- Design §2 UI: approved (sidebar Цели, tabs, Cytoscape medals, side panel, workout_goals untouched).
- Design §3 tech: approved (app/goals.py, cytoscape+dagre vendor, task→node hook, one parent v1).

## Review fixes: finance Excel branch (2026-09-14 ~20:25)

- Branch: `feat/finance-excel-task-sync` (do not switch to main; keep `e8a9602` hourly notify).
- `+ строка`: unique live name «Новая статья» / «Новая статья 2»… (`uniqueFinanceCategoryName`).
- Plan PUT: `await loadFinancePage()` after success so Δ refreshes.
- `patch_task`: rematch category when `cost_type` or `cost` changes (same as `project_id`), if `finance_category_id` not in patch and `has_cost`.
- Keyboard: Tab/Enter/Arrow steal only inside `tr[data-fin-cat]` name/plan or selected row.
- Removed unused `Any` from `app/finance_task_sync.py`.
- Tests: `test_cost_type_change_rematch_different_id`; 33 ok.

## Fix: hourly reminds after complete (2026-09-14 ~20:08)

- Symptom: TG hourly nags for #16/#161 after «Выполнить» same day.
- Root: `complete_task_row` sets pause `remind_at` = next due morning 09:00; `notify.tick_once` hourly branch ignored `remind_at`, fired every hour and overwrote pause to next `:00`.
- Fix: `hourly_ready(now, remind_at)` in `app/remind_utils.py`; notify fires hourly only if ready. Live DB #16/#161 resume restored `2026-09-15T09:00:00+03:00`.
- Tests: `HourlyReadyTests` in `tests/test_hourly_remind.py`.
- Pending (separate): TG Mini Apps + bot UX — brainstorm, not started.

## Task 4: Excel grid UI + Fact drawer (2026-09-14)

- Branch: `feat/finance-excel-task-sync` (do not switch to main).
- UI: `static/app.js` + `static/styles.css`. No cache bump (Task 5). No Python.
- `#view-finance` grid columns: Статья | План | Факт | Δ | +. Name = contenteditable `data-fin-name`. Plan = `input.fin-plan-input`. Fact = `td.is-fact` (not input).
- Removed `#fin-tx-form` and page journal `.fin-ops-page`. Journal = drawer `#fin-fact-drawer` from `categories[].fact_entries`.
- `state.financeSheet = data` in `renderFinancePage`. Click Fact → drawer. Click task → `setView("today")` + `anim-pulse` + `scrollIntoView` on `.item[data-id]`.
- Row `+` / drawer «+ задача»: `prompt` title then amount; cancel amount = no POST. `POST /api/tasks` with `finance_category_id`, `cost_type=kind`, `project_id` if `projects.name === category.name`, `due_at` = today or `{ym}-01`.
- `+ строка`: `POST /api/finance/categories` `{ name: "Новая статья", kind, group_name }`. Duplicate live `(name, kind)` → 409 alert.
- Delete: selected row Delete/Backspace or × → `DELETE /api/finance/categories/{id}`; 409 shows `detail`.
- Rename blur: `PATCH` `{ name, kind, group_name, sort }`. Keys: Tab name↔plan, Enter next row, arrows, Esc closes drawer.
- Commit: `feat(finance): Excel grid and Fact drawer`. Do not commit `.superpowers/` or `scripts/backup-db.sh`.

## Task 3: Sheet Fact by category + 409s (2026-09-14)

- Branch: `feat/finance-excel-task-sync`
- `GET /api/finance/sheet`: Fact per category = tasks (`task_month_key` due then created) + sheet txns + work payments on **Работа/income** only. No lump into «Прочие *» / «Подработка». `_rollup_task_work_budget` removed.
- Each `categories[]` item: `planned`, `actual`, `delta`, `fact_entries[]` (`source` task|sheet|work, id, title, amount, day, task_id).
- Helpers: `category_actuals_for_month`, `category_has_entries`, `assert_unique_live_category` in `app/finance_sheet.py`.
- 409: duplicate live `(name, kind)` on create; delete if tasks/txns/any work payment on Работа/income.
- Month bucket change only on sheet path, not `/api/finance/months`.
- Tests: `tests/test_finance_sheet_fact.py` (8). Host `.venv` is Python 3.14 — fastapi/pydantic stubs in that test file.
- `sum_work_payment_income(..., year_month=)` still 250k in August.

## Brainstorm: Finance Excel + Goals game-graph (2026-09-14 ~15:56 MSK)

- User ask (started in treckbas by mistake, switched here): (1) Finance as Excel table synced with tasks; (2) new Goals section, several tabs, game-style graph we design together — graph = plan to reach a goal.
- Current: sidebar Сегодня / Финансы / История / Статистика + project sections. **No Цели.**
- Finance now: month, balance, accounts, budget grid (Статья · План · Факт · Δ), txn form, journal (manual + task amounts + work payments). API `/api/finance/sheet`. Tasks already have `cost` / `costType`.
- Two independent pieces. Finance spec written. Goals later, own spec.
- Spec: `docs/superpowers/specs/2026-09-14-finance-excel-task-sync-design.md`
- Plan: `docs/superpowers/plans/2026-09-14-finance-excel-task-sync.md`
- Shipped on `feat/finance-excel-task-sync` (not merged). Live via mounted `app/`+`static/` after `docker restart notetask`.
- Browser 2026-09-14: grid Статья|План|Факт|Δ|+; no txn form; Fact drawer lists tasks; Sep Покупки −530k / Работа −320k; Aug Работа +250k work (not Подработка). Cache `app.js?v=77`.
- Goals still later, own spec.
- Decisions so far:
  - First: Finance (Goals later).
  - Rows stay budget articles (Статья / План / Факт / Δ), not task-per-row.
  - Excel feel: click cell, Tab/Enter, add/delete row. No formulas.
  - Page: hero (balance + accounts) + grid; journal = click Fact.
  - Fact = tasks + manual txns + work payments.
  - Task month = due_at; no due → created_at.
  - Default article = task project/section name (Здоровье, Работа, …).

## TG reminds outage 2026-09-14 (~11:55 MSK)

## TG reminds outage 2026-09-14 (~11:55 MSK)

**Причины (две):**
1. `TELEGRAM_PROXY=http://127.0.0.1:7890` без auth → mihomo **407**. getMe/send/getUpdates fail. Fix in `.env`: proxy URL with mihomo `authentication` user (не в git).
2. Complete (TG «Выполнить» / API) с `cleared_remind` снимал `remind_rule` у daily → #161/#16 без hourly с ~10–13 сент.

**Фикс:**
- `.env` proxy auth (recreate container).
- Recurring+hourly: keep `remind_rule`, pause until next due day 09:00 (`_hourly_resume_at`).
- Re-enabled hourly on #161 Отжиматься, #16 Почистить зубы.
- Verify: getMe/send True; test TG message delivered.

## TG remind «Выполнить» button 2026-09-09 (~13:05 MSK)

- Remind + due TG messages: inline `✅ Выполнить` (`callback_data=done:{id}`).
- Notify loop long-polls `getUpdates` (callback_query); only `TELEGRAM_CHAT_ID`.
- Tap → `complete_task_row` (same as API): recurring rolls due, clears `remind_*` so hourly stops; edits message to ✓.
- Shared: `app/task_complete.py`, `app/tg_callbacks.py`.
- Tests: `tests/test_tg_complete_callback.py`.

## Hourly remind until done 2026-09-09 (~12:40 MSK)

- `tasks.remind_rule` TEXT (`hourly` | NULL). One-shot `remind_at` без rule — как раньше.
- Worker: open + hourly → на локальном `:00`…`:04` шлёт TG/in-app, dedupe `remind:{id}:{YYYY-MM-DDTHH}`, двигает `remind_at` на след. час.
- Стоп: status≠open или «Без напоминания» (`remind_rule`+`remind_at` null). Daily complete не сбрасывает hourly.
- UI: пресет **Каждый час** (composer + список). Чип `Каждый час · HH:00`.
- NLP: `каждый час`, `напоминай/напомни/долби каждый час`, `hourly` → strip + highlight.
- Включено на #161 Отжиматься, #16 Почистить зубы. Cache: `app.js?v=76`, `pwa.js?v=13`, SW `notetask-v28`.
- Tests: `tests/test_hourly_remind.py` (7 ok).

## Treck LAN hairpin (parallel to todo) 2026-09-08 (~17:40 MSK)

- Treck: client fallback → `http://192.168.0.6:8000` + cookie Secure via X-Forwarded-Proto (see treckbas context).
- hosts script (`fix-windows-hosts.ps1`) already lists `treck.baski.pro`; health check now also pings treck.
- Caddy `http://192.168.0.6/` остаётся NoteTask only (`:8100`); treck — порт `:8000`.

## Outage check 2026-09-08 (~17:30 MSK) — «домен не грузится / проверь nginx»

**Вердикт: nginx не участвует; Caddy + backend живы; снаружи 200.**

- Host `nginx` = **inactive**. Прокси = Docker `baski-web` (**Caddy**), Caddyfile `todo.baski.pro` → `127.0.0.1:8100`.
- `notetask` Up; `/api/health` 200: `127.0.0.1:8100`, `http://192.168.0.6`, `https://todo.baski.pro` (LAN + `--resolve` на WAN `5.144.98.126`).
- LE cert `CN=todo.baski.pro` до **2026-11-06**.
- DNS: `@8.8.8.8` / router `192.168.0.1` → `5.144.98.126`; dnsmasq `192.168.0.6` → `192.168.0.6`; `/etc/hosts` тоже.
- Caddy access: внешние клиенты (YaBrowser, Photino) на `todo.baski.pro` — 200 прямо сейчас.
- Скорее снова **hairpin** домашнего Wi‑Fi (router DNS/DoH → WAN IP, NAT loopback нет). Обход: DNS/`hosts` на `192.168.0.6` или `http://192.168.0.6/`.

## Daily repeat catch-up 2026-09-06 (~18:50 MSK)

- Open `repeat_rule=daily` с `due_at < today` → на `GET /api/tasks` snap `due_at` на сегодня (время/дата-only сохранить). Не тянуть старую дату в чипе.
- Complete daily: next due = завтра от **сегодня**, не +1 от просроченной даты (`next_daily_after_complete`).
- Chip: если due сегодня и не overdue → «Сегодня» / «Сегодня HH:MM» (+ «· Каждый день»).
- Helpers: `catch_up_daily_due_at`, `snap_due_to_day`, `next_daily_after_complete` в `app/due_utils.py`.
- Tests: `tests/test_daily_catchup.py` (8 ok). Cache: `app.js?v=75`, `pwa.js?v=12`, SW `notetask-v27`.
- Verify: task 161 Отжиматься `due=2026-09-06`; UI чип «Сегодня · Каждый день» (было «4 сент. · Каждый день»).

## Due period window (due_start…due_at) 2026-09-06 (~18:40 MSK)

- DB: `tasks.due_start` TEXT (migrate `ensure_column`).
- Semantics: `due_at` = конец/срок; `due_start` = начало окна (nullable). Без start — однодневный срок как раньше.
- Повестка `view=today`: окно с `today >= due_start` (включая после конца = просрочка); до start — не в today, в `upcoming`.
- UI поповер срока: поля **С** / **По** (+ время); чип `1 сент.–30 сент.`; просрочка `Просрочено · …` + класс `.is-overdue` (красн.). `due_at` не автосдвигается.
- Quick-пресеты / «Без срока» сбрасывают `due_start`. Повтор при complete → `due_start=NULL`.
- Helpers: `app/due_utils.py` — `due_day`, `normalize_due_start`, `task_in_today_view`, `task_in_upcoming_view`, `task_window_overdue`.
- Tests: `tests/test_due_window.py` (13 ok). Cache: `app.js?v=74`, `styles.css?v=49`, `pwa.js?v=11`, SW `notetask-v26`.
- Verify: task 138 Spider `2026-09-01…30` чип «1 сент.–30 сент.» в Сегодня; ЛЦТ/отжимания — «Просрочено · …».



## Due chip «Сегодня» + overdue group 2026-09-06 (~12:35 MSK)

- Поповер срока (список + composer): кнопка **Сегодня** над «Завтра» (`data-quick-due="today"` / `data-composer-quick-due="today"`). Клик пишет `due_at` на сегодня, время оставляет.
- Просроченные **открытые** в списке группируются под заголовок «Сегодня». `due_at` в БД не меняется; чип как был («4 сент.»). Выполненные остаются под своей датой.
- `taskDayKey`: `status !== "done"` и `due[:10] < todayIso()` → ключ сегодня.
- Cache: `app.js?v=73`, `pwa.js?v=10`, SW `notetask-v25`.
- Verify LAN: open-группа только «Сегодня» (Силовые, ЛЦТ, отжимания, Spider-Men, зубы); done — август/сентябрь даты; меню чипа: Сегодня…Через месяц.



## Outage check 2026-09-06 (~12:20 MSK) — «почему перестал работать поддомен todo»

**Вердикт: поддомен не падал.** Backend + Caddy + LE + публичный DNS живы. Ломается только путь клиент→сервер в домашнем Wi‑Fi (тот же hairpin, что 2026-08-29 / 2026-09-03).

Доказательства:
- `notetask` Up 2 days, RestartCount=0; `/api/health` 200 на `127.0.0.1:8100` (~1ms)
- `https://todo.baski.pro/api/health` 200 с сервера (split-DNS → `192.168.0.6`) и **снаружи** (WebFetch isolated)
- Публичный A `@8.8.8.8` = `5.144.98.126` (совпадает с WAN / `ifconfig.me`)
- LE cert `CN=todo.baski.pro` до **2026-11-06**; Caddy ACME без error за 48h
- Browser на сервере: логин-экран NoteTask, URL `https://todo.baski.pro/`
- Caddy 24h `todo.baski.pro`: status почти все 200/304/308; клиенты — боты (185.213.175.92 и др.) + LAN `192.168.0.5` (55 req, Cursor 12:15 MSK, полный boot: `/` `app.js?v=71` `/api/health` `/api/projects` 200)
- Router DNS `192.168.0.1` → `5.144.98.126`; dnsmasq `192.168.0.6` → `192.168.0.6`
- WireGuard peers `10.66.0.2/3` — **нет handshake**
- Caddyfile mtime 2026-09-03 21:19; `baski-web` Up since 2026-09-03, restarts 0

Не чинилось: TP-Link без NAT loopback. С Wi‑Fi + публичный/DoH DNS пакет на `5.144.98.126` не доезжает до Caddy. Обход: hosts / DNS `192.168.0.6` / `http://192.168.0.6/` / LTE.

Скрин юзера 2026-09-06 12:18 — `showBootError` («Нет связи» + «Повторить»). HTML из SW-кэша, API не доехал. Caddy с `.5` Cursor в те же минуты отдавал `/` + `/api/health` + `/api/tasks` 200 — другой браузер (YaBrowser DoH) бьёт в WAN и висит.

Fix 2026-09-06: любой клиент при мёртвом `/api/health` → `http://192.168.0.6/` (раньше только desktop). `api()` 503/`offline` = `network`. Cache: `app.js?v=72`, `login.js?v=13`, `pwa.js?v=9`, SW `notetask-v24`. Старый SW-кэш фикс не подхватит, пока не открыть LAN.



## Main views full width 2026-09-04 (~01:20 MSK)

- Bug: `.main` имел `max-width: 980px` (~924px контент) + пустой gutter справа. Только `#view-finance` снимал лимит через `.finance-wide`.
- Fix: `.main { max-width: none; min-width: 0 }`; класс `.content-wide` (HTML + `setView`) рядом с `.finance-wide`.
- Views: Сегодня/`#view-tasks`, История, Статистика, разделы (Идеи, Здоровье, Тренировки, Питание, …), Финансы. Sidebar + `.with-section-panel` без изменений (2 колонки).
- Mobile ≤860px: padding 18/14, single column — ок.
- Cache: `styles.css?v=48`, `app.js?v=71`, `pwa.js?v=8`, SW `notetask-v23`.
- Verify 1600px / sidebar 340: `.main` = 1260 (= remaining), `max-width: none`; Идеи `#view-tasks` 1204; Здоровье `with-section-panel` 623+563; История/Финансы 1204.

## Finance sheet work income fix 2026-09-04 (~01:15 MSK)

- Bug report: `#view-finance` income «ДОХОД +0 · работа 0 ₽» при received-платежах в Работа.
- Root cause: summary `/api/finance/sheet` уже считал `work_income` (`sum_work_payment_income`, paid_at month, status≠planned). На **текущем месяце** (2026-09) received=0 — 250k в августе, сентябрьские planned. Панель Работа — все received без фильтра месяца.
- Fix: budget rollup — `work_income` → «Подработка», `task_income` → «Прочие доходы», `task_expense` → «Прочие расходы».
- Tests: `tests/test_finance_income.py` (2 ok).
- Verify: `GET /api/finance/sheet?year_month=2026-08` → income/work 250k, Подработка actual 250k; browser август — карточка +250k, журнал «Снеговики · работа».
- Commit: `6de2c39`. Backend restart. Frontend cache без изменений.

## Finance page full-width budget grid 2026-09-04 (~00:55 MSK)

- **Layout:** `#view-finance` — panel padding 0; `.fin-page-summary` (месяц, баланс, счета) с padding 18px; таблицы бюджета **full bleed** в `.fin-budget-sheet`.
- **CSS:** `.main.finance-wide` снимает `max-width: 980px`; `.fin-budget-table` — spreadsheet grid (border all cells, fixed cols: Статья 46% · План/Факт/Δ по 18%), zebra + hover.
- **JS:** `setView("finance")` → `main.finance-wide`; budget section вынесена из summary wrapper.
- **Google Sheet CSV (gid=0):** экспорт доступен, но вкладка — **реестр проектов** (Проект · Направление · Цена · Месяц · Статус), не шаблон «Статья · План · Факт · Δ». Seed категорий без изменений (типовой «Домашний бюджет» из 820ab20). Другие gid → login HTML.
- Cache: `styles.css?v=47`, `app.js?v=70`, SW `notetask-v22`.

## Task list remind chip 2026-09-04 (~00:50 MSK)

- Bug: `.task-attrs` не показывал напоминание — только composer `#chip-remind`; `remind_at` в БД есть, UI списка нет.
- Fix: chip «Напомн.» (bell) в `renderTaskAttrs` между сроком и местом — popover: `datetime-local`, пресеты (15 мин, 1 ч, за 1 ч до срока, в момент срока), «Без напоминания»; PATCH `{ remind_at }` / `null`.
- Composer `#pop-remind`: те же пресеты.
- Notify без изменений — worker `app/notify.py` уже шлёт по `remind_at`.
- Cache: `app.js?v=69`, SW `notetask-v21`. Verify: task 174, `http://192.168.0.6/`.

## NLP trailing remind 2026-09-04 (~00:45 MSK)

- Trailing keywords in title: `напомнить`, `напомни`, `remind` (end of string only).
- Regex: `(?<![\p{L}\p{N}_])(?:напомнить|напомни|remind)(?=\s*$)` → meta `{ remindAtDue: true }`.
- `resolveRemindLocal(meta, fbDate, fbTime)`: absolute `remindAt` → `remindBeforeMinutes` offset from due → `remindAtDue` at due moment.
- **Default remind:** due date+time from NLP or chip fallback via `dueAtForRemindPreset`; date-only due → 09:00 that day; no due → next 09:00 local.
- Strip keyword from `cleanTitle`; highlight `.hl-remind`. Composer + inline rename use same parser; inline rename reads due chips as fallback.
- Cache: `app.js?v=69`, SW `notetask-v21`.

## Sidebar resize + collapse 2026-09-04 (~00:30 MSK)

- Левое меню `.sidebar`: drag resize правый край (handle `#sidebar-resize`), min 180 / max 400 / default 240 px.
- CSS `--sidebar-width` на `.app-shell`; grid `var(--sidebar-width) 1fr`; collapsed → `0 1fr` (как было).
- localStorage: `notetask_sidebar_width` (число px), `notetask_sidebar_collapsed` (`"1"`/`"0"`).
- Toggle «Скрыть меню» в topbar (`#sidebar-toggle`) — уже был; dblclick на handle → сброс 240px; ArrowLeft/Right на handle ±16px.
- Touch: touchstart/move/end; класс `.sidebar-resizing` отключает transition при drag.
- Mobile ≤860px: handle скрыт, collapse как раньше.
- Cache: `styles.css?v=46`, `app.js?v=68`, SW `notetask-v20`.

## Finance section (full page) 2026-09-04 (~00:20 MSK)

- Google Sheet `1UrEntfxS-y7Ol0c6yUsvVZQcKV6GqxD4VcC4k0rp-cQ` — gid=0 CSV: реестр проектов (не бюджет-шаблон); типовой seed «Домашний бюджет».
- **Sidebar:** кнопка **Финансы** (`data-view="finance"`) — отдельный экран `#view-finance`, не путать с fin-panel в «Личные дела».
- **UI:** месяц ‹›, баланс/доход/расход, счета, таблица бюджета (Статья · План · Факт · Δ), форма операции, журнал (записи + задачи + work payments).
- **DB:** `finance_categories`, `finance_accounts`, `finance_transactions`, `finance_budget` (+ старые `finance_months`).
- **Seed при старте:** 21 категория (Доходы / Обязательные / Быт / Досуг / Прочее / Накопления), 3 счёта (Наличные, Дебетовая карта, Накопительный).
- **API (новое):**
  - `GET /api/finance/sheet?year_month=YYYY-MM` — overview
  - CRUD `/api/finance/categories`, `/accounts`, `/transactions`
  - `PUT /api/finance/budget/{year_month}/{category_id}` — план
  - `POST /api/finance/import-csv` — `{ csv_text, year_month? }` (гибкий парсер колонок)
- **Старое без изменений:** `/api/finance/months/*` — fin-panel «Личные дела» + stats 30d.
- **Импорт таблицы:** Файл → «Опубликовать в интернете» → anyone with link, либо экспорт CSV и POST import-csv. Колонки: категория, сумма/факт, дата, план, тип.
- Cache: `app.js?v=67`, `styles.css?v=45`, SW `notetask-v19`.

## Overdue notify null due_at fix 2026-09-04 (~00:15 MSK)

- Bug: вечерний digest «Просрочено» включал задачи без срока — у digest id=2 (28 задач) были старые `due_at` из Todoist (напр. `2026-08-08`); юзер снял через «Без срока» (~22:00 MSK 2026-09-03).
- Fix: `app/due_utils.py` — `due_at_present`, `parse_task_dt`, `is_task_overdue`; `app/notify.py` — SQL `due_at IS NOT NULL AND TRIM != '' AND date < today` + double-check `is_task_overdue`; due-at notify skip без due.
- Tests: `tests/test_due_overdue.py` (8 ok). Live DB: 31 null due → 0 overdue; 2 с реальным прошлым сроком.
- Backend: `docker compose restart notetask`. Frontend cache не менялся.

## Day group header year 2026-09-04 (~00:10 MSK)

- Task list `.day-group-header` (`formatDayHeader` in `app.js`): добавлен `year: "numeric"` — ru-RU как `monthLabel`, напр. «понедельник, 1 января 2026 г.» (не для «Сегодня»/«Завтра»/«Без срока»).
- Cache: `app.js?v=65`, SW `notetask-v18`.

## Work planned payments 2026-09-04 (~00:05 MSK)

- Раздел **Работа** → панель проекта: платежи `received` | `planned` (колонка `status`, миграция default `received`).
- Прогресс «Получено X из Y» + шкала — только `received`; в summary «· план Z» если есть planned.
- UI: чекбокс **План** в форме (+ авто-галка если дата > сегодня); строка с badge «План»; ✓ → PATCH `status: received`.
- API: POST `{ status }`; PATCH `/api/work-projects/{id}/payments/{pid}`; DELETE без изменений.
- Cache: `app.js?v=65`, `styles.css?v=44`, SW `notetask-v18`.

## Finance income from work payments 2026-09-03 (~23:58 MSK)

- Bug: fin-panel `.fin-split-card.income` (ДОХОД) = +0 ₽ — игнорировал `work_project_payments`.
- Fix: backend `/api/finance/months/*` + `/api/stats` — `work_income` из received-платежей (`status != planned`); операции включают work_payment entries.
- Cache: `app.js?v=65`, SW `notetask-v18`.

## Due chip popover fix 2026-09-03 (~23:50 MSK)

- Bug: task list due chip popover closed on first click in `input[type=date|time]` (manual edit / native picker retarget).
- Cause: document `click` outside-handler ran before input focus; some browsers report wrong `event.target` for date/time controls.
- Fix: `chipPopoverRoot()` helper + deferred close (`setTimeout(0)`) skips close when `document.activeElement` still inside `.chip-menu`.
- Cache: `app.js?v=64`, SW `notetask-v17`.

## Health hair region 2026-09-03 (~22:45 MSK)

- Карта тела: зона `forehead` / «Лоб» заменена на `hair` / «Волосы» (SVG ellipse выше головы).
- Backend `HEALTH_REGION_IDS`: `hair` вместо `forehead`.
- DB migrate: `health_body` + `health_body_notes` `forehead` → `hair`.
- Cache: `app.js?v=63`, SW `notetask-v16`. Playwright: клик → label «Волосы».

## Health unknown status + notes 2026-09-03 (~22:25 MSK)

- Статус зоны: `ok` / `warn` / `bad` / `unknown` (Неизвестно). Карта: `.region.unknown` серый пунктир.
- Заметки зоны — таблица `health_body_notes`; старая `health_body.note` мигрирует в первую запись.
- API: `POST/DELETE /api/health-body/{region}/notes/{id}`; статус PUT без `note` не затирает журнал.
- UI: select автосейв; список заметок + «Добавить заметку». Cache `app.js?v=62`, `styles.css?v=43`, SW `notetask-v15`.

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
- **Sidebar:** кнопка «←» в topbar — сворачивает меню, состояние в `localStorage` (`notetask_sidebar_collapsed`); drag resize правого края, ширина в `notetask_sidebar_width` (180–400px, CSS `--sidebar-width`)
- **Плашка задачи:** под каждой задачей чипы — раздел, P, срок/время, **напоминание**, место, сумма (расход/доход)
- **Финансы:** суммы в задачах; сводка в «Статистика» — расходы/доходы/баланс за 30д + список операций; **полный раздел «Финансы»** в sidebar — бюджет/счета/операции (`/api/finance/sheet`)
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
