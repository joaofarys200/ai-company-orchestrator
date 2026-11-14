"""Canonical `database.db` write-exclusivity guard for JARVIS OS Python runtimes.

Ensures Rust Core (`SqliteDatabase` in `src-tauri/src/storage/sqlite.rs`) is the
sole writer to `PROJECT_ROOT/database.db` whenever running inside a Tauri worker
or when `JARVIS_DB_WRITE_OWNER=rust` is set.

Non-canonical SQLite databases (`state.db` for MissionWorker, `:memory:`,
`chroma.sqlite3`, and temporary test databases) remain unrestricted.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import sqlite3
import sys
import threading
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CANONICAL_DB_PATH = PROJECT_ROOT / "database.db"

_GUARD_LOCK = threading.Lock()
_GUARD_INSTALLED = False
_ORIG_CONNECT = sqlite3.connect
_ORIG_CONNECTION = sqlite3.Connection

_READ_WRITE_URI_MODES = frozenset({"rw", "rwc"})
_ALLOWED_READONLY_PRAGMAS = frozenset({"busy_timeout", "foreign_keys", "synchronous"})

_WRITE_OPCODES = frozenset(
    opcode
    for opcode in (
        getattr(sqlite3, "SQLITE_INSERT", None),
        getattr(sqlite3, "SQLITE_UPDATE", None),
        getattr(sqlite3, "SQLITE_DELETE", None),
        getattr(sqlite3, "SQLITE_CREATE_INDEX", None),
        getattr(sqlite3, "SQLITE_CREATE_TABLE", None),
        getattr(sqlite3, "SQLITE_CREATE_TEMP_INDEX", None),
        getattr(sqlite3, "SQLITE_CREATE_TEMP_TABLE", None),
        getattr(sqlite3, "SQLITE_CREATE_TEMP_TRIGGER", None),
        getattr(sqlite3, "SQLITE_CREATE_TEMP_VIEW", None),
        getattr(sqlite3, "SQLITE_CREATE_TRIGGER", None),
        getattr(sqlite3, "SQLITE_CREATE_VIEW", None),
        getattr(sqlite3, "SQLITE_CREATE_VTABLE", None),
        getattr(sqlite3, "SQLITE_DROP_INDEX", None),
        getattr(sqlite3, "SQLITE_DROP_TABLE", None),
        getattr(sqlite3, "SQLITE_DROP_TEMP_INDEX", None),
        getattr(sqlite3, "SQLITE_DROP_TEMP_TABLE", None),
        getattr(sqlite3, "SQLITE_DROP_TEMP_TRIGGER", None),
        getattr(sqlite3, "SQLITE_DROP_TEMP_VIEW", None),
        getattr(sqlite3, "SQLITE_DROP_TRIGGER", None),
        getattr(sqlite3, "SQLITE_DROP_VIEW", None),
        getattr(sqlite3, "SQLITE_DROP_VTABLE", None),
        getattr(sqlite3, "SQLITE_ALTER_TABLE", None),
        getattr(sqlite3, "SQLITE_ATTACH", None),
        getattr(sqlite3, "SQLITE_DETACH", None),
        getattr(sqlite3, "SQLITE_REINDEX", None),
        getattr(sqlite3, "SQLITE_ANALYZE", None),
        getattr(sqlite3, "SQLITE_SAVEPOINT", None),
    )
    if opcode is not None
)

_SQLITE_PRAGMA = getattr(sqlite3, "SQLITE_PRAGMA", 19)
_SQLITE_ATTACH = getattr(sqlite3, "SQLITE_ATTACH", 24)
_SQLITE_OK = getattr(sqlite3, "SQLITE_OK", 0)
_SQLITE_DENY = getattr(sqlite3, "SQLITE_DENY", 1)


class DatabaseWritePermissionError(PermissionError):
    """Raised when Python attempts an unauthorized direct write to `database.db`."""


def is_rust_write_owner() -> bool:
    return os.environ.get("JARVIS_DB_WRITE_OWNER", "").strip().lower() == "rust"


def is_worker_guard_installed() -> bool:
    return _GUARD_INSTALLED


def should_block_direct_canonical_writes() -> bool:
    return _GUARD_INSTALLED or is_rust_write_owner()


def _normalize_fs_path(path_value: str | Path) -> str:
    expanded = os.path.abspath(os.path.expanduser(str(path_value)))
    resolved = os.path.realpath(expanded)
    return os.path.normcase(resolved)


def get_canonical_db_paths() -> list[Path]:
    """Returns canonical `database.db` candidates protected against Python writes."""
    paths: list[Path] = [DEFAULT_CANONICAL_DB_PATH]
    env_db = os.environ.get("JARVIS_CANONICAL_DB_PATH", "").strip()
    if env_db:
        paths.append(Path(env_db))
    env_root = os.environ.get("JARVIS_PROJECT_ROOT", "").strip()
    if env_root:
        paths.append(Path(env_root) / "database.db")
    return paths


def _canonical_db_normalized_set() -> set[str]:
    return {_normalize_fs_path(p) for p in get_canonical_db_paths()}


def get_active_canonical_db_path() -> Path:
    env_db = os.environ.get("JARVIS_CANONICAL_DB_PATH", "").strip()
    if env_db:
        return Path(env_db)
    env_root = os.environ.get("JARVIS_PROJECT_ROOT", "").strip()
    if env_root:
        return Path(env_root) / "database.db"
    return DEFAULT_CANONICAL_DB_PATH


def parse_sqlite_target(
    database: Any,
    *,
    uri: bool = False,
) -> tuple[str | None, str | None, bool]:
    """Resolves `(normalized_abs_path, uri_mode, is_memory)` for any sqlite target."""
    if database is None:
        return _normalize_fs_path(get_active_canonical_db_path()), None, False

    if isinstance(database, bytes):
        raw = os.fsdecode(database)
    elif isinstance(database, os.PathLike):
        raw = os.fspath(database)
        if isinstance(raw, bytes):
            raw = os.fsdecode(raw)
    else:
        raw = str(database)

    text = raw.strip()
    if text == ":memory:":
        return None, None, True

    if not text or text == "database.db":
        return _normalize_fs_path(get_active_canonical_db_path()), None, False

    is_file_uri = uri or text.lower().startswith("file:")
    if is_file_uri:
        parsed = urlsplit(text)
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        mode_vals = query_params.get("mode") or []
        mode = mode_vals[0].strip().lower() if mode_vals else None
        unquoted_path = unquote(parsed.path or "")
        if not unquoted_path and parsed.netloc:
            unquoted_path = unquote(parsed.netloc)
        if unquoted_path.startswith(":memory:") or mode == "memory":
            return None, mode, True
        if os.name == "nt" and re.match(r"^/[A-Za-z]:", unquoted_path):
            unquoted_path = unquoted_path[1:]
        if not unquoted_path or unquoted_path == "database.db":
            return _normalize_fs_path(get_active_canonical_db_path()), mode, False
        return _normalize_fs_path(unquoted_path), mode, False

    return _normalize_fs_path(text), None, False


def is_canonical_db_target(database: Any, *, uri: bool = False) -> bool:
    normalized, _mode, is_memory = parse_sqlite_target(database, uri=uri)
    if is_memory or normalized is None:
        return False
    return normalized in _canonical_db_normalized_set()


def assert_direct_write_allowed(
    db_path: Any = None,
    *,
    uri: bool = False,
    operation: str = "sqlite write",
) -> None:
    """Raises `DatabaseWritePermissionError` if Python attempts direct writes to `database.db`."""
    if not should_block_direct_canonical_writes():
        return
    if is_canonical_db_target(db_path, uri=uri):
        raise DatabaseWritePermissionError(
            f"Direct Python {operation} on canonical database.db is forbidden; "
            "Rust SqliteDatabase owns all writes."
        )


def should_route_canonical_db_via_rpc(db_path: Any = None) -> tuple[bool, Any | None]:
    """Returns `(use_rpc, rpc_server)` for canonical DB operations under Rust supervision.

    Fails closed with `DatabaseWritePermissionError` if `JARVIS_DB_WRITE_OWNER=rust`
    is set without an active stdio RPC server.
    """
    if not is_canonical_db_target(db_path):
        return False, None
    if not is_rust_write_owner():
        return False, None

    from workers.common.stdio_rpc import get_active_rpc_server

    server = get_active_rpc_server()
    if server is None:
        raise DatabaseWritePermissionError(
            "JARVIS_DB_WRITE_OWNER=rust is set, but no active Reverse-RPC bridge "
            "is available for canonical database.db."
        )
    return True, server


def _strict_readonly_authorizer(
    action: int,
    arg1: str | None,
    arg2: str | None,
    _db_name: str | None,
    _trigger_name: str | None,
) -> int:
    if action in _WRITE_OPCODES:
        return _SQLITE_DENY
    if action == _SQLITE_PRAGMA:
        pragma_name = (arg1 or "").strip().lower()
        if arg2 is not None and pragma_name not in _ALLOWED_READONLY_PRAGMAS:
            return _SQLITE_DENY
    return _SQLITE_OK


def _attach_jail_authorizer(
    action: int,
    arg1: str | None,
    _arg2: str | None,
    _db_name: str | None,
    _trigger_name: str | None,
) -> int:
    if action == _SQLITE_ATTACH and arg1 and is_canonical_db_target(arg1):
        return _SQLITE_DENY
    return _SQLITE_OK


def _readonly_uri_for_normalized(normalized_path: str) -> str:
    return f"file:{Path(normalized_path).as_posix()}?mode=ro"


class _GuardedConnection(_ORIG_CONNECTION):
    """`sqlite3.Connection` subclass blocking direct writes and ATTACH escapes to `database.db`."""

    _jarvis_readonly_locked: bool = False

    def __init__(self, database: Any, *args: Any, **kwargs: Any) -> None:
        uri = bool(kwargs.get("uri", False))
        target_norm, mode, is_memory = parse_sqlite_target(database, uri=uri)

        if not is_memory and target_norm in _canonical_db_normalized_set():
            if mode in _READ_WRITE_URI_MODES:
                raise DatabaseWritePermissionError(
                    f"Direct Python SQLite URI mode={mode} on canonical database.db "
                    "is forbidden; Rust SqliteDatabase owns all writes."
                )
            ro_kwargs = dict(kwargs)
            ro_kwargs["uri"] = True
            ro_uri = _readonly_uri_for_normalized(target_norm)
            super().__init__(ro_uri, *args, **ro_kwargs)
            self.execute("PRAGMA query_only = ON")
            super().set_authorizer(_strict_readonly_authorizer)
            object.__setattr__(self, "_jarvis_readonly_locked", True)
            return

        super().__init__(database, *args, **kwargs)
        super().set_authorizer(_attach_jail_authorizer)

    def set_authorizer(self, authorizer_callback: Any) -> Any:
        if getattr(self, "_jarvis_readonly_locked", False):
            raise DatabaseWritePermissionError(
                "Cannot override SQLite authorizer on a canonical database.db read-only connection."
            )
        return super().set_authorizer(authorizer_callback)


def _guarded_sqlite_connect(database: Any, *args: Any, **kwargs: Any) -> sqlite3.Connection:
    uri = bool(kwargs.get("uri", False))
    target_norm, mode, is_memory = parse_sqlite_target(database, uri=uri)
    custom_factory = kwargs.get("factory")

    if not is_memory and target_norm in _canonical_db_normalized_set():
        if mode in _READ_WRITE_URI_MODES:
            raise DatabaseWritePermissionError(
                f"Direct sqlite3.connect(..., mode={mode}) on canonical database.db "
                "is forbidden; Rust SqliteDatabase owns all writes."
            )
        ro_kwargs = dict(kwargs)
        ro_kwargs["uri"] = True
        if custom_factory is None:
            ro_kwargs["factory"] = _GuardedConnection
        ro_uri = _readonly_uri_for_normalized(target_norm)
        conn = _ORIG_CONNECT(ro_uri, *args, **ro_kwargs)
        if not getattr(conn, "_jarvis_readonly_locked", False):
            conn.execute("PRAGMA query_only = ON")
            _ORIG_CONNECTION.set_authorizer(conn, _strict_readonly_authorizer)
            try:
                setattr(conn, "_jarvis_readonly_locked", True)
            except Exception:
                pass
        return conn

    connect_kwargs = dict(kwargs)
    if custom_factory is None:
        connect_kwargs["factory"] = _GuardedConnection
    conn = _ORIG_CONNECT(database, *args, **connect_kwargs)
    if custom_factory is not None:
        _ORIG_CONNECTION.set_authorizer(conn, _attach_jail_authorizer)
    return conn


def install_canonical_db_write_guard() -> None:
    """Installs process-wide worker guards blocking direct Python writes to `database.db`."""
    global _GUARD_INSTALLED
    with _GUARD_LOCK:
        if _GUARD_INSTALLED:
            return
        sqlite3.connect = _guarded_sqlite_connect  # type: ignore[assignment]
        sqlite3.Connection = _GuardedConnection  # type: ignore[misc]
        dbapi2 = sys.modules.get("sqlite3.dbapi2")
        if dbapi2 is not None:
            setattr(dbapi2, "connect", _guarded_sqlite_connect)
            setattr(dbapi2, "Connection", _GuardedConnection)
        _GUARD_INSTALLED = True


def _reset_guard_for_tests() -> None:
    """Test-only helper restoring original `sqlite3` callables after isolated unit tests."""
    global _GUARD_INSTALLED
    with _GUARD_LOCK:
        sqlite3.connect = _ORIG_CONNECT  # type: ignore[assignment]
        sqlite3.Connection = _ORIG_CONNECTION  # type: ignore[misc]
        dbapi2 = sys.modules.get("sqlite3.dbapi2")
        if dbapi2 is not None:
            setattr(dbapi2, "connect", _ORIG_CONNECT)
            setattr(dbapi2, "Connection", _ORIG_CONNECTION)
        _GUARD_INSTALLED = False
