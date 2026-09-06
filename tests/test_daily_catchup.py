import unittest
from datetime import date

from app.due_utils import catch_up_daily_due_at, next_daily_after_complete


class CatchUpDailyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.today = date(2026, 9, 6)

    def test_overdue_date_only_snaps_to_today(self) -> None:
        self.assertEqual(catch_up_daily_due_at("2026-09-04", self.today), "2026-09-06")

    def test_overdue_keeps_time(self) -> None:
        self.assertEqual(
            catch_up_daily_due_at("2026-09-04T07:00:00", self.today),
            "2026-09-06T07:00:00",
        )

    def test_today_unchanged(self) -> None:
        self.assertEqual(catch_up_daily_due_at("2026-09-06", self.today), "2026-09-06")
        self.assertEqual(
            catch_up_daily_due_at("2026-09-06T07:00:00", self.today),
            "2026-09-06T07:00:00",
        )

    def test_future_unchanged(self) -> None:
        self.assertEqual(catch_up_daily_due_at("2026-09-10", self.today), "2026-09-10")

    def test_empty(self) -> None:
        self.assertIsNone(catch_up_daily_due_at(None, self.today))
        self.assertEqual(catch_up_daily_due_at("", self.today), "")


class NextDailyAfterCompleteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.today = date(2026, 9, 6)

    def test_from_overdue_goes_tomorrow(self) -> None:
        self.assertEqual(next_daily_after_complete("2026-09-04", self.today), "2026-09-07")

    def test_keeps_time(self) -> None:
        self.assertEqual(
            next_daily_after_complete("2026-09-04T07:00:00", self.today),
            "2026-09-07T07:00:00",
        )

    def test_from_today_goes_tomorrow(self) -> None:
        self.assertEqual(next_daily_after_complete("2026-09-06", self.today), "2026-09-07")


if __name__ == "__main__":
    unittest.main()
