from __future__ import annotations

import argparse
from contextlib import closing
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import os
import sqlite3
import sys
import tempfile
from typing import Callable, Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from persistence.db import CANONICAL_DB_PATH

RHO_BUSY_TIMEOUT_MS = 30_000
RHO_SCHEMA_USER_VERSION = 1

RHO_TABLES_DDL: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS model_trajectories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id TEXT NOT NULL,
        task_profile TEXT NOT NULL,
        fingerprint TEXT NOT NULL,
        status TEXT NOT NULL,
        attempts_count INTEGER NOT NULL,
        failure_reason TEXT,
        created_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rho_compounding_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_profile TEXT NOT NULL,
        rule_text TEXT NOT NULL,
        failure_trigger TEXT NOT NULL,
        occurrences INTEGER DEFAULT 1,
        created_at REAL NOT NULL
    )
    """,
)

RHO_INDEXES_DDL: tuple[tuple[str, str], ...] = (
    (
        "idx_model_trajectories_pattern",
        """
        CREATE INDEX IF NOT EXISTS idx_model_trajectories_pattern
        ON model_trajectories (task_profile, failure_reason, created_at)
        """,
    ),
    (
        "idx_model_trajectories_request_id",
        """
        CREATE INDEX IF NOT EXISTS idx_model_trajectories_request_id
        ON model_trajectories (request_id)
        """,
    ),
    (
        "idx_model_trajectories_fingerprint",
        """
        CREATE INDEX IF NOT EXISTS idx_model_trajectories_fingerprint
        ON model_trajectories (fingerprint)
        """,
    ),
    (
        "idx_rho_rules_task_profile_id",
        """
        CREATE INDEX IF NOT EXISTS idx_rho_rules_task_profile_id
        ON rho_compounding_rules (task_profile, id DESC)
        """,
    ),
    (
        "idx_rho_rules_trigger",
        """
        CREATE INDEX IF NOT EXISTS idx_rho_rules_trigger
        ON rho_compounding_rules (task_profile, failure_trigger)
        """,
    ),
)

TRAJECTORY_COLUMNS = (
    "id",
    "request_id",
    "task_profile",
    "fingerprint",
    "status",
    "attempts_count",
    "failure_reason",
    "created_at",
)

RULE_COLUMNS = (
    "id",
    "task_profile",
    "rule_text",
    "failure_trigger",
    "occurrences",
    "created_at",
)


class RhoMigrationError(RuntimeError):
    """Raised when RHO migration validation, copy, or rollback fails."""


class RhoMigrationSafetyError(RhoMigrationError, ValueError):
    """Raised when a Stage 1 RHO migration targets a forbidden production path."""


@dataclass(frozen=True)
class RhoMigrationReport:
    source_path: str
    target_path: str
    source_trajectories: int
    target_trajectories: int
    source_rules: int
    target_rules: int
    source_trajectories_sha256: str
    target_trajectories_sha256: str
    source_rules_sha256: str
    target_rules_sha256: str
    integrity_ok: bool
    user_version: int
    indexes: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def get_default_sandbox_root() -> Path:
    """Return the canonical absolute path of the Stage 1 temporary sandbox root."""
    return Path(os.path.realpath(tempfile.gettempdir()))


def _collect_protected_file_ids(paths: Iterable[Path]) -> set[tuple[int, int]]:
    file_ids: set[tuple[int, int]] = set()
    for path in paths:
        try:
            st = os.stat(path)
        except OSError:
            continue
        if st.st_ino:
            file_ids.add((st.st_dev, st.st_ino))
    return file_ids


def assert_sandbox_target_path(
    target_path: Path | str,
    source_path: Path | str,
    *,
    sandbox_root: Path | str | None = None,
) -> Path:
    """
    Enforce Stage 1 sandbox-only allowlist:
    - Target must resolve canonically inside the approved temporary sandbox root.
    - Target cannot equal the source path or protected production paths/directories.
    - Symlinks and hard-linked file aliases (`st_nlink > 1` or matching inode) are rejected.
    """
    raw_target = Path(target_path).expanduser()
    raw_source = Path(source_path).expanduser()

    resolved_root = Path(
        os.path.realpath(
            str(Path(sandbox_root).expanduser() if sandbox_root is not None else tempfile.gettempdir())
        )
    )
    resolved_target = Path(os.path.realpath(str(raw_target)))
    resolved_source = Path(os.path.realpath(str(raw_source)))

    forbidden_paths = (
        Path(os.path.realpath(str(CANONICAL_DB_PATH))),
        Path(os.path.realpath(str(PROJECT_ROOT / "database.db.pre-tauri.bak"))),
        Path(os.path.realpath(str(PROJECT_ROOT / "data" / "rho.db"))),
    )
    data_dir = Path(os.path.realpath(str(PROJECT_ROOT / "data")))

    if resolved_target == resolved_source:
        raise RhoMigrationSafetyError(
            f"Target path cannot equal source path: {resolved_target}"
        )
    if resolved_target in forbidden_paths or resolved_target.is_relative_to(data_dir):
        raise RhoMigrationSafetyError(
            f"Stage 1 safety guard blocked non-sandbox target path: {resolved_target}. "
            "Production RHO migration is forbidden in Stage 1."
        )
    if resolved_target == resolved_root or not resolved_target.is_relative_to(resolved_root):
        raise RhoMigrationSafetyError(
            f"Stage 1 safety guard blocked target outside approved sandbox root ({resolved_root}): "
            f"{resolved_target}. Stage 1 RHO migration requires a temporary sandbox destination."
        )

    protected_ids = _collect_protected_file_ids((*forbidden_paths, resolved_source))
    for suffix in ("", "-wal", "-shm"):
        candidate_raw = Path(f"{raw_target}{suffix}")
        candidate_resolved = Path(f"{resolved_target}{suffix}")
        if candidate_raw.is_symlink() or candidate_resolved.is_symlink():
            raise RhoMigrationSafetyError(
                f"Stage 1 safety guard blocked symlink target or WAL sidecar: {candidate_raw}"
            )
        try:
            st = os.stat(candidate_resolved)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise RhoMigrationSafetyError(
                f"Stage 1 safety guard could not inspect target path {candidate_resolved}: {exc}"
            ) from exc
        if st.st_nlink > 1 or (st.st_ino and (st.st_dev, st.st_ino) in protected_ids):
            raise RhoMigrationSafetyError(
                f"Stage 1 safety guard blocked hard-linked or protected inode alias: "
                f"{candidate_resolved} (st_nlink={st.st_nlink})."
            )

    return resolved_target


def compute_table_snapshot(
    conn: sqlite3.Connection,
    table_name: str,
    columns: Iterable[str],
) -> tuple[int, str]:
    """Return deterministic (row_count, sha256_hex) over all ordered rows of a table."""
    cols = tuple(columns)
    col_sql = ", ".join(cols)
    cursor = conn.execute(f"SELECT {col_sql} FROM {table_name} ORDER BY id ASC")
    hasher = hashlib.sha256()
    count = 0
    for row in cursor:
        payload = json.dumps(list(row), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        hasher.update(payload)
        hasher.update(b"\n")
        count += 1
    return count, hasher.hexdigest()


def _open_readonly_source(source_path: Path) -> sqlite3.Connection:
    if not source_path.exists():
        raise RhoMigrationError(f"Source database does not exist: {source_path}")
    resolved = source_path.resolve(strict=True)
    conn = sqlite3.connect(
        f"{resolved.as_uri()}?mode=ro",
        uri=True,
        timeout=30.0,
    )
    conn.execute(f"PRAGMA busy_timeout={RHO_BUSY_TIMEOUT_MS}")
    return conn


def _open_target_connection(target_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(
        str(target_path),
        timeout=30.0,
        isolation_level=None,
    )
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute(f"PRAGMA busy_timeout={RHO_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _check_sqlite_integrity(conn: sqlite3.Connection, label: str) -> None:
    integrity = conn.execute("PRAGMA integrity_check").fetchall()
    if integrity != [("ok",)]:
        raise RhoMigrationError(f"{label} failed PRAGMA integrity_check: {integrity!r}")
    fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk_violations:
        raise RhoMigrationError(f"{label} failed PRAGMA foreign_key_check: {fk_violations!r}")


def _cleanup_aborted_fresh_target(target_path: Path) -> None:
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(f"{target_path}{suffix}")
        try:
            if candidate.exists():
                candidate.unlink()
        except OSError:
            pass


def migrate_rho_db(
    source_path: Path | str,
    target_path: Path | str,
    *,
    verify_sha256: bool = True,
    sandbox_root: Path | str | None = None,
    fault_hook: Callable[[str, sqlite3.Connection], None] | None = None,
) -> RhoMigrationReport:
    """
    Atomically extract `model_trajectories` and `rho_compounding_rules` from a source
    SQLite database into a sandbox target SQLite database with full integrity and SHA256 parity.
    """
    resolved_source = Path(os.path.realpath(str(Path(source_path).expanduser())))
    resolved_target = assert_sandbox_target_path(
        target_path,
        resolved_source,
        sandbox_root=sandbox_root,
    )
    resolved_target.parent.mkdir(parents=True, exist_ok=True)
    target_existed_before = resolved_target.exists()

    with closing(_open_readonly_source(resolved_source)) as src:
        _check_sqlite_integrity(src, "Source database")
        existing_tables = {
            row[0]
            for row in src.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        missing = [
            name for name in ("model_trajectories", "rho_compounding_rules")
            if name not in existing_tables
        ]
        if missing:
            raise RhoMigrationError(
                f"Source database missing required RHO table(s): {', '.join(missing)}"
            )

        src_traj_rows = src.execute(
            f"SELECT {', '.join(TRAJECTORY_COLUMNS)} FROM model_trajectories ORDER BY id ASC"
        ).fetchall()
        src_rule_rows = src.execute(
            f"SELECT {', '.join(RULE_COLUMNS)} FROM rho_compounding_rules ORDER BY id ASC"
        ).fetchall()
        src_traj_count, src_traj_sha = compute_table_snapshot(
            src, "model_trajectories", TRAJECTORY_COLUMNS
        )
        src_rule_count, src_rule_sha = compute_table_snapshot(
            src, "rho_compounding_rules", RULE_COLUMNS
        )

    tgt = _open_target_connection(resolved_target)
    try:
        try:
            tgt.execute("BEGIN IMMEDIATE")

            for ddl in RHO_TABLES_DDL:
                tgt.execute(ddl)

            existing_traj = tgt.execute("SELECT COUNT(*) FROM model_trajectories").fetchone()[0]
            existing_rules = tgt.execute("SELECT COUNT(*) FROM rho_compounding_rules").fetchone()[0]
            if existing_traj or existing_rules:
                raise RhoMigrationError(
                    f"Sandbox target {resolved_target} already contains RHO rows "
                    f"(trajectories={existing_traj}, rules={existing_rules}); aborting to avoid overwrite."
                )

            if fault_hook is not None:
                fault_hook("before_trajectories", tgt)

            tgt.executemany(
                f"INSERT INTO model_trajectories ({', '.join(TRAJECTORY_COLUMNS)}) "
                f"VALUES ({', '.join('?' for _ in TRAJECTORY_COLUMNS)})",
                src_traj_rows,
            )

            if fault_hook is not None:
                fault_hook("after_trajectories", tgt)

            tgt.executemany(
                f"INSERT INTO rho_compounding_rules ({', '.join(RULE_COLUMNS)}) "
                f"VALUES ({', '.join('?' for _ in RULE_COLUMNS)})",
                src_rule_rows,
            )

            if fault_hook is not None:
                fault_hook("after_rules", tgt)

            for _, index_ddl in RHO_INDEXES_DDL:
                tgt.execute(index_ddl)

            tgt.execute(f"PRAGMA user_version={RHO_SCHEMA_USER_VERSION}")

            if fault_hook is not None:
                fault_hook("before_commit", tgt)

            tgt.execute("COMMIT")
        except Exception:
            try:
                if tgt.in_transaction:
                    tgt.execute("ROLLBACK")
            finally:
                tgt.close()
                if not target_existed_before:
                    _cleanup_aborted_fresh_target(resolved_target)
            raise

        _check_sqlite_integrity(tgt, "Target sandbox RHO database")
        tgt_traj_count, tgt_traj_sha = compute_table_snapshot(
            tgt, "model_trajectories", TRAJECTORY_COLUMNS
        )
        tgt_rule_count, tgt_rule_sha = compute_table_snapshot(
            tgt, "rho_compounding_rules", RULE_COLUMNS
        )

        if tgt_traj_count != src_traj_count or tgt_rule_count != src_rule_count:
            raise RhoMigrationError(
                f"Row count mismatch after migration: "
                f"trajectories {src_traj_count} != {tgt_traj_count}, "
                f"rules {src_rule_count} != {tgt_rule_count}"
            )
        if verify_sha256 and (tgt_traj_sha != src_traj_sha or tgt_rule_sha != src_rule_sha):
            raise RhoMigrationError(
                "Deterministic row SHA256 digest mismatch between source and target RHO tables"
            )

        indexes = [
            row[0]
            for row in tgt.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND name NOT LIKE 'sqlite_autoindex%' ORDER BY name ASC"
            ).fetchall()
        ]
        user_version = int(tgt.execute("PRAGMA user_version").fetchone()[0])
    finally:
        try:
            tgt.close()
        except sqlite3.Error:
            pass

    return RhoMigrationReport(
        source_path=str(resolved_source),
        target_path=str(resolved_target),
        source_trajectories=src_traj_count,
        target_trajectories=tgt_traj_count,
        source_rules=src_rule_count,
        target_rules=tgt_rule_count,
        source_trajectories_sha256=src_traj_sha,
        target_trajectories_sha256=tgt_traj_sha,
        source_rules_sha256=src_rule_sha,
        target_rules_sha256=tgt_rule_sha,
        integrity_ok=True,
        user_version=user_version,
        indexes=indexes,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage 1 Sandbox-only RHO SQLite extractor & integrity verifier"
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=CANONICAL_DB_PATH,
        help="Source SQLite database path (opened read-only)",
    )
    parser.add_argument(
        "--target",
        type=Path,
        required=True,
        help="Sandbox target SQLite database path for RHO tables",
    )
    args = parser.parse_args(argv)
    report = migrate_rho_db(args.source, args.target)
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
