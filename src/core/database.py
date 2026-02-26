import sqlite3
import json
import datetime
import pickle

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]  # project root
DB_NAME = str(BASE_DIR / "notebook.db")


def init_db():
    """Initialize the database with the cells table."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS cells (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            output TEXT,
            variables TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    # NEW: persisted runtime variables
    c.execute("""
        CREATE TABLE IF NOT EXISTS variables (
            name TEXT PRIMARY KEY,
            type TEXT,
            value_pickle BLOB,
            metadata TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def add_cell(code, output, variables):
    """Add a new execution cell to the database."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO cells (code, output, variables)
        VALUES (?, ?, ?)
    """,
        (code, output, json.dumps(variables)),
    )
    conn.commit()
    conn.close()


def get_history():
    """Retrieve all execution history."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "SELECT id, code, output, variables, timestamp FROM cells ORDER BY id ASC"
    )
    rows = c.fetchall()
    conn.close()
    return rows


def get_last_state():
    """Retrieve the variables from the last execution."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT variables FROM cells ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return {}


def upsert_variable(name: str, value, metadata: dict | None = None):
    """Serialize (pickle) and persist a python object."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    type_name = type(value).__name__
    blob = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
    meta_json = json.dumps(metadata or {})

    c.execute(
        """
        INSERT INTO variables (name, type, value_pickle, metadata, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(name) DO UPDATE SET
            type=excluded.type,
            value_pickle=excluded.value_pickle,
            metadata=excluded.metadata,
            updated_at=CURRENT_TIMESTAMP
    """,
        (name, type_name, blob, meta_json),
    )

    conn.commit()
    conn.close()


def load_all_variables() -> dict:
    """Load and unpickle all persisted variables."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT name, value_pickle FROM variables")
    rows = c.fetchall()
    conn.close()

    out = {}
    for name, blob in rows:
        try:
            out[name] = pickle.loads(blob)
        except Exception:
            # If something cannot be unpickled, skip it (don’t crash app)
            continue
    return out


if __name__ == "__main__":
    init_db()
    print("Database initialized.")
