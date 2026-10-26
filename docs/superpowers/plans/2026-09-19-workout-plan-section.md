# Workout Plan Section Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Training full page (A/B/C queue + calendar slots, session log with last weights, one muted media + muscle chips per exercise) and seed three sport Goals trees; leave #161/#163 hourly tasks untouched.

**Architecture:** New `app/workouts.py` router (schema ensure, seed, plan GET, media, session create that advances `next_code`). `app/main.py` only registers the router and extends `WorkoutIn` / `create_workout`. Frontend: `#view-workouts` becomes the Тренировки project screen. Goals seed uses existing `goals` / `goal_nodes` / `goal_edges` tables.

**Tech Stack:** FastAPI, aiosqlite, vanilla JS, HTML5 `<img>` / `<video muted autoplay loop playsinline>`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-09-19-workout-plan-section-design.md`
- Do not change tasks #161 / #163 / hourly reminds.
- Do not drop `workout_goals` table; remove it from Training UI only.
- Do not touch live Goals tab «Создать канала на 1к подписчиков в ТГ».
- Slot weekdays stored as JS `Date.getDay()`: 0=Sun … 6=Sat. Default `[1,3,5]` (Mon/Wed/Fri).
- `next_code` cycles A→B→C→A only when an A/B/C session is logged. Home `H` never advances it.
- One media file per exercise: `data/workout-media/{id}.{ext}`. Image/gif ≤ 8_000_000 bytes, video ≤ 25_000_000. GET requires auth.
- Host Python 3.14 cannot import real fastapi/pydantic: helper tests use the stub pattern in `tests/test_finance_ledger.py`. Run those on host. Docker `notetask` for anything that needs the real app.
- Conventional commits, English messages. No `git config`. Do not mix finance ledger files into these commits.
- Branch: `feat/workout-plan-section` from current HEAD. Do not commit already-staged finance files.
- Cache bump when shipping front: `styles.css?v=59`, `app.js?v=84`, `pwa.js?v=16`, `sw.js` `notetask-v32` / `?v=32` (from current 58 / 83 / 15 / v31).
- No new npm libraries.

## File map

- Create: `app/workouts.py` — constants, helpers, ensure+seed, router
- Create: `tests/test_workout_plan.py` — helpers + seed + queue (aiosqlite, stubs)
- Create: `tests/test_workout_media.py` — mime/size helpers
- Create: `data/workout-media/.gitkeep` (if missing)
- Modify: `app/db.py` — call `ensure_workout_plan` from `ensure_defaults`
- Modify: `app/main.py` — `WorkoutIn.day_code` / `exercise_id` on sets; register router; `create_workout` advances queue
- Modify: `app/config.py` only if a `WORKOUT_MEDIA_DIR` constant is cleaner (`DATA_DIR / "workout-media"`)
- Modify: `static/index.html` — replace `#view-workouts` body; cache query
- Modify: `static/app.js` — Тренировки → workout view, not task list + panel
- Modify: `static/styles.css` — cards gif-left
- Modify: `static/sw.js`, `static/pwa.js` — cache name
- Modify: `.gitignore` — `data/workout-media/*` with gitkeep exception

---

### Task 1: Helpers + schema ensure (no seed data yet)

**Files:**
- Create: `app/workouts.py`
- Create: `tests/test_workout_plan.py`
- Modify: `app/db.py` (`ensure_defaults` call at end of migrations, before return)
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `app.db.ensure_column`, `utcnow`, `DATA_DIR`
- Produces:
  - `MUSCLE_KEYS: frozenset[str]`
  - `MUSCLE_LABELS: dict[str, str]`
  - `next_letter(code: str) -> str`
  - `parse_slot_weekdays(raw: str | None) -> list[int]`
  - `validate_muscles(keys: list[str]) -> list[str]`  # raises ValueError
  - `media_kind_for_mime(mime: str) -> str`  # `image` | `gif` | `video`; ValueError
  - `media_max_bytes(mime: str) -> int`
  - `WORKOUT_MEDIA_DIR: Path`
  - `async def ensure_workout_tables(db) -> None`

