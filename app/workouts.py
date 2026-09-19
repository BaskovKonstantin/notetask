"""Workout plan helpers, schema ensure, seed, and GET /api/workout-plan."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .auth import require_auth
from .config import DATA_DIR

if TYPE_CHECKING:
    import aiosqlite

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
EXT_BY_MIME = {
    "image/gif": "gif",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "video/mp4": "mp4",
    "video/webm": "webm",
}
IMAGE_MAX = 8_000_000
VIDEO_MAX = 25_000_000
DEFAULT_SLOTS = [1, 3, 5]
GYM_CODES = ("A", "B", "C")

WORKOUT_MEDIA_DIR: Path = DATA_DIR / "workout-media"
PROGRAM_TITLE = "Силовой план"

SPORT_GOAL_CHAINS: list[tuple[str, list[str]]] = [
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

SEED_EXERCISES: list[tuple[str, list[str]]] = [
    ("Эскалатор 15 мин", ["cardio"]),
    ("Жим лёжа", ["chest", "triceps", "front_delt"]),
    ("Присед", ["quads", "glutes", "hamstrings"]),
    ("Подтягивания", ["lats", "biceps", "upper_back"]),
    ("Тяга в наклоне", ["lats", "upper_back", "biceps"]),
    ("Жим стоя", ["front_delt", "triceps"]),
    ("Румынская тяга", ["hamstrings", "glutes", "lower_back"]),
    ("Жим ногами", ["quads", "glutes"]),
    ("Тяга верхнего блока", ["lats", "biceps"]),
    ("Планка", ["abs"]),
    ("Отжимания", ["chest", "triceps", "front_delt"]),
    ("Пресс", ["abs"]),
]

# (exercise name, sets, reps_low, reps_high, notes)
SEED_DAYS: list[dict[str, Any]] = [
    {
        "code": "A",
        "title": "День A",
        "sort": 0,
        "items": [
            ("Эскалатор 15 мин", 1, 15, 15, "скорость 6–7"),
            ("Жим лёжа", 3, 5, 8, ""),
            ("Присед", 3, 5, 5, "старт 80 кг"),
            ("Подтягивания", 4, 1, 5, ""),
            ("Тяга в наклоне", 3, 8, 12, ""),
        ],
    },
    {
        "code": "B",
        "title": "День B",
        "sort": 1,
        "items": [
            ("Эскалатор 15 мин", 1, 15, 15, "скорость 6–7"),
            ("Жим лёжа", 3, 5, 5, "−10% от A, больше RIR"),
            ("Жим стоя", 3, 5, 8, ""),
            ("Румынская тяга", 3, 8, 8, ""),
            ("Подтягивания", 4, 1, 5, ""),
        ],
    },
    {
        "code": "C",
        "title": "День C",
        "sort": 2,
        "items": [
            ("Эскалатор 15 мин", 1, 15, 15, "скорость 6–7"),
            ("Жим лёжа", 3, 8, 10, "−10% от A"),
            ("Жим ногами", 3, 8, 12, ""),
            ("Подтягивания", 4, 1, 5, ""),
            ("Тяга верхнего блока", 3, 10, 12, ""),
        ],
    },
    {
        "code": "H",
        "title": "День H",
        "sort": 3,
        "items": [
            ("Планка", 3, 60, 120, ""),
            ("Отжимания", 3, 8, 30, ""),
            ("Пресс", 2, 10, 15, ""),
        ],
    },
]

router = APIRouter()


class MediaError(Exception):
    def __init__(self, status: int, detail: str = "") -> None:
        self.status = status
        self.detail = detail
        super().__init__(detail)


class ExercisePatchIn(BaseModel):
    name: str | None = None
    muscles: list[str] | None = None


async def _workout_db() -> AsyncGenerator[Any, None]:
    # Lazy: app.deps imports aiosqlite; helper unit tests reload this module without it.
    from .deps import get_db

    async for conn in get_db():
        yield conn


def next_letter(code: str) -> str:
    if code == "H":
        return "H"
    if code not in GYM_CODES:
        raise ValueError(f"unknown day code: {code}")
    idx = GYM_CODES.index(code)
    return GYM_CODES[(idx + 1) % len(GYM_CODES)]


async def advance_next_code(db: "aiosqlite.Connection", day_code: str | None) -> str | None:
    from .db import utcnow  # lazy: app.db imports aiosqlite at module level

    cur = await db.execute("SELECT next_code FROM workout_plan_state WHERE id=1")
    row = await cur.fetchone()
    current = row[0] if row else None
    if day_code is None or day_code not in GYM_CODES:
        return current
    new_code = next_letter(day_code)
    await db.execute(
        "UPDATE workout_plan_state SET next_code=?, updated_at=? WHERE id=1",
        (new_code, utcnow()),
    )
    return new_code


def validate_muscles(keys: list[str]) -> list[str]:
    for key in keys:
        if key not in MUSCLE_KEYS:
            raise ValueError("unknown muscle")
    return keys


def media_kind_for_mime(mime: str) -> str:
    if mime == "image/gif":
        return "gif"
    if mime in IMAGE_MIMES:
        return "image"
    if mime in VIDEO_MIMES:
        return "video"
    raise ValueError(f"unsupported mime: {mime}")


def media_max_bytes(mime: str) -> int:
    kind = media_kind_for_mime(mime)
    if kind == "video":
        return VIDEO_MAX
    return IMAGE_MAX


def ext_for_mime(mime: str) -> str:
    ext = EXT_BY_MIME.get(mime)
    if ext is None:
        raise MediaError(415, "unsupported mime")
    return ext


def check_media_bytes(mime: str, n: int) -> None:
    try:
        media_kind_for_mime(mime)
    except ValueError as exc:
        raise MediaError(415, "unsupported mime") from exc
    if n > media_max_bytes(mime):
        raise MediaError(413, "too large")


def media_file_path(exercise_id: int, ext: str) -> Path:
    return WORKOUT_MEDIA_DIR / f"{exercise_id}.{ext}"


async def _get_live_exercise_row(db: "aiosqlite.Connection", exercise_id: int) -> dict[str, Any]:
    cur = await db.execute(
        "SELECT * FROM workout_exercises WHERE id=? AND deleted_at IS NULL",
        (exercise_id,),
    )
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return _row_dict(row)


async def patch_exercise_row(
    db: "aiosqlite.Connection",
    exercise_id: int,
    *,
    name: str | None = None,
    muscles: list[str] | None = None,
) -> dict[str, Any]:
    from .db import utcnow  # lazy: app.db imports aiosqlite at module level

    row = await _get_live_exercise_row(db, exercise_id)
    updates: list[str] = []
    params: list[Any] = []
    if name is not None:
        cur = await db.execute(
            """
            SELECT id FROM workout_exercises
            WHERE name=? AND deleted_at IS NULL AND id<>?
            """,
            (name, exercise_id),
        )
        if await cur.fetchone() is not None:
            raise HTTPException(status_code=409, detail="Duplicate exercise name")
        updates.append("name=?")
        params.append(name)
    if muscles is not None:
        try:
            validated = validate_muscles(muscles)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Unknown muscle") from exc
        updates.append("muscles_json=?")
        params.append(json.dumps(validated))
    if not updates:
        return row
    updates.append("updated_at=?")
    params.append(utcnow())
    params.append(exercise_id)
    await db.execute(
        f"UPDATE workout_exercises SET {', '.join(updates)} WHERE id=?",
        params,
    )
    await db.commit()
    return await _get_live_exercise_row(db, exercise_id)


async def save_exercise_media(
    db: "aiosqlite.Connection",
    exercise_id: int,
    mime: str,
    data: bytes,
) -> dict[str, Any]:
    from .db import utcnow  # lazy: app.db imports aiosqlite at module level

    row = await _get_live_exercise_row(db, exercise_id)
    check_media_bytes(mime, len(data))
    ext = ext_for_mime(mime)
    old_ext = row.get("media_ext")
    if old_ext and old_ext != ext:
        old_path = media_file_path(exercise_id, old_ext)
        if old_path.exists():
            old_path.unlink()
    WORKOUT_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    media_file_path(exercise_id, ext).write_bytes(data)
    now = utcnow()
    await db.execute(
        """
        UPDATE workout_exercises
        SET media_mime=?, media_ext=?, updated_at=?
        WHERE id=?
        """,
        (mime, ext, now, exercise_id),
    )
    await db.commit()
    return await _get_live_exercise_row(db, exercise_id)


async def delete_exercise_media(db: "aiosqlite.Connection", exercise_id: int) -> dict[str, Any]:
    from .db import utcnow  # lazy: app.db imports aiosqlite at module level

    row = await _get_live_exercise_row(db, exercise_id)
    old_ext = row.get("media_ext")
    if old_ext:
        path = media_file_path(exercise_id, old_ext)
        if path.exists():
            path.unlink()
    now = utcnow()
    await db.execute(
        """
        UPDATE workout_exercises
        SET media_mime=NULL, media_ext=NULL, updated_at=?
        WHERE id=?
        """,
        (now, exercise_id),
    )
    await db.commit()
    return await _get_live_exercise_row(db, exercise_id)


def parse_slot_weekdays(raw: str | None) -> list[int]:
    if raw is None or not str(raw).strip():
        return list(DEFAULT_SLOTS)
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError("slot_weekdays must be a JSON array")
    seen: set[int] = set()
    out: list[int] = []
    for item in parsed:
        if not isinstance(item, int):
            raise ValueError("slot weekday must be int")
        if item < 0 or item > 6:
            raise ValueError("slot weekday out of range")
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


async def ensure_workout_tables(db: "aiosqlite.Connection") -> None:
    import aiosqlite  # noqa: F401 — lazy import so helpers load without aiosqlite

    from .db import ensure_column

    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS workout_exercises (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          muscles_json TEXT NOT NULL DEFAULT '[]',
          media_mime TEXT,
          media_ext TEXT,
          deleted_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS workout_programs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'active',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS workout_days (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          program_id INTEGER NOT NULL REFERENCES workout_programs(id),
          code TEXT NOT NULL,
          title TEXT NOT NULL,
          sort INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS workout_day_items (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          day_id INTEGER NOT NULL REFERENCES workout_days(id),
          exercise_id INTEGER NOT NULL REFERENCES workout_exercises(id),
          sort INTEGER NOT NULL DEFAULT 0,
          sets INTEGER NOT NULL DEFAULT 1,
          reps_low INTEGER NOT NULL DEFAULT 1,
          reps_high INTEGER NOT NULL DEFAULT 1,
          notes TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS workout_plan_state (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          next_code TEXT NOT NULL DEFAULT 'A',
          slot_weekdays_json TEXT NOT NULL DEFAULT '[1,3,5]',
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS workout_sessions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL DEFAULT 'Тренировка',
          notes TEXT NOT NULL DEFAULT '',
          started_at TEXT NOT NULL,
          deleted_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS workout_sets (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id INTEGER NOT NULL REFERENCES workout_sessions(id) ON DELETE CASCADE,
          exercise TEXT NOT NULL,
          weight REAL,
          reps INTEGER,
          set_index INTEGER NOT NULL DEFAULT 1,
          notes TEXT NOT NULL DEFAULT ''
        );
        """
    )
    await ensure_column(db, "workout_sessions", "day_code", "TEXT")
    await ensure_column(db, "workout_sessions", "program_id", "INTEGER")
    await ensure_column(db, "workout_sets", "exercise_id", "INTEGER")
    WORKOUT_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    await db.commit()
    await seed_workout_program(db)


