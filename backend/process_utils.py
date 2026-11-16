"""Windows console-free subprocess helpers, process audit logging, and secret scrubbing.

On Windows release builds (`windows_subsystem = "windows"`), `jarvis-os.exe` runs
without an attached console. Any child or grandchild console binary spawned without
`CREATE_NO_WINDOW` causes Windows to flash a visible Command Prompt / PowerShell
window. This module provides:

1. `no_window_creationflags` / `hidden_startupinfo` / `hidden_subprocess_kwargs`
   (ensuring `DETACHED_PROCESS` and `CREATE_NO_WINDOW` are never combined, while
   allowing `CREATE_BREAKAWAY_FROM_JOB` for Ollama/CUDA).
2. Secret-scrubbed, size-rotated file logging under `<JARVIS_PROJECT_ROOT>/logs/`
   (or `JARVIS_LOG_DIR`).
3. `install_windows_no_window_subprocess_guard()` for `workers/worker_boot.py` so even
   third-party site-packages (`pymupdf`, `pdfplumber`, `imageio_ffmpeg`, `websockets`,
   etc.) inherit console-free execution on Windows.
"""

from __future__ import annotations

import asyncio
import datetime
import functools
import inspect
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, IO, Sequence

WIN_CREATE_NO_WINDOW: int = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
WIN_CREATE_BREAKAWAY_FROM_JOB: int = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0x01000000)
WIN_CREATE_NEW_PROCESS_GROUP: int = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
WIN_DETACHED_PROCESS: int = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
WIN_CREATE_NEW_CONSOLE: int = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)
WIN_STARTF_USESHOWWINDOW: int = getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)
WIN_SW_HIDE: int = getattr(subprocess, "SW_HIDE", 0)

DEFAULT_LOG_MAX_BYTES: int = 5 * 1024 * 1024
DEFAULT_LOG_BACKUP_COUNT: int = 4

_SENSITIVE_CLI_FLAGS = frozenset(
    {
        "--api-key",
        "--apikey",
        "--token",
        "--access-token",
        "--refresh-token",
        "--secret",
        "--password",
        "--passwd",
        "--auth",
        "--auth-token",
        "--bearer",
        "--client-secret",
        "--private-key",
        "--key",
    }
)

_SENSITIVE_KEY_MARKERS = (
    "API_KEY",
    "APIKEY",
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "PASSWD",
    "PRIVATE_KEY",
    "CREDENTIAL",
    "AUTH",
)

_INLINE_SECRET_RE = re.compile(
    r"(?:AIza[0-9A-Za-z_-]{12,}"
    r"|sk-[0-9A-Za-z_-]{12,}"
    r"|gh[pousr]_[0-9A-Za-z_]{12,}"
    r"|github_pat_[0-9A-Za-z_]{12,}"
    r"|xox[baprs]-[0-9A-Za-z-]{10,}"
    r"|hf_[0-9A-Za-z]{12,}"
    r"|glpat-[0-9A-Za-z_-]{12,})"
)
_BEARER_OR_BASIC_RE = re.compile(r"\b(Bearer|Basic)\s+[A-Za-z0-9._+/=-]{6,}", re.IGNORECASE)
_URL_CREDENTIALS_RE = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://[^/\s:@]+:)([^/\s@]+)(@)")
_KV_ASSIGN_RE = re.compile(
    r"(?i)\b([A-Za-z0-9_.-]*(?:api_?key|secret|token|password|passwd|private_key|credential|auth)[A-Za-z0-9_.-]*)\s*([=:])\s*(['\"]?)([^\s'\";,}\]]+)\3"
)

_LOG_LOCK = threading.Lock()
_GUARD_LOCK = threading.Lock()
_GUARD_INSTALLED = False
_ASYNCIO_GUARD_INSTALLED = False
_LOG_GUARD = threading.local()

_REPO_ROOT = Path(__file__).resolve().parent.parent


def resolve_logs_dir() -> Path:
    """Returns the canonical log directory (`%LOCALAPPDATA%\\JarvisOS\\logs` in release)."""
    explicit = str(os.environ.get("JARVIS_LOG_DIR") or "").strip()
    if explicit:
        return Path(explicit)
    project_root = str(os.environ.get("JARVIS_PROJECT_ROOT") or "").strip()
    if project_root:
        return Path(project_root) / "logs"
    return _REPO_ROOT / "logs"


