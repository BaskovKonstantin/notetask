from __future__ import annotations

from collections.abc import AsyncGenerator

import aiosqlite

from .config import DB_PATH


async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA busy_timeout=5000")
    await db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()