- [ ] **Step 1: Write failing tests** in `tests/test_workout_plan.py` using the fastapi/pydantic stub copy from `tests/test_finance_ledger.py` `_install_import_stubs()`, then:

```python
from app.workouts import (
    MUSCLE_KEYS,
    media_kind_for_mime,
    media_max_bytes,
    next_letter,
    parse_slot_weekdays,
    validate_muscles,
)

class NextLetterTests(unittest.TestCase):
    def test_cycle(self):
        self.assertEqual(next_letter("A"), "B")
        self.assertEqual(next_letter("B"), "C")
        self.assertEqual(next_letter("C"), "A")

    def test_home_does_not_rotate(self):
        self.assertEqual(next_letter("H"), "H")

    def test_bad_raises(self):
        with self.assertRaises(ValueError):
            next_letter("X")

class MuscleTests(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(validate_muscles(["chest", "triceps"]), ["chest", "triceps"])

    def test_unknown(self):
        with self.assertRaises(ValueError):
            validate_muscles(["wings"])

class MediaHelperTests(unittest.TestCase):
    def test_gif(self):
        self.assertEqual(media_kind_for_mime("image/gif"), "gif")
        self.assertEqual(media_max_bytes("image/gif"), 8_000_000)

    def test_mp4(self):
        self.assertEqual(media_kind_for_mime("video/mp4"), "video")
        self.assertEqual(media_max_bytes("video/mp4"), 25_000_000)

    def test_bad_mime(self):
        with self.assertRaises(ValueError):
            media_kind_for_mime("application/pdf")

class SlotParseTests(unittest.TestCase):
    def test_default(self):
        self.assertEqual(parse_slot_weekdays(None), [1, 3, 5])

    def test_json(self):
        self.assertEqual(parse_slot_weekdays("[1,3,5,0]"), [1, 3, 5, 0])
```

- [ ] **Step 2: Run tests, expect fail** (import error)

```bash
cd /home/kon/Projects/notetask
python -m unittest tests.test_workout_plan -v
```

Expected: `ModuleNotFoundError: app.workouts` or similar.

- [ ] **Step 3: Implement `app/workouts.py` helpers + `ensure_workout_tables`**

Constants and helpers (exact):

```python
MUSCLE_LABELS = {
    "chest": "грудь",
    "front_delt": "передняя дельта",
    "side_delt": "средняя дельта",
    "rear_delt": "задняя дельта",
    "triceps": "трицепс",
    "biceps": "бицепс",
    "forearm": "предплечье",
    "lats": "широчайшие",
    "upper_back": "верх спины",
    "traps": "трапеции",
    "abs": "пресс",
    "obliques": "косые",
    "quads": "квадрицепс",
    "hamstrings": "бицепс бедра",
    "glutes": "ягодицы",
    "calves": "икры",
    "adductors": "приводящие",
    "lower_back": "поясница",
    "cardio": "кардио",
}
MUSCLE_KEYS = frozenset(MUSCLE_LABELS)
IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
VIDEO_MIMES = {"video/mp4", "video/webm"}
IMAGE_MAX = 8_000_000
VIDEO_MAX = 25_000_000
DEFAULT_SLOTS = [1, 3, 5]
GYM_CODES = ("A", "B", "C")
```

`next_letter`: if `H` return `H`; if in GYM_CODES return next in cycle; else `ValueError`.

`validate_muscles`: every key in `MUSCLE_KEYS` or `ValueError("unknown muscle")`.

`media_kind_for_mime`: gif → `gif`; other IMAGE_MIMES → `image`; VIDEO_MIMES → `video`; else `ValueError`.

`parse_slot_weekdays`: None/blank → `DEFAULT_SLOTS`; `json.loads`; each int 0..6 unique keep order.

