"""Telegram callback helpers (no heavy deps)."""

from __future__ import annotations


def parse_done_callback_data(data: str | None) -> int | None:
    raw = (data or "").strip()
    if not raw.startswith("done:"):
        return None
    try:
        return int(raw.split(":", 1)[1])
    except ValueError:
        return None
