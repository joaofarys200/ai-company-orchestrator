"""
Shared crash-safe atomic file I/O primitives for JARVIS OS Python modules.

Uses unique sibling temporary files via ``tempfile.mkstemp``, ``flush()``, ``os.fsync()``,
and ``os.replace()`` with transient Windows sharing-violation retry so partial/torn
writes never corrupt JSON, SQLite side-car state, caches, or Markdown knowledge notes.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


def run_with_sharing_retry(fn: Any, *, attempts: int = 10, base_delay: float = 0.004) -> Any:
    """Retries transient WinError 5/32 sharing violations briefly during atomic swap."""
    for attempt in range(attempts):
        try:
            return fn()
        except PermissionError:
            if os.name != "nt" or attempt + 1 >= attempts:
                raise
            time.sleep(base_delay * (attempt + 1))


def atomic_write_bytes(path: Path | str, data: bytes) -> None:
    """Atomically writes raw bytes using ``mkstemp`` + ``fsync`` + ``os.replace``."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
        run_with_sharing_retry(lambda: os.replace(tmp_name, target))
    except Exception:
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except OSError:
            pass
        raise


def atomic_write_text(
    path: Path | str,
    content: str,
    *,
    encoding: str = "utf-8",
) -> None:
    """Atomically writes UTF-8 (or specified encoding) text."""
    atomic_write_bytes(path, content.encode(encoding))


def atomic_write_json(
    path: Path | str,
    payload: Any,
    *,
    indent: int = 2,
    ensure_ascii: bool = False,
) -> None:
    """Serializes JSON deterministically and writes it atomically."""
    serialized = json.dumps(payload, indent=indent, ensure_ascii=ensure_ascii)
    atomic_write_text(path, serialized, encoding="utf-8")
