import os
from dataclasses import dataclass
from pathlib import Path

from .db import ROOT

@dataclass(frozen=True)
class Settings:
    database: Path
    files: Path
    jwt_secret: str
    draft_mode: str = "mock"
    model_url: str = ""
    model_name: str = ""
    model_key: str = ""

    @classmethod
    def from_env(cls):
        data = Path(os.environ.get("LENSBRIEF_DATA", ROOT / "data"))
        return cls(Path(os.environ.get("LENSBRIEF_DB", data / "lensbrief.sqlite3")),
                   data / "files", os.environ.get("LENSBRIEF_JWT_SECRET", "lensbrief-local-development-only-change-me"),
                   os.environ.get("LENSBRIEF_DRAFT_MODE", "mock"),
                   os.environ.get("LENSBRIEF_MODEL_URL", ""), os.environ.get("LENSBRIEF_MODEL", ""),
                   os.environ.get("LENSBRIEF_MODEL_KEY", ""))