`ensure_workout_tables`: CREATE the five new tables from the spec; `ensure_column` on `workout_sessions.day_code`, `workout_sessions.program_id`, `workout_sets.exercise_id`; `WORKOUT_MEDIA_DIR.mkdir(parents=True, exist_ok=True)`. No seed in this task.

Call `await ensure_workout_tables(db)` from `ensure_defaults` in `app/db.py`.

`.gitignore`:

```
data/workout-media/*
!data/workout-media/.gitkeep
```

- [ ] **Step 4: Re-run tests, expect PASS**

```bash
python -m unittest tests.test_workout_plan -v
```

- [ ] **Step 5: Commit** (workout files only)

```bash
git add app/workouts.py tests/test_workout_plan.py app/db.py .gitignore data/workout-media/.gitkeep
git commit -m "$(cat <<'EOF'
feat(workout): schema helpers for plan queue and media

EOF
)"
```

---

### Task 2: Seed program + GET /api/workout-plan

**Files:**
- Modify: `app/workouts.py`
- Modify: `app/main.py` (`app.include_router`)
- Modify: `tests/test_workout_plan.py`

**Interfaces:**
- Consumes: Task 1 tables
- Produces:
  - `async def seed_workout_program(db) -> None` idempotent
  - `async def get_plan_payload(db) -> dict`
  - Router `GET /api/workout-plan`
  - `SEED_EXERCISES` / day items as specified below

- [ ] **Step 1: Failing tests** (aiosqlite memory + `ensure_workout_tables` + `seed_workout_program` twice)

```python
class SeedPlanTests(unittest.IsolatedAsyncioTestCase):
    async def test_seed_idempotent_abc_h(self):
        db = await aiosqlite.connect(":memory:")
        db.row_factory = aiosqlite.Row
        await ensure_workout_tables(db)
        await seed_workout_program(db)
        await seed_workout_program(db)
        cur = await db.execute("SELECT code FROM workout_days ORDER BY sort")
        codes = [r[0] for r in await cur.fetchall()]
        self.assertEqual(codes, ["A", "B", "C", "H"])
        cur = await db.execute("SELECT next_code, slot_weekdays_json FROM workout_plan_state WHERE id=1")
        row = await cur.fetchone()
        self.assertEqual(row["next_code"], "A")
        self.assertEqual(json.loads(row["slot_weekdays_json"]), [1, 3, 5])
        cur = await db.execute("SELECT COUNT(*) FROM workout_programs")
        self.assertEqual((await cur.fetchone())[0], 1)
        await db.close()
```

Also assert day A has 5 items (escalator + 4 lifts). Escalator name: `Эскалатор 15 мин`.

- [ ] **Step 2: Run, expect FAIL** (`seed_workout_program` missing)

- [ ] **Step 3: Implement seed + GET**

Seed exercises (create if no live row with same `name`):

| name | muscles |
|---|---|
| Эскалатор 15 мин | cardio |
| Жим лёжа | chest, triceps, front_delt |
| Присед | quads, glutes, hamstrings |
| Подтягивания | lats, biceps, upper_back |
| Тяга в наклоне | lats, upper_back, biceps |
| Жим стоя | front_delt, triceps |
| Румынская тяга | hamstrings, glutes, lower_back |
| Жим ногами | quads, glutes |
| Тяга верхнего блока | lats, biceps |
| Планка | abs |
| Отжимания | chest, triceps, front_delt |
| Пресс | abs |

Days (sets, reps_low, reps_high, notes):

- A: Эскалатор 1×15–15 note `скорость 6–7` · Жим лёжа 3×5–8 · Присед 3×5–5 note `старт 80 кг` · Подтягивания 4×1–5 · Тяга в наклоне 3×8–12
- B: Эскалатор · Жим лёжа 3×5–5 note `−10% от A, больше RIR` · Жим стоя 3×5–8 · Румынская тяга 3×8–8 · Подтягивания 4×1–5
- C: Эскалатор · Жим лёжа 3×8–10 note `−10% от A` · Жим ногами 3×8–12 · Подтягивания 4×1–5 · Тяга верхнего блока 3×10–12
- H: Планка 3×60–120 · Отжимания 3×8–30 · Пресс 2×10–15