def _row_dict(row: Any) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


async def _lastrowid(db: "aiosqlite.Connection") -> int:
    cur = await db.execute("SELECT last_insert_rowid()")
    return int((await cur.fetchone())[0])


async def seed_sport_goals(db: "aiosqlite.Connection") -> None:
    from .db import utcnow
    from .goals import persist_recomputed

    now = utcnow()
    for goal_title, steps in SPORT_GOAL_CHAINS:
        cur = await db.execute(
            "SELECT id FROM goals WHERE title=? AND deleted_at IS NULL",
            (goal_title,),
        )
        if await cur.fetchone():
            continue
        cur = await db.execute(
            "SELECT COALESCE(MAX(sort), 0) + 1 AS s FROM goals WHERE deleted_at IS NULL"
        )
        sort = int((await cur.fetchone())["s"])
        cur = await db.execute(
            "INSERT INTO goals(title, sort, created_at, updated_at) VALUES(?,?,?,?)",
            (goal_title, sort, now, now),
        )
        goal_id = int(cur.lastrowid)
        cur = await db.execute(
            """
            INSERT INTO goal_nodes(goal_id, title, status, sort, created_at, updated_at)
            VALUES(?,?,?,?,?,?)
            """,
            (goal_id, goal_title, "open", 0, now, now),
        )
        parent_id = int(cur.lastrowid)
        for step_sort, step_title in enumerate(steps, start=1):
            cur = await db.execute(
                """
                INSERT INTO goal_nodes(goal_id, title, status, sort, created_at, updated_at)
                VALUES(?,?,?,?,?,?)
                """,
                (goal_id, step_title, "locked", step_sort, now, now),
            )
            child_id = int(cur.lastrowid)
            await db.execute(
                """
                INSERT INTO goal_edges(goal_id, parent_node_id, child_node_id)
                VALUES(?,?,?)
                """,
                (goal_id, parent_id, child_id),
            )
            parent_id = child_id
        await db.commit()
        await persist_recomputed(db, goal_id)


