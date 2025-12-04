from pathlib import Path
import sqlite3
from typing import Generator

# BASE_DIR = repo root (FND-AGENT-1)
BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "data" / "fnd_products.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    FastAPI dependency: open a connection per request and close it
    afterwards.
    """
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
