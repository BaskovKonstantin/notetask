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
    fastapi.status = types.SimpleNamespace(HTTP_401_UNAUTHORIZED=401)
    sys.modules["fastapi"] = fastapi

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


if __name__ == "__main__":
    unittest.main()
