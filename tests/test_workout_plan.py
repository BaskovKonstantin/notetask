import json
import sys
import types
import unittest


def _install_import_stubs() -> None:
    """Host venv is Python 3.14; pydantic/fastapi wheels do not build here."""
    if "fastapi" in sys.modules:
        return

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: object = None, headers: object = None) -> None:
            super().__init__(str(detail))
            self.status_code = status_code
            self.detail = detail
            self.headers = headers

    class _Router:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def _deco(self, *args: object, **kwargs: object):
            def wrap(fn):
                return fn

            return wrap

        get = post = patch = delete = put = _deco

    fastapi = types.ModuleType("fastapi")
    fastapi.APIRouter = _Router
    fastapi.Depends = lambda *a, **k: None
    fastapi.HTTPException = HTTPException
    fastapi.UploadFile = object
    fastapi.File = lambda *a, **k: None
    fastapi.status = types.SimpleNamespace(HTTP_401_UNAUTHORIZED=401)
    sys.modules["fastapi"] = fastapi

    responses = types.ModuleType("fastapi.responses")

    class FileResponse:
        def __init__(self, path: object, media_type: str | None = None) -> None:
            self.path = path
            self.media_type = media_type

    responses.FileResponse = FileResponse
    sys.modules["fastapi.responses"] = responses
    fastapi.responses = responses

    security = types.ModuleType("fastapi.security")

    class HTTPBearer:
        def __init__(self, auto_error: bool = False) -> None:
            pass

    class HTTPAuthorizationCredentials:
        pass

    security.HTTPBearer = HTTPBearer
    security.HTTPAuthorizationCredentials = HTTPAuthorizationCredentials
    sys.modules["fastapi.security"] = security
    fastapi.security = security

    pydantic = types.ModuleType("pydantic")

    class BaseModel:
        pass

    def Field(*args: object, **kwargs: object) -> None:
        return None

    pydantic.BaseModel = BaseModel
    pydantic.Field = Field
    sys.modules["pydantic"] = pydantic

    jwt_mod = types.ModuleType("jwt")
    jwt_mod.encode = lambda *a, **k: ""
    jwt_mod.decode = lambda *a, **k: {}
    jwt_mod.PyJWTError = type("PyJWTError", (Exception,), {})
    sys.modules["jwt"] = jwt_mod


_install_import_stubs()

import aiosqlite