def _log_rotation_limits() -> tuple[int, int]:
    try:
        max_bytes = max(1024, int(os.environ.get("JARVIS_LOG_MAX_BYTES", DEFAULT_LOG_MAX_BYTES)))
    except (TypeError, ValueError):
        max_bytes = DEFAULT_LOG_MAX_BYTES
    try:
        backups = max(0, int(os.environ.get("JARVIS_LOG_BACKUPS", DEFAULT_LOG_BACKUP_COUNT)))
    except (TypeError, ValueError):
        backups = DEFAULT_LOG_BACKUP_COUNT
    return max_bytes, backups


def _is_sensitive_key(name: str) -> bool:
    upper = name.strip().upper().replace("-", "_")
    return any(marker in upper for marker in _SENSITIVE_KEY_MARKERS)


def redact_sensitive_text(text: str, *, max_len: int = 800) -> str:
    """Removes API keys, bearer tokens, credentials, and secret env assignments from text."""
    if not text:
        return ""
    cleaned = text.replace("\r", " ").replace("\n", " ")
    cleaned = _URL_CREDENTIALS_RE.sub(r"\1[REDACTED]\3", cleaned)
    cleaned = _BEARER_OR_BASIC_RE.sub(r"\1 [REDACTED]", cleaned)
    cleaned = _KV_ASSIGN_RE.sub(
        lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}[REDACTED]{m.group(3)}",
        cleaned,
    )
    cleaned = _INLINE_SECRET_RE.sub("[REDACTED]", cleaned)
    if len(cleaned) > max_len:
        return f"{cleaned[:max_len]}...[truncated]"
    return cleaned


def redact_command_args(args: Any) -> list[str] | str:
    """Returns a secret-scrubbed representation of command arguments."""
    if args is None:
        return []
    if isinstance(args, (str, bytes, os.PathLike)):
        text = os.fspath(args)
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="replace")
        return redact_sensitive_text(text)

    if not isinstance(args, Sequence):
        return redact_sensitive_text(str(args))

    out: list[str] = []
    hide_next = False
    for raw in args:
        if isinstance(raw, bytes):
            token = raw.decode("utf-8", errors="replace")
        elif isinstance(raw, os.PathLike):
            token = os.fspath(raw)
        else:
            token = str(raw)

        if hide_next:
            out.append("[REDACTED]")
            hide_next = False
            continue

        lower = token.lower()
        if lower in _SENSITIVE_CLI_FLAGS:
            out.append(token)
            hide_next = True
            continue

        if "=" in token:
            key_part, val_part = token.split("=", 1)
            key_lower = key_part.lower()
            clean_key = key_lower.lstrip("-")
            if (
                key_lower in _SENSITIVE_CLI_FLAGS
                or _is_sensitive_key(clean_key)
                or bool(_INLINE_SECRET_RE.search(val_part))
            ):
                out.append(f"{key_part}=[REDACTED]")
                continue

        out.append(redact_sensitive_text(token))
    return out


def _extract_target(args: Any, executable: Any = None) -> str:
    if executable is not None:
        val = os.fspath(executable) if isinstance(executable, os.PathLike) else str(executable)
        return redact_sensitive_text(val, max_len=240)
    if isinstance(args, (str, bytes, os.PathLike)):
        val = os.fspath(args)
        if isinstance(val, bytes):
            val = val.decode("utf-8", errors="replace")
        parts = val.strip().split(None, 1)
        return redact_sensitive_text(parts[0] if parts else "", max_len=240)
    if isinstance(args, Sequence) and len(args) > 0:
        first = args[0]
        if isinstance(first, bytes):
            first = first.decode("utf-8", errors="replace")
        elif isinstance(first, os.PathLike):
            first = os.fspath(first)
        return redact_sensitive_text(str(first), max_len=240)
    return ""


