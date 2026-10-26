from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from app.alice_parse import parse_alice

TZ = ZoneInfo("Europe/Moscow")
NOW = datetime(2026, 9, 19, 22, 2, tzinfo=TZ)  # Saturday


class AliceParseTests(unittest.TestCase):
    def test_plain_title(self):
        draft = parse_alice("добавь купить молоко", NOW)
        self.assertTrue(draft.ok)
        self.assertEqual(draft.title, "купить молоко")
        self.assertIsNone(draft.due_at)
        self.assertIsNone(draft.remind_at)
        self.assertIsNone(draft.repeat_rule)

    def test_remind_tomorrow_morning(self):
        draft = parse_alice("напомни завтра в 9 позвонить стоматологу", NOW)
        self.assertTrue(draft.ok)
        self.assertEqual(draft.title, "позвонить стоматологу")
        self.assertEqual(draft.due_at, "2026-09-20")
        self.assertEqual(draft.remind_at, "2026-09-20T09:00:00+03:00")
        self.assertIn("Напомню завтра в 9:00", draft.reply)

    def test_deadline_friday(self):
        draft = parse_alice("до пятницы сдать отчет", NOW)
        self.assertTrue(draft.ok)
        self.assertEqual(draft.title, "сдать отчет")
        self.assertEqual(draft.due_at, "2026-09-25")
        self.assertIsNone(draft.remind_at)

    def test_every_monday(self):
        draft = parse_alice("каждый понедельник в 8 зарядка", NOW)
        self.assertTrue(draft.ok)
        self.assertEqual(draft.title, "зарядка")
        self.assertEqual(draft.repeat_rule, "weekly")
        self.assertEqual(draft.due_at, "2026-09-21T08:00:00+03:00")

    def test_weekdays(self):
        draft = parse_alice("по будням стендап в 10", NOW)
        self.assertEqual(draft.repeat_rule, "weekdays")
        self.assertEqual(draft.title, "стендап")
        self.assertEqual(draft.due_at, "2026-09-21T10:00:00+03:00")

    def test_hourly(self):
        draft = parse_alice("напомни каждый час пить воду", NOW)
        self.assertTrue(draft.ok)
        self.assertEqual(draft.title, "пить воду")
        self.assertEqual(draft.remind_rule, "hourly")
        self.assertIn("каждые 3 часа", draft.reply)

    def test_every_3_hours(self):
        draft = parse_alice("напомни каждые 3 часа пить воду", NOW)
        self.assertTrue(draft.ok)
        self.assertEqual(draft.title, "пить воду")
        self.assertEqual(draft.remind_rule, "hourly")
        self.assertIn("каждые 3 часа", draft.reply)

    def test_help(self):
        draft = parse_alice("помощь", NOW)
        self.assertFalse(draft.ok)
        self.assertIn("завтра в 9", draft.reply)

    def test_evening_word(self):
        draft = parse_alice("напомни завтра в девять вечера забрать посылку", NOW)
        self.assertEqual(draft.remind_at, "2026-09-20T21:00:00+03:00")
        self.assertEqual(draft.title, "забрать посылку")


if __name__ == "__main__":
    unittest.main()
