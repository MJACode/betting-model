"""
conftest.py — Shared pytest fixtures for the betting model test suite.
"""

import sys
import sqlite3
from pathlib import Path
import pytest

# Add project root to sys.path so all modules resolve correctly
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.db_setup import SCHEMA_SQL


@pytest.fixture
def db_conn():
    """In-memory SQLite database with the full schema applied."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    yield conn
    conn.close()
