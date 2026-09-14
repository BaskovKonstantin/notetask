from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from app.remind_utils import (
    hourly_dedupe_key,
    hourly_ready,
    in_hour_fire_window,
    next_hour_boundary,
    normalize_remind_rule,
)

TZ = ZoneInfo("Europe/Moscow")


class NormalizeRemindRuleTests(unittest.TestCase):
    def test_empty(self):
        self.assertIsNone(normalize_remind_rule(None))
        self.assertIsNone(normalize_remind_rule(""))
        self.assertIsNone(normalize_remind_rule("none"))

    def test_hourly(self):
        self.assertEqual(normalize_remind_rule("hourly"), "hourly")
        self.assertEqual(normalize_remind_rule("HOURLY"), "hourly")

    def test_invalid(self):
        with self.assertRaises(ValueError):
            normalize_remind_rule("daily")


class NextHourBoundaryTests(unittest.TestCase):
    def test_mid_hour(self):
        now = datetime(2026, 9, 9, 12, 34, 0, tzinfo=TZ)
        self.assertEqual(next_hour_boundary(now), datetime(2026, 9, 9, 13, 0, 0, tzinfo=TZ))

    def test_exact_hour(self):
        now = datetime(2026, 9, 9, 13, 0, 0, tzinfo=TZ)
        self.assertEqual(next_hour_boundary(now), datetime(2026, 9, 9, 13, 0, 0, tzinfo=TZ))


class HourlyWindowTests(unittest.TestCase):
    def test_window(self):
        self.assertTrue(in_hour_fire_window(datetime(2026, 9, 9, 13, 0, 10, tzinfo=TZ)))
        self.assertTrue(in_hour_fire_window(datetime(2026, 9, 9, 13, 4, 59, tzinfo=TZ)))
        self.assertFalse(in_hour_fire_window(datetime(2026, 9, 9, 13, 5, 0, tzinfo=TZ)))

    def test_dedupe_key(self):
        key = hourly_dedupe_key(16, datetime(2026, 9, 9, 13, 2, 0, tzinfo=TZ))
        self.assertEqual(key, "remind:16:2026-09-09T13")


class HourlyReadyTests(unittest.TestCase):
    def test_no_resume_ready(self):
        now = datetime(2026, 9, 14, 18, 0, 0, tzinfo=TZ)
        self.assertTrue(hourly_ready(now, None))
        self.assertTrue(hourly_ready(now, ""))

    def test_future_resume_paused(self):
        now = datetime(2026, 9, 14, 18, 0, 0, tzinfo=TZ)
        resume = "2026-09-15T09:00:00+03:00"
        self.assertFalse(hourly_ready(now, resume))

    def test_past_or_equal_resume_ready(self):
        now = datetime(2026, 9, 15, 9, 0, 0, tzinfo=TZ)
        self.assertTrue(hourly_ready(now, "2026-09-15T09:00:00+03:00"))
        self.assertTrue(hourly_ready(now, "2026-09-15T08:00:00+03:00"))


if __name__ == "__main__":
    unittest.main()
