"""Fingerprint the database and uploaded files created by the browser journeys."""

import sqlite3
from hashlib import sha256

from backend.app.settings import Settings
from backend.app.storage import LocalStorage

settings = Settings.from_env()
storage = LocalStorage(settings.files)
digest = sha256()
with sqlite3.connect(settings.database.resolve().as_uri() + "?mode=ro", uri=True) as db:
    db.execute("BEGIN")
    assert db.execute("SELECT count(*) FROM report").fetchone()[0] > 2, "Missing browser-created reports"
    assert db.execute("SELECT 1 FROM version_asset LIMIT 1").fetchone(), "Missing versioned attachments"
    for statement in db.iterdump():
        digest.update(statement.encode("utf-8"))
        digest.update(b"\n")
    for key, size in db.execute("SELECT storage_key, size_bytes FROM asset ORDER BY id"):
        data = storage.get(key)
        assert len(data) == size, f"Attachment size differs for {key}"
        digest.update(sha256(data).digest())

print(digest.hexdigest())
