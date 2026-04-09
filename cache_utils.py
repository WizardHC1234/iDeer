"""Cache utilities: stable hashing, atomic writes, safe JSON reads."""

import hashlib
import json
import os
import tempfile


def stable_profile_hash(description: str) -> str:
    """Compute a stable short hash from user interest description.

    Normalizes whitespace so trivial formatting differences (trailing
    newlines, \\r\\n vs \\n, extra spaces) don't bust the cache.
    """
    normalized = "\n".join(line.strip() for line in description.strip().splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def atomic_write_json(path: str, data: dict, indent: int = 2) -> None:
    """Write JSON atomically via temp-file-then-rename.

    Prevents corrupted cache files if the process crashes mid-write.
    """
    dir_name = os.path.dirname(path)
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        os.replace(tmp_path, path)  # atomic on POSIX
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def safe_read_json(path: str) -> dict | None:
    """Read a JSON file, returning None on missing or corrupt files."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