async def seed_workout_program(db: "aiosqlite.Connection") -> None:
    from .db import utcnow  # lazy: app.db imports aiosqlite at module level

    now = utcnow()
    name_to_id: dict[str, int] = {}
    for name, muscles in SEED_EXERCISES:
        cur = await db.execute(
            "SELECT id FROM workout_exercises WHERE name=? AND deleted_at IS NULL",
            (name,),
        )
        row = await cur.fetchone()
        if row:
            name_to_id[name] = int(row["id"])
            continue
        await db.execute(
            """
            INSERT INTO workout_exercises(name, muscles_json, created_at, updated_at)
            VALUES(?,?,?,?)
            """,
            (name, json.dumps(muscles), now, now),
        )
        name_to_id[name] = await _lastrowid(db)

    cur = await db.execute("SELECT id FROM workout_programs ORDER BY id LIMIT 1")
    row = await cur.fetchone()
    if row:
        program_id = int(row["id"])
    else:
        await db.execute(
            """
            INSERT INTO workout_programs(title, status, created_at, updated_at)
            VALUES(?,?,?,?)
            """,
            (PROGRAM_TITLE, "active", now, now),
        )
        program_id = await _lastrowid(db)

    for day in SEED_DAYS:
        code = day["code"]
        cur = await db.execute(
            "SELECT id FROM workout_days WHERE program_id=? AND code=?",
            (program_id, code),
        )
        existing = await cur.fetchone()
        if existing:
            day_id = int(existing["id"])
        else:
            await db.execute(
                """
                INSERT INTO workout_days(program_id, code, title, sort)
                VALUES(?,?,?,?)
                """,
                (program_id, code, day["title"], day["sort"]),
            )
            day_id = await _lastrowid(db)

        cur = await db.execute(
            "SELECT COUNT(*) FROM workout_day_items WHERE day_id=?",
            (day_id,),
        )
        if int((await cur.fetchone())[0]) > 0:
            continue
        for sort, item in enumerate(day["items"]):
            ex_name, sets, reps_low, reps_high, notes = item
            await db.execute(
                """
                INSERT INTO workout_day_items(
                  day_id, exercise_id, sort, sets, reps_low, reps_high, notes
                )
                VALUES(?,?,?,?,?,?,?)
                """,
                (
                    day_id,
                    name_to_id[ex_name],
                    sort,
                    sets,
                    reps_low,
                    reps_high,
                    notes,
                ),
            )

    cur = await db.execute("SELECT id FROM workout_plan_state WHERE id=1")
    if await cur.fetchone() is None:
        await db.execute(
            """
            INSERT INTO workout_plan_state(id, next_code, slot_weekdays_json, updated_at)
            VALUES(1, 'A', '[1,3,5]', ?)
            """,
            (now,),
        )
    await db.commit()