def _rotate_file_if_needed(path: Path, incoming_len: int, max_bytes: int, backup_count: int) -> None:
    try:
        if not path.exists():
            return
        size = path.stat().st_size
    except OSError:
        return
    if size <= 0 or size + incoming_len <= max_bytes:
        return

    if backup_count <= 0:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        return

    base = str(path)
    for idx in range(backup_count - 1, 0, -1):
        src = Path(f"{base}.{idx}")
        dst = Path(f"{base}.{idx + 1}")
        if src.exists():
            try:
                os.replace(src, dst)
            except OSError:
                pass
    try:
        os.replace(path, Path(f"{base}.1"))
    except OSError:
        pass


def append_rotated_log_line(filename: str, line: str) -> None:
    """Thread-safe, secret-scrubbed, size-rotated line append under `resolve_logs_dir()`."""
    if getattr(_LOG_GUARD, "active", False):
        return
    _LOG_GUARD.active = True
    try:
        logs_dir = resolve_logs_dir()
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / filename
        sanitized = redact_sensitive_text(line, max_len=4000)
        encoded_len = len(sanitized.encode("utf-8", errors="replace")) + 1
        max_bytes, backup_count = _log_rotation_limits()

        with _LOG_LOCK:
            _rotate_file_if_needed(log_path, encoded_len, max_bytes, backup_count)
            with log_path.open("a", encoding="utf-8", errors="replace") as fh:
                fh.write(f"{sanitized}\n")
    except Exception:
        pass
    finally:
        _LOG_GUARD.active = False


def rotate_and_open_process_log_handle(filename: str = "ollama.log") -> IO[bytes]:
    """Rotates `filename` if over size limit and opens it in unbuffered binary append mode."""
    logs_dir = resolve_logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / filename
    max_bytes, backup_count = _log_rotation_limits()
    with _LOG_LOCK:
        _rotate_file_if_needed(log_path, 0, max_bytes, backup_count)
    return log_path.open("ab", buffering=0)


def _caller_summary() -> str:
    try:
        frame = inspect.currentframe()
        if frame is None:
            return "unknown"
        curr = frame.f_back
        skip_suffixes = (
            os.path.normcase(os.path.join("backend", "process_utils.py")),
            os.path.normcase(f"{os.sep}subprocess.py"),
            os.path.normcase("asyncio"),
        )
        while curr is not None:
            filename = os.path.normcase(curr.f_code.co_filename or "")
            if filename and not any(suffix in filename for suffix in skip_suffixes):
                mod = curr.f_globals.get("__name__", "") or Path(filename).stem
                return f"{mod}:{curr.f_code.co_name}:{curr.f_lineno}"
            curr = curr.f_back
    except Exception:
        pass
    return "unknown"


