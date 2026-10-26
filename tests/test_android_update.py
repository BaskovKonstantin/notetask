from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.main import android_update_payload


class AndroidUpdatePayloadTests(unittest.TestCase):
    def test_reads_sidecar_json(self):
        with TemporaryDirectory() as raw:
            folder = Path(raw)
            (folder / "NoteTask.apk").write_bytes(b"pk")
            (folder / "android-version.json").write_text(
                json.dumps({"versionCode": 4, "versionName": "0.3.0"}),
                encoding="utf-8",
            )
            with patch("app.main.DOWNLOADS_DIR", folder):
                data = android_update_payload()
        self.assertEqual(data["versionCode"], 4)
        self.assertEqual(data["versionName"], "0.3.0")
        self.assertTrue(data["available"])
        self.assertEqual(data["url"], "/downloads/NoteTask.apk")
        self.assertEqual(data["size"], 2)
