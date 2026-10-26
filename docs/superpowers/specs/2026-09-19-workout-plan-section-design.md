# Workout plan + Training section + sport Goals

Date: 2026-09-19  
Status: approved (user: write implementation plan)

## Goal

Раздел **Тренировки** — экран плана и лога (очередь A/B/C + календарные слоты). У упражнения одно mute-медиа (гиф/видео/картинка) сразу видно, плюс мышцы. Спортивные цели живут во вкладках **Цели**, не в панели `workout_goals`.

## Locked decisions

- Plan **v2**: 3–4 зала, пропуск сдвигает букву. Жим каждый зал (тяжёлый / лёгкий / объём). Эскалатор 15 мин скорость 6–7. Дом: планка, отжимания, пресс. Файл: `context/workout-plan-draft.md`.
- Календарь + очередь вместе. Пропуск ≠ потеря дня.
- Медиа **на упражнение** в каталоге, не на день.
- В зале: **без лишнего клика**, **без звука**, видно движение и мышцы. Карточка: **гиф слева**, лог справа.
- Одно медиа на упражнение (gif / image / muted video).
- Цели зала **не** в правой панели Тренировок. Три новых вкладки в **Цели** (`context/workout-goals-trees.md`). Вкладка «канал 1к ТГ» не трогать.
- Якорь сушки: **88 кг**. «Пресс виден» на 88 не обещаем.
- Кардио отдельной целью нет — эскалатор в каждой сессии.
- Задачи **#161 Отжиматься** и **#163 Планка** (+ hourly) **оставить как есть**. План рядом, не заменяет их.
- `#view-workouts` оживить как полную страницу (как Финансы). Клик по разделу Тренировки открывает её, не список задач. Задачи раздела по-прежнему в **Сегодня**.
- Правая панель `workout_goals` на Тренировках убрать. Таблицу не дропать.
- Авто-complete узлов Целей из жима/подтягиваний в логе — **не v1** (ручная галочка / связь с задачей как сейчас).

## Current

- Проект Тренировки: список задач + панель цели/счётчики/recent.
- `#view-workouts` в HTML есть, `setView` всегда `hidden`, `loadWorkouts()` нигде не зовётся.
- `workout_sessions` + `workout_sets(exercise text, weight, reps)`. Одна живая сессия: «Ноги» присед 80×5.
- Загрузка файлов в приложении нет (кроме `data/downloads/` для клиентов).

## Training UI

1. Шапка: буква **следующей** сессии, ближайший слот, кнопка «Начать A/B/C».
2. Полоска недели: целевые дни (дефолт пн/ср/пт, 4-й слот можно включить). Пропущенный слот без сессии — буква не крутится.
3. Сессия: эскалатор первой строкой (можно без медиа), дальше 4 упражнения дня. Карточка: превью слева (autoplay loop muted playsInline), название, чипы мышц, цель подходов, прошлые кг×повт, поля лога.
4. Не слот зала: блок «дом» из плана (планка / отжимания / пресс) **справочно**. #161/#163 не удалять и не переписывать.
5. Каталог упражнений: имя, мышцы, одно медиа (файл). Журнал сессий ниже или отдельный подэкран.
6. Старт сессии копирует состав дня + подставляет прошлые рабочие веса этого упражнения.

## Queue + calendar

- Состояние: `next_code` ∈ {A,B,C}, `slot_weekdays` JSON, например `[1,3,5]` (пн=0 или пн=1 — зафиксировать **пн=0** как `Date.getDay()` в JS: вс=0… сб=6; слоты хранить как JS `getDay()`).
- Сегодня слот **или** пользователь жмёт «Начать» в любой день → открывается `next_code`.
- Успешный лог сессии A/B/C → `next_code` = следующая буква.
- Слот прошёл, сессии нет → `next_code` не менять (сдвиг).
- День H (дом) в очередь не входит.

## Seed program (v2)

Каждый зал: эскалатор 15 мин, затем:

**A:** жим лёжа 3×5–8 · присед 3×5 · подтягивания 3–4 · тяга в наклоне 3×8–12  
**B:** жим лёжа лёгкий 3×5 (−10%, больше RIR) · жим стоя 3×5–8 · румынская тяга 3×8 · подтягивания 3–4  
**C:** жим лёжа 3×8–10 (−10%) · жим ногами 3×8–12 · подтягивания 3–4 · тяга верхнего блока 3×10–12  

Прогрессия: все рабочие подходы верх диапазона → +2.5 кг в следующий такой же день. Стоп 2–3 RIR. Присед старт 80 кг.

Дом (справочно, не очередь): планка 2–3× от 60с; отжимания 3× с RIR; пресс 2×10–15. В день зала в этом блоке отжимания не подсвечивать.