async def get_plan_payload(db: "aiosqlite.Connection") -> dict[str, Any]:
    cur = await db.execute(
        "SELECT * FROM workout_programs WHERE status='active' ORDER BY id LIMIT 1"
    )
    program_row = await cur.fetchone()
    if program_row is None:
        cur = await db.execute("SELECT * FROM workout_programs ORDER BY id LIMIT 1")
        program_row = await cur.fetchone()
    program = _row_dict(program_row) if program_row else None

    cur = await db.execute(
        "SELECT next_code, slot_weekdays_json FROM workout_plan_state WHERE id=1"
    )
    state_row = await cur.fetchone()
    if state_row:
        state = {
            "next_code": state_row["next_code"],
            "slot_weekdays": parse_slot_weekdays(state_row["slot_weekdays_json"]),
        }
    else:
        state = {"next_code": "A", "slot_weekdays": list(DEFAULT_SLOTS)}

    days: list[dict[str, Any]] = []
    if program is not None:
        cur = await db.execute(
            "SELECT * FROM workout_days WHERE program_id=? ORDER BY sort, id",
            (program["id"],),
        )
        for day in await cur.fetchall():
            item_cur = await db.execute(
                """
                SELECT i.id, i.sort, i.sets, i.reps_low, i.reps_high, i.notes,
                       e.id AS exercise_id, e.name, e.muscles_json,
                       e.media_mime, e.media_ext
                FROM workout_day_items i
                JOIN workout_exercises e ON e.id = i.exercise_id
                WHERE i.day_id=?
                ORDER BY i.sort, i.id
                """,
                (day["id"],),
            )
            items: list[dict[str, Any]] = []
            for item in await item_cur.fetchall():
                media_ext = item["media_ext"]
                items.append(
                    {
                        "id": item["id"],
                        "sort": item["sort"],
                        "sets": item["sets"],
                        "reps_low": item["reps_low"],
                        "reps_high": item["reps_high"],
                        "notes": item["notes"],
                        "exercise": {
                            "id": item["exercise_id"],
                            "name": item["name"],
                            "muscles": json.loads(item["muscles_json"] or "[]"),
                            "media_mime": item["media_mime"],
                            "media_ext": media_ext,
                            "has_media": media_ext is not None,
                        },
                    }
                )
            days.append({"code": day["code"], "title": day["title"], "items": items})

    cur = await db.execute(
        """
        SELECT ws.id, ws.title, ws.day_code, ws.started_at,
               (SELECT COUNT(*) FROM workout_sets s WHERE s.session_id = ws.id) AS sets_count
        FROM workout_sessions ws
        WHERE ws.deleted_at IS NULL
        ORDER BY ws.started_at DESC, ws.id DESC
        LIMIT 8
        """
    )
    recent = [
        {
            "id": row["id"],
            "title": row["title"],
            "day_code": row["day_code"],
            "started_at": row["started_at"],
            "sets_count": row["sets_count"],
        }
        for row in await cur.fetchall()
    ]

    cur = await db.execute(
        """
        SELECT s.exercise_id, s.weight, s.reps
        FROM workout_sets s
        JOIN workout_sessions ws ON ws.id = s.session_id
        WHERE s.exercise_id IS NOT NULL AND ws.deleted_at IS NULL
        ORDER BY ws.started_at DESC, s.set_index DESC, s.id DESC
        """
    )
    last_sets: dict[str, dict[str, Any]] = {}
    for row in await cur.fetchall():
        key = str(row["exercise_id"])
        if key in last_sets:
            continue
        last_sets[key] = {"weight": row["weight"], "reps": row["reps"]}

    return {
        "program": program,
        "state": state,
        "days": days,
        "recent": recent,
        "last_sets": last_sets,
    }


