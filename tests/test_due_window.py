import unittest
from datetime import date

from app.due_utils import (
    due_day,
    normalize_due_start,
    task_in_today_view,
    task_in_upcoming_view,
    task_window_overdue,
)


class DueDayTests(unittest.TestCase):
    def test_parses_date_and_datetime(self) -> None:
        self.assertEqual(due_day("2026-09-01"), date(2026, 9, 1))
        self.assertEqual(due_day("2026-09-01T15:30:00"), date(2026, 9, 1))

    def test_empty(self) -> None:
        self.assertIsNone(due_day(None))
        self.assertIsNone(due_day(""))
        self.assertIsNone(due_day("   "))


class NormalizeDueStartTests(unittest.TestCase):
    def test_no_end_clears_start(self) -> None:
        self.assertIsNone(normalize_due_start("2026-09-01", None))

    def test_keeps_valid_window(self) -> None:
        self.assertEqual(normalize_due_start("2026-09-01", "2026-09-30"), "2026-09-01")

    def test_clamps_start_after_end(self) -> None:
        self.assertEqual(normalize_due_start("2026-10-01", "2026-09-30"), "2026-09-30")

    def test_same_day_ok(self) -> None:
        self.assertEqual(normalize_due_start("2026-09-06", "2026-09-06"), "2026-09-06")


class AgendaWindowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.today = date(2026, 9, 6)

    def test_single_due_today(self) -> None:
        t = {"kind": "task", "due_at": "2026-09-06", "due_start": None}
        self.assertTrue(task_in_today_view(t, self.today))
        self.assertFalse(task_in_upcoming_view(t, self.today))

    def test_single_due_future(self) -> None:
        t = {"kind": "task", "due_at": "2026-09-10", "due_start": None}
        self.assertFalse(task_in_today_view(t, self.today))
        self.assertTrue(task_in_upcoming_view(t, self.today))

    def test_single_due_overdue(self) -> None:
        t = {"kind": "task", "due_at": "2026-09-01", "due_start": None}
        self.assertTrue(task_in_today_view(t, self.today))
        self.assertTrue(task_window_overdue(t, self.today))
        self.assertFalse(task_in_upcoming_view(t, self.today))

    def test_window_before_start(self) -> None:
        t = {"kind": "task", "due_at": "2026-09-30", "due_start": "2026-09-10"}
        self.assertFalse(task_in_today_view(t, self.today))
        self.assertTrue(task_in_upcoming_view(t, self.today))
        self.assertFalse(task_window_overdue(t, self.today))

    def test_window_in_range(self) -> None:
        t = {"kind": "task", "due_at": "2026-09-30", "due_start": "2026-09-01"}
        self.assertTrue(task_in_today_view(t, self.today))
        self.assertFalse(task_in_upcoming_view(t, self.today))
        self.assertFalse(task_window_overdue(t, self.today))

    def test_window_after_end_overdue(self) -> None:
        t = {"kind": "task", "due_at": "2026-09-03", "due_start": "2026-09-01"}
        self.assertTrue(task_in_today_view(t, self.today))
        self.assertTrue(task_window_overdue(t, self.today))
        self.assertFalse(task_in_upcoming_view(t, self.today))

    def test_ideas_ignored(self) -> None:
        t = {"kind": "idea", "due_at": "2026-09-01", "due_start": None}
        self.assertFalse(task_in_today_view(t, self.today))


if __name__ == "__main__":
    unittest.main()
