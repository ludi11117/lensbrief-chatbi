import re
from pathlib import Path
from typing import Protocol

class ObjectStorage(Protocol):
    def put(self, key: str, content: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...

class LocalStorage:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def path(self, key):
        if not re.fullmatch(r"[a-f0-9]{32}", key):
            raise ValueError("Invalid storage key")
        return self.root / key

    def put(self, key, content):
        target = self.path(key)
        staging = target.with_suffix(".tmp")
        try:
            with staging.open("xb") as handle:
                handle.write(content)
            staging.replace(target)
        finally:
            staging.unlink(missing_ok=True)

    def get(self, key):
        return self.path(key).read_bytes()

    def delete(self, key):
        self.path(key).unlink(missing_ok=True)