@router.get("/api/workout-plan")
async def get_workout_plan(
    db: "aiosqlite.Connection" = Depends(_workout_db),
    _: dict = Depends(require_auth),
) -> dict[str, Any]:
    return await get_plan_payload(db)


@router.patch("/api/workout-exercises/{exercise_id}")
async def patch_workout_exercise(
    exercise_id: int,
    body: ExercisePatchIn,
    db: "aiosqlite.Connection" = Depends(_workout_db),
    _: dict = Depends(require_auth),
) -> dict[str, Any]:
    row = await patch_exercise_row(
        db,
        exercise_id,
        name=body.name,
        muscles=body.muscles,
    )
    return {
        "id": row["id"],
        "name": row["name"],
        "muscles": json.loads(row["muscles_json"] or "[]"),
        "media_mime": row["media_mime"],
        "media_ext": row["media_ext"],
        "has_media": row["media_ext"] is not None,
    }


@router.put("/api/workout-exercises/{exercise_id}/media")
async def put_workout_exercise_media(
    exercise_id: int,
    file: UploadFile = File(...),
    db: "aiosqlite.Connection" = Depends(_workout_db),
    _: dict = Depends(require_auth),
) -> dict[str, Any]:
    mime = file.content_type or ""
    data = await file.read()
    try:
        row = await save_exercise_media(db, exercise_id, mime, data)
    except MediaError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
    return {
        "id": row["id"],
        "media_mime": row["media_mime"],
        "media_ext": row["media_ext"],
        "has_media": row["media_ext"] is not None,
    }


@router.get("/api/workout-exercises/{exercise_id}/media")
async def get_workout_exercise_media(
    exercise_id: int,
    db: "aiosqlite.Connection" = Depends(_workout_db),
    _: dict = Depends(require_auth),
) -> FileResponse:
    row = await _get_live_exercise_row(db, exercise_id)
    ext = row.get("media_ext")
    if not ext:
        raise HTTPException(status_code=404, detail="No media")
    path = media_file_path(exercise_id, ext)
    if not path.exists():
        raise HTTPException(status_code=404, detail="No media")
    return FileResponse(path, media_type=row["media_mime"] or "application/octet-stream")


@router.delete("/api/workout-exercises/{exercise_id}/media")
async def delete_workout_exercise_media(
    exercise_id: int,
    db: "aiosqlite.Connection" = Depends(_workout_db),
    _: dict = Depends(require_auth),
) -> dict[str, Any]:
    row = await delete_exercise_media(db, exercise_id)
    return {
        "id": row["id"],
        "media_mime": row["media_mime"],
        "media_ext": row["media_ext"],
        "has_media": False,
    }