from app.goals import ensure_goals_tables
from app.workouts import (
    MUSCLE_KEYS,
    SPORT_GOAL_CHAINS,
    advance_next_code,
    ensure_workout_tables,
    get_plan_payload,
    media_kind_for_mime,
    media_max_bytes,
    next_letter,
    parse_slot_weekdays,
    seed_sport_goals,
    seed_workout_program,
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

    def test_blank(self):
        self.assertEqual(parse_slot_weekdays(""), [1, 3, 5])

    def test_json(self):
        self.assertEqual(parse_slot_weekdays("[1,3,5,0]"), [1, 3, 5, 0])


class ImportWithoutAiosqliteTests(unittest.TestCase):
    def test_helpers_import_without_aiosqlite(self):
        saved = sys.modules.pop("aiosqlite", None)
        try:
            import importlib

            import app.workouts as workouts

            importlib.reload(workouts)
            self.assertEqual(workouts.next_letter("A"), "B")
        finally:
            if saved is not None:
                sys.modules["aiosqlite"] = saved
            elif "aiosqlite" in sys.modules:
                del sys.modules["aiosqlite"]


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
        cur = await db.execute(
            """
            SELECT COUNT(*) FROM workout_day_items i
            JOIN workout_days d ON d.id = i.day_id
            WHERE d.code = 'A'
            """
        )
        self.assertEqual((await cur.fetchone())[0], 5)
        cur = await db.execute(
            """
            SELECT e.name FROM workout_day_items i
            JOIN workout_days d ON d.id = i.day_id
            JOIN workout_exercises e ON e.id = i.exercise_id
            WHERE d.code = 'A'
            ORDER BY i.sort, i.id
            """
        )
        names = [r[0] for r in await cur.fetchall()]
        self.assertEqual(names[0], "Эскалатор 15 мин")
        await db.close()

    async def test_plan_payload_after_seed(self):
        db = await aiosqlite.connect(":memory:")
        db.row_factory = aiosqlite.Row
        await ensure_workout_tables(db)
        await seed_workout_program(db)
        payload = await get_plan_payload(db)
        self.assertIsInstance(payload["program"], dict)
        self.assertEqual(payload["state"]["next_code"], "A")
        self.assertEqual(payload["state"]["slot_weekdays"], [1, 3, 5])
        self.assertEqual([d["code"] for d in payload["days"]], ["A", "B", "C", "H"])
        self.assertEqual(payload["days"][0]["title"], "День A")
        day_a = payload["days"][0]["items"]
        self.assertEqual(len(day_a), 5)
        first = day_a[0]
        self.assertEqual(first["exercise"]["name"], "Эскалатор 15 мин")
        self.assertEqual(first["sets"], 1)
        self.assertEqual(first["reps_low"], 15)
        self.assertEqual(first["reps_high"], 15)
        self.assertEqual(first["notes"], "скорость 6–7")
        self.assertEqual(first["exercise"]["muscles"], ["cardio"])
        self.assertIsNone(first["exercise"]["media_mime"])
        self.assertIsNone(first["exercise"]["media_ext"])
        self.assertFalse(first["exercise"]["has_media"])
        bench = day_a[1]
        self.assertEqual(bench["exercise"]["name"], "Жим лёжа")
        self.assertEqual(bench["sets"], 3)
        self.assertEqual(bench["reps_low"], 5)
        self.assertEqual(bench["reps_high"], 8)
        self.assertEqual(bench["exercise"]["muscles"], ["chest", "triceps", "front_delt"])
        squat = day_a[2]
        self.assertEqual(squat["notes"], "старт 80 кг")
        self.assertEqual(payload["recent"], [])
        self.assertEqual(payload["last_sets"], {})
        await db.close()

    async def test_last_sets_and_recent(self):
        db = await aiosqlite.connect(":memory:")
        db.row_factory = aiosqlite.Row
        await ensure_workout_tables(db)
        await seed_workout_program(db)
        cur = await db.execute(
            "SELECT id FROM workout_exercises WHERE name=? AND deleted_at IS NULL",
            ("Жим лёжа",),
        )
        bench_id = (await cur.fetchone())[0]
        cur = await db.execute(
            """
            INSERT INTO workout_sessions(title, notes, started_at, created_at, updated_at, day_code)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            ("День A", "", "2026-09-18T10:00:00", "2026-09-18T10:00:00", "2026-09-18T10:00:00", "A"),
        )
        sid = cur.lastrowid
        await db.execute(
            """
            INSERT INTO workout_sets(session_id, exercise, weight, reps, set_index, notes, exercise_id)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (sid, "Жим лёжа", 80, 5, 1, "", bench_id),
        )
        await db.commit()
        payload = await get_plan_payload(db)
        self.assertEqual(len(payload["recent"]), 1)
        recent = payload["recent"][0]
        self.assertEqual(recent["title"], "День A")
        self.assertEqual(recent["day_code"], "A")
        self.assertEqual(recent["sets_count"], 1)
        self.assertEqual(payload["last_sets"][str(bench_id)], {"weight": 80, "reps": 5})
        await db.close()


class SeedSportGoalsTests(unittest.IsolatedAsyncioTestCase):
    TG_DUMMY_TITLE = "Создать канала на 1к подписчиков в ТГ"
    SPORT_TITLES = [title for title, _ in SPORT_GOAL_CHAINS]

    async def _insert_dummy_tg_goal(self, db: aiosqlite.Connection) -> int:
        from app.db import utcnow

        now = utcnow()
        cur = await db.execute(
            "INSERT INTO goals(title, sort, created_at, updated_at) VALUES(?,?,?,?)",
            (self.TG_DUMMY_TITLE, 0, now, now),
        )
        goal_id = int(cur.lastrowid)
        await db.execute(
            """
            INSERT INTO goal_nodes(goal_id, title, status, sort, created_at, updated_at)
            VALUES(?,?,?,?,?,?)
            """,
            (goal_id, self.TG_DUMMY_TITLE, "open", 0, now, now),
        )
        await db.commit()
        return goal_id

    async def test_seed_idempotent_three_sport_trees(self):
        db = await aiosqlite.connect(":memory:")
        db.row_factory = aiosqlite.Row
        await ensure_goals_tables(db)
        await self._insert_dummy_tg_goal(db)
        cur = await db.execute(
            """
            SELECT COUNT(*) FROM goal_nodes n
            JOIN goals g ON g.id = n.goal_id
            WHERE g.title=? AND g.deleted_at IS NULL AND n.deleted_at IS NULL
            """,
            (self.TG_DUMMY_TITLE,),
        )
        dummy_nodes_before = int((await cur.fetchone())[0])

        await seed_sport_goals(db)
        await seed_sport_goals(db)

        placeholders = ",".join("?" * len(self.SPORT_TITLES))
        cur = await db.execute(
            f"""
            SELECT COUNT(*) FROM goals
            WHERE deleted_at IS NULL AND title IN ({placeholders})
            """,
            self.SPORT_TITLES,
        )
        self.assertEqual(int((await cur.fetchone())[0]), 3)

        cur = await db.execute(
            """
            SELECT COUNT(*) FROM goal_nodes n
            JOIN goals g ON g.id = n.goal_id
            WHERE g.title=? AND g.deleted_at IS NULL AND n.deleted_at IS NULL
            """,
            (self.TG_DUMMY_TITLE,),
        )
        self.assertEqual(int((await cur.fetchone())[0]), dummy_nodes_before)

        for goal_title, steps in SPORT_GOAL_CHAINS:
            cur = await db.execute(
                "SELECT id FROM goals WHERE title=? AND deleted_at IS NULL",
                (goal_title,),
            )
            goal_id = int((await cur.fetchone())[0])
            cur = await db.execute(
                """
                SELECT COUNT(*) FROM goal_nodes
                WHERE goal_id=? AND deleted_at IS NULL
                """,
                (goal_id,),
            )
            self.assertEqual(int((await cur.fetchone())[0]), 1 + len(steps))
            cur = await db.execute(
                """
                SELECT COUNT(*) FROM goal_edges WHERE goal_id=?
                """,
                (goal_id,),
            )
            self.assertEqual(int((await cur.fetchone())[0]), len(steps))

        await db.close()


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

    async def test_mismatch_day_code_does_not_advance(self):
        db = await aiosqlite.connect(":memory:")
        db.row_factory = aiosqlite.Row
        await ensure_workout_tables(db)
        await seed_workout_program(db)
        await advance_next_code(db, "C")
        cur = await db.execute("SELECT next_code FROM workout_plan_state WHERE id=1")
        self.assertEqual((await cur.fetchone())[0], "A")
        await db.close()


if __name__ == "__main__":
    unittest.main()
