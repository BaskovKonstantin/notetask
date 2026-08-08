import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("NOTEBOOK_DATA", ROOT / "data"))
DB_PATH = Path(os.environ.get("NOTEBOOK_DB", DATA_DIR / "notetask.db"))
PASSWORD = os.environ.get("NOTEBOOK_PASSWORD", "changeme")
SECRET = os.environ.get("NOTEBOOK_SECRET", "dev-secret-change-me")
TOKEN_HOURS = int(os.environ.get("NOTEBOOK_TOKEN_HOURS", "720"))
PORT = int(os.environ.get("NOTEBOOK_PORT", "8100"))
