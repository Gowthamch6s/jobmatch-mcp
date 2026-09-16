import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Every test gets its own throwaway SQLite file and mock-mode Adzuna
    (no credentials set), so tests never touch a shared db or the network."""
    db_path = tmp_path / "test_jobmatch.db"
    monkeypatch.setenv("JOBMATCH_DB_PATH", str(db_path))
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    yield str(db_path)
