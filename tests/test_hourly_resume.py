from __future__ import annotations

import unittest
from datetime import date, timedelta

from app.task_complete import _hourly_resume_at


class HourlyResumeTests(unittest.TestCase):
    def test_uses_next_due_morning(self):
        day = date.today() + timedelta(days=2)
        got = _hourly_resume_at(day.isoformat())
        self.assertTrue(got.startswith(f"{day.isoformat()}T09:00:00"))

    def test_bumps_today_or_past_to_tomorrow(self):
        today = date.today()
        got = _hourly_resume_at(today.isoformat())
        tomorrow = today + timedelta(days=1)
        self.assertTrue(got.startswith(f"{tomorrow.isoformat()}T09:00:00"))


if __name__ == "__main__":
    unittest.main()