def log_process_event(
    event: str,
    *,
    filename: str = "processes.log",
    target: str = "",
    args: Any = None,
    pid: int | None = None,
    exit_code: int | None = None,
    creationflags: int | None = None,
    starter: str | None = None,
    caller: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Writes a structured JSON process-audit entry to the rotating process log."""
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")
    record: dict[str, Any] = {
        "ts": ts,
        "event": event,
        "starter": starter or Path(sys.executable).name,
        "starter_pid": os.getpid(),
        "worker_role": str(os.environ.get("JARVIS_WORKER_ROLE") or "").strip() or None,
        "caller": caller or _caller_summary(),
        "target": redact_sensitive_text(target, max_len=240) if target else "",
        "args": redact_command_args(args),
    }
    if pid is not None:
        record["pid"] = pid
    if exit_code is not None:
        record["exit_code"] = exit_code
    if creationflags is not None:
        record["creationflags"] = f"0x{int(creationflags):08x}"
    if extra:
        for k, v in extra.items():
            if _is_sensitive_key(str(k)) and v is not None:
                record[k] = "[REDACTED]"
            elif isinstance(v, str):
                record[k] = redact_sensitive_text(v, max_len=500)
            else:
                record[k] = v
    append_rotated_log_line(filename, json.dumps(record, ensure_ascii=False))


def no_window_creationflags(
    base_flags: int = 0,
    *,
    allow_breakaway: bool = False,
    new_process_group: bool = False,
) -> int:
    """Returns Windows `creationflags` with `CREATE_NO_WINDOW` and no `DETACHED_PROCESS`."""
    if os.name != "nt":
        return 0
    flags = int(base_flags or 0)
    # DETACHED_PROCESS + CREATE_NO_WINDOW can conflict / break CUDA detection in children.
    flags &= ~WIN_DETACHED_PROCESS
    flags &= ~WIN_CREATE_NEW_CONSOLE
    flags |= WIN_CREATE_NO_WINDOW
    if allow_breakaway:
        flags |= WIN_CREATE_BREAKAWAY_FROM_JOB
    if new_process_group:
        flags |= WIN_CREATE_NEW_PROCESS_GROUP
    return flags


def hidden_startupinfo(existing: Any = None) -> Any:
    """Returns a Windows `STARTUPINFO` with `STARTF_USESHOWWINDOW` + `SW_HIDE`."""
    if os.name != "nt" or not hasattr(subprocess, "STARTUPINFO"):
        return existing
    si = subprocess.STARTUPINFO()
    if existing is not None:
        for attr in (
            "dwFlags",
            "wShowWindow",
            "hStdInput",
            "hStdOutput",
            "hStdError",
            "lpDesktop",
            "lpTitle",
        ):
            if hasattr(existing, attr):
                try:
                    setattr(si, attr, getattr(existing, attr))
                except Exception:
                    pass
    si.dwFlags = int(getattr(si, "dwFlags", 0) or 0) | WIN_STARTF_USESHOWWINDOW
    si.wShowWindow = WIN_SW_HIDE
    return si


def hidden_subprocess_kwargs(
    existing_kwargs: dict[str, Any] | None = None,
    *,
    allow_breakaway: bool = False,
    new_process_group: bool = False,
    allow_console: bool = False,
    **extra_kwargs: Any,
) -> dict[str, Any]:
    """Builds `subprocess` keyword arguments enforcing windowless execution on Windows."""
    kwargs = dict(existing_kwargs or {})
    if extra_kwargs:
        kwargs.update(extra_kwargs)
    if os.name != "nt":
        return kwargs
    if allow_console:
        return kwargs

    existing_flags = int(kwargs.get("creationflags", 0) or 0)
    # Respect explicit caller opt-out when a visible console was deliberately requested.
    if existing_flags & WIN_CREATE_NEW_CONSOLE:
        return kwargs

    kwargs["creationflags"] = no_window_creationflags(
        existing_flags,
        allow_breakaway=allow_breakaway,
        new_process_group=new_process_group,
    )
    kwargs["startupinfo"] = hidden_startupinfo(kwargs.get("startupinfo"))
    return kwargs


def popen_hidden(args: Any, **kwargs: Any) -> subprocess.Popen[Any]:
    """Starts `subprocess.Popen` without visible console windows on Windows and logs it."""
    allow_breakaway = bool(kwargs.pop("allow_breakaway", False))
    new_process_group = bool(kwargs.pop("new_process_group", False))
    allow_console = bool(kwargs.pop("allow_console", False))
    patched = hidden_subprocess_kwargs(
        kwargs,
        allow_breakaway=allow_breakaway,
        new_process_group=new_process_group,
        allow_console=allow_console,
    )
    caller = _caller_summary()
    target = _extract_target(args, patched.get("executable"))
    if not _GUARD_INSTALLED:
        try:
            proc = subprocess.Popen(args, **patched)
        except Exception as exc:
            log_process_event(
                "process_error",
                target=target,
                args=args,
                creationflags=patched.get("creationflags"),
                caller=caller,
                extra={"error": f"{type(exc).__name__}: {exc}"},
            )
            raise
        log_process_event(
            "process_start",
            target=target,
            args=args,
            pid=getattr(proc, "pid", None),
            creationflags=patched.get("creationflags"),
            caller=caller,
        )
        return proc
    return subprocess.Popen(args, **patched)


def run_hidden(args: Any, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
    """Runs `subprocess.run` without visible console windows on Windows and logs it."""
    allow_breakaway = bool(kwargs.pop("allow_breakaway", False))
    new_process_group = bool(kwargs.pop("new_process_group", False))
    allow_console = bool(kwargs.pop("allow_console", False))
    patched = hidden_subprocess_kwargs(
        kwargs,
        allow_breakaway=allow_breakaway,
        new_process_group=new_process_group,
        allow_console=allow_console,
    )
    caller = _caller_summary()
    target = _extract_target(args, patched.get("executable"))
    if not _GUARD_INSTALLED:
        started_at = time.perf_counter()
        log_process_event(
            "process_start",
            target=target,
            args=args,
            creationflags=patched.get("creationflags"),
            caller=caller,
        )
        try:
            completed = subprocess.run(args, **patched)
        except Exception as exc:
            log_process_event(
                "process_error",
                target=target,
                args=args,
                creationflags=patched.get("creationflags"),
                caller=caller,
                extra={"error": f"{type(exc).__name__}: {exc}"},
            )
            raise
        log_process_event(
            "process_exit",
            target=target,
            args=args,
            exit_code=int(completed.returncode),
            creationflags=patched.get("creationflags"),
            caller=caller,
            extra={"duration_ms": round((time.perf_counter() - started_at) * 1000.0, 2)},
        )
        return completed
    return subprocess.run(args, **patched)


def _record_exit_if_finished(proc: subprocess.Popen[Any]) -> None:
    try:
        if getattr(proc, "_jarvis_exit_logged", False):
            return
        rc = getattr(proc, "returncode", None)
        if rc is None:
            return
        proc._jarvis_exit_logged = True  # type: ignore[attr-defined]
        started_at = getattr(proc, "_jarvis_started_at", None)
        duration_ms = (
            round((time.perf_counter() - started_at) * 1000.0, 2)
            if isinstance(started_at, (int, float))
            else None
        )
        log_process_event(
            "process_exit",
            target=str(getattr(proc, "_jarvis_target", "")),
            args=getattr(proc, "args", None),
            pid=getattr(proc, "pid", None),
            exit_code=int(rc),
            creationflags=getattr(proc, "_jarvis_creationflags", None),
            caller=str(getattr(proc, "_jarvis_caller", "") or "unknown"),
            extra={"duration_ms": duration_ms} if duration_ms is not None else None,
        )
    except Exception:
        pass


def _install_asyncio_subprocess_guard() -> None:
    global _ASYNCIO_GUARD_INSTALLED
    if _ASYNCIO_GUARD_INSTALLED or os.name != "nt":
        return

    try:
        from asyncio.base_events import BaseEventLoop
    except Exception:
        return

    orig_subproc_exec = BaseEventLoop.subprocess_exec
    orig_subproc_shell = BaseEventLoop.subprocess_shell

    @functools.wraps(orig_subproc_exec)
    async def _guarded_subproc_exec(self, protocol_factory, program, *args, **kwargs):  # type: ignore[no-untyped-def]
        allow_console = bool(kwargs.pop("_jarvis_allow_console", False))
        patched = hidden_subprocess_kwargs(kwargs, allow_console=allow_console)
        caller = _caller_summary()
        cmd_preview = [program, *args]
        flags = patched.get("creationflags")
        try:
            transport, protocol = await orig_subproc_exec(
                self, protocol_factory, program, *args, **patched
            )
        except Exception as exc:
            log_process_event(
                "process_error",
                target=str(program),
                args=cmd_preview,
                creationflags=flags,
                caller=caller,
                extra={"error": f"{type(exc).__name__}: {exc}", "async": True},
            )
            raise
        pid = transport.get_pid() if hasattr(transport, "get_pid") else None
        log_process_event(
            "process_start",
            target=str(program),
            args=cmd_preview,
            pid=pid,
            creationflags=flags,
            caller=caller,
            extra={"async": True},
        )
        return transport, protocol

    @functools.wraps(orig_subproc_shell)
    async def _guarded_subproc_shell(self, protocol_factory, cmd, **kwargs):  # type: ignore[no-untyped-def]
        allow_console = bool(kwargs.pop("_jarvis_allow_console", False))
        patched = hidden_subprocess_kwargs(kwargs, allow_console=allow_console)
        caller = _caller_summary()
        flags = patched.get("creationflags")
        try:
            transport, protocol = await orig_subproc_shell(
                self, protocol_factory, cmd, **patched
            )
        except Exception as exc:
            log_process_event(
                "process_error",
                target="cmd.exe" if os.name == "nt" else "/bin/sh",
                args=cmd,
                creationflags=flags,
                caller=caller,
                extra={"error": f"{type(exc).__name__}: {exc}", "async": True, "shell": True},
            )
            raise
        pid = transport.get_pid() if hasattr(transport, "get_pid") else None
        log_process_event(
            "process_start",
            target="cmd.exe" if os.name == "nt" else "/bin/sh",
            args=cmd,
            pid=pid,
            creationflags=flags,
            caller=caller,
            extra={"async": True, "shell": True},
        )
        return transport, protocol

    BaseEventLoop.subprocess_exec = _guarded_subproc_exec  # type: ignore[method-assign]
    BaseEventLoop.subprocess_shell = _guarded_subproc_shell  # type: ignore[method-assign]
    _ASYNCIO_GUARD_INSTALLED = True


def install_windows_no_window_subprocess_guard() -> bool:
    """Installs process-wide default `CREATE_NO_WINDOW` + audit logging for `subprocess` & `asyncio`.

    Idempotent. Safe to call in `worker_boot.py` before importing domain/third-party modules.
    Ensures third-party libraries (`pymupdf`, `pdfplumber`, `imageio_ffmpeg`, `websockets`, etc.)
    never spawn flashing Windows console windows.
    """
    global _GUARD_INSTALLED
    with _GUARD_LOCK:
        if _GUARD_INSTALLED:
            return False

        orig_popen_init = subprocess.Popen.__init__
        orig_popen_wait = subprocess.Popen.wait
        orig_popen_poll = subprocess.Popen.poll
        orig_popen_comm = subprocess.Popen.communicate

        @functools.wraps(orig_popen_init)
        def _guarded_popen_init(self, args, *pargs, **kwargs):  # type: ignore[no-untyped-def]
            allow_console = bool(kwargs.pop("_jarvis_allow_console", False))
            if os.name == "nt" and not allow_console:
                existing_flags = int(kwargs.get("creationflags", 0) or 0)
                if not (existing_flags & WIN_CREATE_NEW_CONSOLE):
                    kwargs["creationflags"] = no_window_creationflags(existing_flags)
                if kwargs.get("startupinfo") is None:
                    kwargs["startupinfo"] = hidden_startupinfo()

            caller = _caller_summary()
            target = _extract_target(args, kwargs.get("executable"))
            applied_flags = kwargs.get("creationflags")
            started_at = time.perf_counter()
            self._jarvis_target = target  # type: ignore[attr-defined]
            self._jarvis_caller = caller  # type: ignore[attr-defined]
            self._jarvis_started_at = started_at  # type: ignore[attr-defined]
            self._jarvis_creationflags = applied_flags  # type: ignore[attr-defined]
            self._jarvis_exit_logged = False  # type: ignore[attr-defined]

            try:
                orig_popen_init(self, args, *pargs, **kwargs)
            except Exception as exc:
                log_process_event(
                    "process_error",
                    target=target,
                    args=args,
                    creationflags=applied_flags,
                    caller=caller,
                    extra={"error": f"{type(exc).__name__}: {exc}"},
                )
                raise

            log_process_event(
                "process_start",
                target=target,
                args=args,
                pid=getattr(self, "pid", None),
                creationflags=applied_flags,
                caller=caller,
            )

        @functools.wraps(orig_popen_wait)
        def _guarded_popen_wait(self, *pargs, **kwargs):  # type: ignore[no-untyped-def]
            res = orig_popen_wait(self, *pargs, **kwargs)
            _record_exit_if_finished(self)
            return res

        @functools.wraps(orig_popen_poll)
        def _guarded_popen_poll(self, *pargs, **kwargs):  # type: ignore[no-untyped-def]
            res = orig_popen_poll(self, *pargs, **kwargs)
            if res is not None:
                _record_exit_if_finished(self)
            return res

        @functools.wraps(orig_popen_comm)
        def _guarded_popen_comm(self, *pargs, **kwargs):  # type: ignore[no-untyped-def]
            try:
                return orig_popen_comm(self, *pargs, **kwargs)
            finally:
                _record_exit_if_finished(self)

        subprocess.Popen.__init__ = _guarded_popen_init  # type: ignore[method-assign]
        subprocess.Popen.wait = _guarded_popen_wait  # type: ignore[method-assign]
        subprocess.Popen.poll = _guarded_popen_poll  # type: ignore[method-assign]
        subprocess.Popen.communicate = _guarded_popen_comm  # type: ignore[method-assign]

        _install_asyncio_subprocess_guard()
        _GUARD_INSTALLED = True
        return True
