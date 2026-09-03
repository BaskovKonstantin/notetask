import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from app.due_utils import due_at_present, is_task_overdue, parse_task_dt


class DueAtPresentTests(unittest.TestCase):
    def test_null_and_empty(self) -> None:
        self.assertFalse(due_at_present(None))
        self.assertFalse(due_at_present(""))
        self.assertFalse(due_at_present("   "))

    def test_valid(self) -> None:
        self.assertTrue(due_at_present("2026-09-03"))
        self.assertTrue(due_at_present(" 2026-09-03 "))


class OverdueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 9, 3, 20, 0, tzinfo=ZoneInfo("Europe/Moscow"))

    def test_null_due_not_overdue(self) -> None:
        self.assertFalse(is_task_overdue(None, self.now))

    def test_empty_due_not_overdue(self) -> None:
        self.assertFalse(is_task_overdue("", self.now))
        self.assertFalse(is_task_overdue("   ", self.now))

    def test_past_date_is_overdue(self) -> None:
        self.assertTrue(is_task_overdue("2026-08-10", self.now))

    def test_today_not_overdue(self) -> None:
        self.assertFalse(is_task_overdue("2026-09-03", self.now))

    def test_future_not_overdue(self) -> None:
        self.assertFalse(is_task_overdue("2026-09-10", self.now))

    def test_invalid_due_not_overdue(self) -> None:
        self.assertFalse(is_task_overdue("not-a-date", self.now))
        self.assertIsNone(parse_task_dt("not-a-date"))


if __name__ == "__main__":
    unittest.main()
