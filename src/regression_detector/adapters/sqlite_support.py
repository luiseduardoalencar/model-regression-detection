"""Shared SQLite setup for the local stores (decided 2026-11-17).

The tables are STRICT (rigid column types), which needs SQLite 3.37 or newer; the
SQLite bundled with Python 3.12 is newer, so no version check is made.
"""

import sqlite3
from pathlib import Path


def connect(path: Path) -> sqlite3.Connection:
    """Open (and create, with its folder) a database file with foreign keys enforced."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