`workout_plan_state` insert `id=1, next_code=A, slot_weekdays_json='[1,3,5]'` if missing.

`GET /api/workout-plan` JSON:

```python
{
  "program": {...},
  "state": {"next_code": "A", "slot_weekdays": [1, 3, 5]},
  "days": [
    {
      "code": "A",
      "title": "День A",
      "items": [
        {
          "id": 1,
          "sort": 0,
          "sets": 3,
          "reps_low": 5,
          "reps_high": 8,
          "notes": "",
          "exercise": {
            "id": 2,
            "name": "Жим лёжа",
            "muscles": ["chest", "triceps", "front_delt"],
            "media_mime": None,
            "media_ext": None,
            "has_media": False,
          },
        }
      ],
    }
  ],
  "recent": [],  # last 8 sessions: id, title, day_code, started_at, sets_count
  "last_sets": {"2": {"weight": 80, "reps": 5}},  # exercise_id -> last logged working set
}
```

`has_media` true when `media_ext` is not null.

Register: `from .workouts import router as workout_plan_router` and `app.include_router(workout_plan_router)` in `app/main.py`. Also call `seed_workout_program` from `ensure_workout_tables` after tables exist (or from `ensure_defaults` after tables).

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(workout): seed A/B/C/H program and plan API

EOF
)"
```

---

### Task 3: Log session advances queue

**Files:**
- Modify: `app/main.py` `WorkoutIn`, `WorkoutSetIn`, `create_workout`
- Modify: `app/workouts.py` (`advance_next_code`)
- Modify: `tests/test_workout_plan.py`

**Interfaces:**
- Consumes: `workout_plan_state.next_code`
- Produces: `async def advance_next_code(db, day_code: str | None) -> str | None` — if code in A/B/C, set state to `next_letter(code)`, return new code; `H` or None: no-op return current

- [ ] **Step 1: Failing test**

```python
class QueueAdvanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_log_a_goes_to_b(self):
        db = await aiosqlite.connect(":memory:")
        db.row_factory = aiosqlite.Row
        await ensure_workout_tables(db)
        await seed_workout_program(db)
        await advance_next_code(db, "A")
        cur = await db.execute("SELECT next_code FROM workout_plan_state WHERE id=1")
        self.assertEqual((await cur.fetchone())[0], "B")
        await advance_next_code(db, None)
        cur = await db.execute("SELECT next_code FROM workout_plan_state WHERE id=1")
        self.assertEqual((await cur.fetchone())[0], "B")
        await db.close()
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Implement**

`WorkoutIn` add `day_code: str | None = None`. `WorkoutSetIn` add `exercise_id: int | None = None`.

`create_workout`: INSERT session with `day_code` and active `program_id`; INSERT sets with `exercise_id`; if `day_code` in A/B/C call `advance_next_code`. Existing clients with no `day_code` keep old behavior (no queue move).

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit** `feat(workout): advance A/B/C queue on session log`

---

### Task 4: Exercise media PUT/GET/DELETE

**Files:**
- Modify: `app/workouts.py`
- Create: `tests/test_workout_media.py` (helpers already in Task 1; add `ext_for_mime`, `assert_media_size`)

**Interfaces:**
- Produces:
  - `ext_for_mime("image/gif") == "gif"`, jpeg→`jpg`, png→`png`, webp→`webp`, mp4→`mp4`, webm→`webm`
  - `PUT /api/workout-exercises/{id}/media` multipart `file`
  - `GET /api/workout-exercises/{id}/media` `FileResponse` + `Content-Type`
  - `DELETE /api/workout-exercises/{id}/media`
  - `PATCH /api/workout-exercises/{id}` `{ name?, muscles? }`

