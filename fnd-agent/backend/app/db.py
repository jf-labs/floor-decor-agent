from pathlib import Path
import sqlite3
from typing import Generator

# __file__ = .../fnd-agent-1/fnd-agent/backend/app/db.py
# parents[0] = app
# parents[1] = backend
# parents[2] = fnd-agent
# parents[3] = fnd-agent-1  <-- repo root
BASE_DIR = Path(__file__).resolve().parents[3]
DB_PATH = BASE_DIR / "data" / "fnd_products.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    FastAPI dependency: opens a connection for each request,
    and closes it when the request is done.
    """
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
