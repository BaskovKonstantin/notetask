import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("NOTEBOOK_DATA", ROOT / "data"))
DB_PATH = Path(os.environ.get("NOTEBOOK_DB", DATA_DIR / "notetask.db"))
PASSWORD = os.environ.get("NOTEBOOK_PASSWORD", "changeme")
SECRET = os.environ.get("NOTEBOOK_SECRET", "dev-secret-change-me")
TOKEN_HOURS = int(os.environ.get("NOTEBOOK_TOKEN_HOURS", "720"))
PORT = int(os.environ.get("NOTEBOOK_PORT", "8100"))
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
TELEGRAM_PROXY = os.environ.get("TELEGRAM_PROXY", "").strip()
NOTIFY_TZ = os.environ.get("NOTEBOOK_TZ", "Europe/Moscow")
EVENING_DIGEST_HOUR = int(os.environ.get("NOTEBOOK_DIGEST_HOUR", "20"))
MORNING_DUE_HOUR = int(os.environ.get("NOTEBOOK_MORNING_DUE_HOUR", "9"))
ALICE_WEBHOOK_TOKEN = os.environ.get("ALICE_WEBHOOK_TOKEN", "").strip()
