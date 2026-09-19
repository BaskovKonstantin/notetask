import json
import sys
import tempfile
import types
import unittest
from pathlib import Path


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

from app.workouts import (
    MediaError,
    WORKOUT_MEDIA_DIR,
    check_media_bytes,
    ensure_workout_tables,
    ext_for_mime,
    patch_exercise_row,
    save_exercise_media,
    delete_exercise_media,
    media_file_path,
)


def assert_media_size(mime: str, size: int, *, expect_ok: bool = True) -> None:
    if expect_ok:
        check_media_bytes(mime, size)
    else:
        check_media_bytes(mime, size)


class ExtForMimeTests(unittest.TestCase):
    def test_gif(self):
        self.assertEqual(ext_for_mime("image/gif"), "gif")

    def test_jpeg(self):
        self.assertEqual(ext_for_mime("image/jpeg"), "jpg")

    def test_png(self):
        self.assertEqual(ext_for_mime("image/png"), "png")

    def test_webp(self):
        self.assertEqual(ext_for_mime("image/webp"), "webp")

    def test_mp4(self):
        self.assertEqual(ext_for_mime("video/mp4"), "mp4")

    def test_webm(self):
        self.assertEqual(ext_for_mime("video/webm"), "webm")

    def test_bad_mime(self):
        with self.assertRaises(MediaError) as ctx:
            ext_for_mime("application/pdf")
        self.assertEqual(ctx.exception.status, 415)


class CheckMediaBytesTests(unittest.TestCase):
    def test_too_big_gif(self):
        with self.assertRaises(MediaError) as ctx:
            check_media_bytes("image/gif", 8_000_001)
        self.assertEqual(ctx.exception.status, 413)

    def test_too_big_jpeg(self):
        with self.assertRaises(MediaError) as ctx:
            check_media_bytes("image/jpeg", 8_000_001)
        self.assertEqual(ctx.exception.status, 413)

    def test_too_big_mp4(self):
        with self.assertRaises(MediaError) as ctx:
            check_media_bytes("video/mp4", 25_000_001)
        self.assertEqual(ctx.exception.status, 413)

    def test_bad_mime(self):
        with self.assertRaises(MediaError) as ctx:
            check_media_bytes("application/pdf", 100)
        self.assertEqual(ctx.exception.status, 415)

    def test_ok_at_limit(self):
        check_media_bytes("image/png", 8_000_000)
        check_media_bytes("video/webm", 25_000_000)

    def test_assert_media_size_helper(self):
        assert_media_size("image/jpeg", 1_000)
        with self.assertRaises(MediaError):
            assert_media_size("image/jpeg", 9_000_000, expect_ok=False)


class MediaFileHelperTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.media_dir = Path(self.tmp.name) / "workout-media"
        self.media_dir.mkdir()
        self._orig_dir = WORKOUT_MEDIA_DIR
        import app.workouts as workouts

        workouts.WORKOUT_MEDIA_DIR = self.media_dir
        self.db = await aiosqlite.connect(":memory:")
        self.db.row_factory = aiosqlite.Row
        await ensure_workout_tables(self.db)
        cur = await self.db.execute(
            "SELECT id FROM workout_exercises WHERE name=? AND deleted_at IS NULL",
            ("Жим лёжа",),
        )
        self.exercise_id = int((await cur.fetchone())[0])

    async def asyncTearDown(self) -> None:
        import app.workouts as workouts

        workouts.WORKOUT_MEDIA_DIR = self._orig_dir
        await self.db.close()
        self.tmp.cleanup()

    async def test_save_and_path(self):
        data = b"GIF89a"
        await save_exercise_media(self.db, self.exercise_id, "image/gif", data)
        path = media_file_path(self.exercise_id, "gif")
        self.assertTrue(path.exists())
        self.assertEqual(path.read_bytes(), data)
        cur = await self.db.execute(
            "SELECT media_mime, media_ext FROM workout_exercises WHERE id=?",
            (self.exercise_id,),
        )
        row = await cur.fetchone()
        self.assertEqual(row["media_mime"], "image/gif")
        self.assertEqual(row["media_ext"], "gif")

    async def test_replace_deletes_old_ext(self):
        ex_id = self.exercise_id
        await save_exercise_media(self.db, ex_id, "image/gif", b"gif-old")
        await save_exercise_media(self.db, ex_id, "image/png", b"png-new")
        self.assertFalse((self.media_dir / f"{ex_id}.gif").exists())
        self.assertTrue((self.media_dir / f"{ex_id}.png").exists())

    async def test_delete_clears_db_and_file(self):
        ex_id = self.exercise_id
        await save_exercise_media(self.db, ex_id, "image/jpeg", b"jpeg")
        await delete_exercise_media(self.db, ex_id)
        self.assertFalse((self.media_dir / f"{ex_id}.jpg").exists())
        cur = await self.db.execute(
            "SELECT media_mime, media_ext FROM workout_exercises WHERE id=?",
            (ex_id,),
        )
        row = await cur.fetchone()
        self.assertIsNone(row["media_mime"])
        self.assertIsNone(row["media_ext"])


class PatchExerciseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = await aiosqlite.connect(":memory:")
        self.db.row_factory = aiosqlite.Row
        await ensure_workout_tables(self.db)
        cur = await self.db.execute(
            "SELECT id, name FROM workout_exercises WHERE deleted_at IS NULL ORDER BY id"
        )
        rows = await cur.fetchall()
        by_name = {row["name"]: int(row["id"]) for row in rows}
        self.bench_id = by_name["Жим лёжа"]
        self.squat_id = by_name["Присед"]

    async def asyncTearDown(self) -> None:
        await self.db.close()

    async def test_patch_name_and_muscles(self):
        row = await patch_exercise_row(
            self.db,
            self.bench_id,
            name="Жим узким",
            muscles=["chest", "triceps"],
        )
        self.assertEqual(row["name"], "Жим узким")
        self.assertEqual(json.loads(row["muscles_json"]), ["chest", "triceps"])

    async def test_duplicate_name_raises(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            await patch_exercise_row(self.db, self.bench_id, name="Присед")
        self.assertEqual(ctx.exception.status_code, 409)

    async def test_unknown_muscle_raises(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            await patch_exercise_row(self.db, self.bench_id, muscles=["wings"])
        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