- [ ] **Step 1: Tests for `ext_for_mime` and size check function `check_media_bytes(mime, n) -> None` raising a small `MediaError` with `.status` 413/415**

```python
def test_too_big_gif():
    with self.assertRaises(MediaError) as ctx:
        check_media_bytes("image/gif", 8_000_001)
    self.assertEqual(ctx.exception.status, 413)
```

- [ ] **Step 2: FAIL then implement helpers**

- [ ] **Step 3: Router**

PUT: auth, read file, `mime = file.content_type`, `check_media_bytes`, write `WORKOUT_MEDIA_DIR / f"{id}.{ext}"`, delete previous ext if changed, UPDATE `media_mime`, `media_ext`.

GET: 404 if no media; `FileResponse`; `require_auth` (401 without token).

DELETE: unlink file if exists, null mime/ext.

Do not mount `workout-media` as public StaticFiles.

- [ ] **Step 4: PASS helper tests. Manual/docker: PUT tiny gif, GET 200, GET without token 401.**

In container after restart:

```bash
docker compose -f /home/kon/Projects/notetask/docker-compose.yml exec -T notetask python -m unittest tests.test_workout_plan tests.test_workout_media -v
```

- [ ] **Step 5: Commit** `feat(workout): authenticated exercise media upload`

---

### Task 5: Seed three Goals trees

**Files:**
- Modify: `app/workouts.py` (`seed_sport_goals`)
- Modify: `app/db.py` or workouts ensure to call it after `ensure_goals_tables`
- Modify: `tests/test_workout_plan.py`

**Interfaces:**
- Consumes: `goals`, `goal_nodes`, `goal_edges`, `app.goals.persist_recomputed`
- Produces: `SPORT_GOAL_CHAINS: list[tuple[str, list[str]]]`

Exact chains:

```python
SPORT_GOAL_CHAINS = [
    (
        "Подтягивание прямым хватом",
        ["Вис 20с", "Негатив 5с × 3", "1 повтор", "3 чистых", "5×5"],
    ),
    (
        "Жим 100 кг",
        ["Первая сессия жима", "40 кг × 8", "60 кг × 5", "80 кг × 5", "90 кг × 3", "100 кг × 1"],
    ),
    (
        "Сушка 88 кг",
        ["4 недели по 3 зала", "Планка 90с", "Вес 88 кг"],
    ),
]
```

For each title: if live `goals.title` exists, skip. Else insert goal, root node title=goal title status open sort 0, then each step as child of previous (root first parent of first step). Call `persist_recomputed`.

- [ ] **Step 1: Test** memory DB with goals tables from `ensure_goals_tables`, seed twice, count live goals with those three titles == 3. Insert dummy «Создать канала на 1к подписчиков в ТГ» first; after seed its node count unchanged.

- [ ] **Step 2: FAIL, implement, PASS**

- [ ] **Step 3: Commit** `feat(goals): seed pull-up bench and cut trees`

Call `seed_sport_goals` from lifespan/`ensure_defaults` **after** `ensure_goals_tables`.

---

### Task 6: Training page UI

**Files:**
- Modify: `static/index.html` `#view-workouts`
- Modify: `static/app.js`
- Modify: `static/styles.css`
- Modify: `static/sw.js`, `static/pwa.js`, `static/index.html` cache queries (this task ships the front — bump here)

**Interfaces:**
- Consumes: `GET /api/workout-plan`, `POST /api/workouts`, media GET with `Authorization` (blob URL)
- Produces: `loadWorkoutPage()`, `renderWorkoutPage(data)`, `isWorkoutProject()`

- [ ] **Step 1: HTML** replace `#view-workouts` inner with:

```html
<section id="view-workouts" class="panel hidden">
  <div id="wo-plan-root"></div>
</section>
```

Keep a hidden unused form only if existing listeners crash — better: update listeners in the same task. Current `$("workout-form")` / `$("wo-add-set")` must be removed or guarded (`if ($("workout-form"))`).

