from __future__ import annotations

import unittest

from app.tg_callbacks import parse_done_callback_data


class ParseDoneCallbackTests(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(parse_done_callback_data("done:161"), 161)

    def test_bad(self):
        self.assertIsNone(parse_done_callback_data(None))
        self.assertIsNone(parse_done_callback_data(""))
        self.assertIsNone(parse_done_callback_data("done:"))
        self.assertIsNone(parse_done_callback_data("noop:1"))


if __name__ == "__main__":
    unittest.main()