Медиа у seed-упражнений пустые — пользователь вешает гифки сам.

## Media

- Файл в `data/workout-media/{exercise_id}.{ext}`. Не в git.
- Типы: `image/jpeg|png|webp|gif`, `video/mp4|webm`.
- Лимит: изображение/гиф 8 МБ, видео 25 МБ. Иначе 413.
- GET медиа только с auth (как API), не публичный StaticFiles без токена.
- UI: `<img>` для фото/гиф; `<video muted autoplay loop playsinline>` для видео. Звук не включать. Клик опционально на полный кадр, **не обязателен** чтобы понять движение.
- Замена = overwrite одного слота. Удаление = файл + поле NULL.

## Muscles

Фиксированный список ключей (RU лейбл в UI):

`chest`, `front_delt`, `side_delt`, `rear_delt`, `triceps`, `biceps`, `forearm`, `lats`, `upper_back`, `traps`, `abs`, `obliques`, `quads`, `hamstrings`, `glutes`, `calves`, `adductors`, `lower_back`, `cardio`

У упражнения массив ключей, чипы под названием. Карту тела Здоровья не трогать.

## Goals seed

Существующий API Целей. Если нет живой цели с таким title — создать дерево (корень = title, дети цепочкой, все родители по одному).

1. **Подтягивание прямым хватом:** вис 20с → негатив 5с×3 → 1 повтор → 3 чистых → 5×5  
2. **Жим 100 кг:** первая сессия жима → 40×8 → 60×5 → 80×5 → 90×3 → 100×1  
3. **Сушка 88 кг:** 4 недели по ≥3 зала → планка 90с → вес 88 кг  

Идемпотентный seed по title. Complete вручную. Smoke/удалённые не воскрешать. ТГ-канал не менять.

## Data

- `workout_exercises(id, name, muscles_json, media_mime, media_ext, deleted_at, created_at, updated_at)`
- `workout_programs(id, title, status, created_at, updated_at)` — v1 одна active
- `workout_days(id, program_id, code, title, sort)` — A,B,C,H
- `workout_day_items(id, day_id, exercise_id, sort, sets, reps_low, reps_high, notes)`
- `workout_plan_state(id INTEGER PK CHECK (id=1), next_code, slot_weekdays_json, updated_at)`
- `workout_sessions`: колонки `day_code`, `program_id` nullable (старые сессии ок)
- `workout_sets`: колонка `exercise_id` nullable; `exercise` text оставить для старых строк

## API (новые)

- `GET /api/workout-plan` — program, days, items, exercises (без байт файла), state, recent sessions
- `PATCH /api/workout-plan/state` — `next_code`, `slot_weekdays`
- `POST /api/workouts` — как сейчас + `day_code`; крутит `next_code` если code A/B/C
- `GET/POST/PATCH /api/workout-exercises`
- `PUT /api/workout-exercises/{id}/media` multipart field `file`
- `GET /api/workout-exercises/{id}/media` — file stream, auth
- `DELETE /api/workout-exercises/{id}/media`

Старые `GET/POST/DELETE /api/workouts` и `workout-goals` не ломать; UI целей зала не показывать.

## Errors

- 413 oversized media
- 415 wrong mime
- 409 duplicate live exercise name
- 400 unknown muscle key / bad day_code
- Нет файла медиа → превью-заглушка «+ медиа», лог не блокировать

## Tests

- Seed: A/B/C/H, next_code A, 88/подтягивание/жим деревья идемпотентны
- Complete session A → next B; второй A не создаётся из сдвига без лога
- Media PUT gif → GET 200 auth; без токена 401
- 413 over 8MB image
- Goals seed не дублирует title, не трогает ТГ-цель

## Out of scope (v1)

Fitbod-генератор, YouTube-embed, несколько медиа на упражнение, авто-узлы Целей из кг в логе, смена #161/#163, HIIT/бассейн как обязаловка, правка состава A/B/C сложным редактором недель (достаточно seed + правка каталога/медиа). Редактор состава дня: простой (порядок, подходы) ок; Boostcamp-на-12-недель нет.

## Impact

- Frontend: `setView` для проекта Тренировки → `#view-workouts`; `app.js` / `styles.css` / cache bump. `goals.js` только если seed с бэка, UI дерева уже есть.
- Backend: новый модуль `app/workouts.py` (не раздувать `main.py`), migrate в `db.py`.
- Диск: `data/workout-media/` в `.gitignore` как `data/downloads/`.
- Здоровье / Финансы / задачи Сегодня: без ломания. Hourly #161/#163 без изменений.
