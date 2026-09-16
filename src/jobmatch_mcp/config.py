"""Environment-backed configuration.

Credentials live here and only here -- they are read from the process
environment on the server side and are never passed through tool
arguments or echoed back into model context. If ADZUNA_APP_ID /
ADZUNA_APP_KEY are absent, the server runs in MOCK mode automatically
(see adzuna_client.py) so it stays fully runnable and testable without
secrets, e.g. in CI.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    adzuna_app_id: str | None
    adzuna_app_key: str | None
    db_path: str
    log_level: str

    @property
    def has_adzuna_credentials(self) -> bool:
        return bool(self.adzuna_app_id and self.adzuna_app_key)


def load_settings() -> Settings:
    return Settings(
        adzuna_app_id=os.environ.get("ADZUNA_APP_ID") or None,
        adzuna_app_key=os.environ.get("ADZUNA_APP_KEY") or None,
        db_path=os.environ.get("JOBMATCH_DB_PATH", "./jobmatch.db"),
        log_level=os.environ.get("JOBMATCH_LOG_LEVEL", "INFO").upper(),
    )