- [ ] **Step 2: `setView`**

When `view === "project"` and project name is `Тренировки`:

- hide `#view-tasks`, show `#view-workouts`
- `hideSectionPanel()`
- `main.classList.add("content-wide")` (already)
- `refresh` → `loadWorkoutPage()` not `loadTasks`

Do **not** call `renderWorkoutPanel`. Remove `workout` from `SECTION_PANELS` (or leave mapping unused).

`loadWorkoutPage`: `api("/api/workout-plan")` then render.

- [ ] **Step 3: Render**

Header: `Следующая: {next_code}` + week strip of 7 days; mark slots; today highlight; button `Начать {next_code}`.

Active session UI: list `days` matching `next_code` (or H if user on non-slot and we still show home reference below). Spec: gym start always `next_code` even off-slot.

Each item card (gif left):

```html
<article class="wo-ex-card" data-exercise-id="…">
  <div class="wo-ex-media"><!-- img or video or + медиа --></div>
  <div class="wo-ex-body">
    <strong>Жим лёжа</strong>
    <div class="wo-muscles">грудь · трицепс · передняя дельта</div>
    <div>3×5–8 · прошлый 80×5</div>
    <div class="wo-set-log"><!-- sets inputs weight/reps --></div>
  </div>
</article>
```

Media: if `has_media`, `fetch` `/api/workout-exercises/{id}/media` with same `api()` token, `blob:` URL into `img` (gif/image) or `video muted autoplay loop playsinline`. No sound. File input on catalog / on empty media: `PUT` FormData field `file`.

Home block: if today `getDay()` not in `slot_weekdays`, show day H list **reference only** (no required log). Never PATCH tasks 161/163.

Submit: `POST /api/workouts` `{ title: "День A", day_code: "A", sets: [{exercise, exercise_id, weight, reps, set_index}] }`.

Catalog: simple list of exercises + file picker. No Boostcamp week editor.

- [ ] **Step 4: CSS** `.wo-ex-card { display:flex; gap:12px; }` media ~140px wide, object-fit cover. Muscle chips muted text.

- [ ] **Step 5: Cache bump** `styles.css?v=59` `app.js?v=84` `pwa.js?v=16` `sw.js` CACHE `notetask-v32` register `sw.js?v=32`

- [ ] **Step 6: Commit** `feat(web): Training page with muted exercise media`

---

### Task 7: Browser verify + context

**Files:** `context/context.md`

- [ ] Restart `docker compose up -d --build` in `/home/kon/Projects/notetask` (code is bind-mounted? if `app/` mounted, restart enough; if image copy, `--build`).
- [ ] Open Тренировки: **not** the old task list as main; A/B/C header visible; no right `workout_goals` panel.
- [ ] Сегодня still shows #161 / #163 hourly chips unchanged.
- [ ] Цели: three new tabs plus existing TG; open pull-up tree chain.
- [ ] Log a fake A session (light weights): `next_code` becomes B after reload.
- [ ] Attach a small gif to «Жим лёжа»: autoplay mute in card, no extra click needed to see motion.
- [ ] Update `context/context.md` with shipped cache versions and branch name.
- [ ] Commit `docs(context): workout plan section shipped` only if context is the remaining file.

---

## Spec coverage

| Spec section | Task |
|---|---|
| Queue + calendar / next_code | 1, 3, 6 |
| Seed v2 A/B/C/H | 2 |
| Media 8/25MB auth GET | 4, 6 |
| Muscles chips | 1, 2, 6 |
| Goals three trees, skip TG | 5 |
| Full page `#view-workouts`, hide panel | 6 |
| Keep #161/#163 | 6 (explicit no writes) |
| Tests listed in spec | 1–5 |
| Cache bump | 6 |

## Out of scope (do not implement)

YouTube, multi-media, auto goal complete from kg, changing hourly tasks, Boostcamp 12-week editor, Fitbod generator.
