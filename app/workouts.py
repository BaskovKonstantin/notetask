"""Workout plan helpers, schema ensure, and API (router added in later tasks)."""

from __future__ import annotations

import json
from pathlib import Path

import aiosqlite

from .config import DATA_DIR
from .db import ensure_column, utcnow

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

WORKOUT_MEDIA_DIR: Path = DATA_DIR / "workout-media"


def next_letter(code: str) -> str:
    if code == "H":
        return "H"
    if code not in GYM_CODES:
        raise ValueError(f"unknown day code: {code}")
    idx = GYM_CODES.index(code)
    return GYM_CODES[(idx + 1) % len(GYM_CODES)]


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


async def ensure_workout_tables(db: aiosqlite.Connection) -> None:
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
        """
    )
    await ensure_column(db, "workout_sessions", "day_code", "TEXT")
    await ensure_column(db, "workout_sessions", "program_id", "INTEGER")
    await ensure_column(db, "workout_sets", "exercise_id", "INTEGER")
    WORKOUT_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    await db.commit()
