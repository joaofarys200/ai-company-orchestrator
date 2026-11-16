"""Regression tests for Windows windowless subprocess execution, log rotation, and secret scrubbing."""

from __future__ import annotations

import ast
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from backend import process_utils
from backend.model_harness.providers.ollama import OllamaChatProvider


def test_no_window_creation_flags_never_combine_detached_process() -> None:
    if os.name != "nt":
        pytest.skip("Windows-specific creationflags check")

    no_win = process_utils.WIN_CREATE_NO_WINDOW
    detached = process_utils.WIN_DETACHED_PROCESS
    breakaway = process_utils.WIN_CREATE_BREAKAWAY_FROM_JOB
    new_group = process_utils.WIN_CREATE_NEW_PROCESS_GROUP

    flags = process_utils.no_window_creationflags(detached | new_group, allow_breakaway=True)
    assert flags & no_win
    assert flags & breakaway
    assert flags & new_group
    assert (flags & detached) == 0

    si = process_utils.hidden_startupinfo()
    assert si is not None
    assert si.dwFlags & process_utils.WIN_STARTF_USESHOWWINDOW
    assert si.wShowWindow == process_utils.WIN_SW_HIDE

    explicit_console = process_utils.hidden_subprocess_kwargs(
        {"creationflags": process_utils.WIN_CREATE_NEW_CONSOLE}
    )
    assert explicit_console["creationflags"] & process_utils.WIN_CREATE_NEW_CONSOLE


def test_redact_sensitive_text_and_args_masks_secrets() -> None:
    args = [
        "python.exe",
        "--api-key",
        "super-secret-value-123",
        "--token=ghp_1234567890abcdef",
        "GEMINI_API_KEY=AIzaSySecretKey1234567890",
        "Authorization=Bearer bearer_secret_999",
        "https://alice:hunter2@internal.example/hook",
        "sk-live-secret-abcdef123456",
    ]
    cleaned = process_utils.redact_command_args(args)
    assert isinstance(cleaned, list)
    joined = " ".join(cleaned)
    for leaked in (
        "super-secret-value-123",
        "ghp_1234567890abcdef",
        "AIzaSySecretKey1234567890",
        "bearer_secret_999",
        "hunter2",
        "sk-live-secret-abcdef123456",
    ):
        assert leaked not in joined
    assert "[REDACTED]" in joined
    assert cleaned[1] == "--api-key"
    assert cleaned[2] == "[REDACTED]"


def test_rotating_process_log_rotates_and_scrubs_secrets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    monkeypatch.setenv("JARVIS_LOG_DIR", str(logs_dir))
    monkeypatch.setenv("JARVIS_LOG_MAX_BYTES", "1024")
    monkeypatch.setenv("JARVIS_LOG_BACKUPS", "2")

    for idx in range(35):
        process_utils.log_process_event(
            "process_start",
            filename="processes.log",
            target="powershell.exe",
            args=["--api-key", f"secret-{idx}", f"GEMINI_API_KEY=AIzaSySecretValue{idx:04}9999"],
            pid=1000 + idx,
            creationflags=process_utils.no_window_creationflags(),
        )

    assert (logs_dir / "processes.log").is_file()
    assert (logs_dir / "processes.log.1").is_file()
    assert (logs_dir / "processes.log.2").is_file()
    assert not (logs_dir / "processes.log.3").exists()

    all_text = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted(logs_dir.glob("processes.log*"))
    )
    assert "AIzaSySecretValue" not in all_text
    assert "secret-10" not in all_text
    assert "[REDACTED]" in all_text


def test_project_builder_never_sets_detached_process(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    if os.name != "nt":
        pytest.skip("Windows-specific creationflags check")

    from agents.orchestrator import project_builder

    opts = project_builder._process_creation_options()
    assert opts["creationflags"] & process_utils.WIN_CREATE_NO_WINDOW
    assert opts["creationflags"] & process_utils.WIN_CREATE_NEW_PROCESS_GROUP
    assert (opts["creationflags"] & process_utils.WIN_DETACHED_PROCESS) == 0

    captured: list[dict] = []

    class DummyProc:
        pid = 4242

    def fake_popen(cmd, **kwargs):
        captured.append(dict(kwargs))
        return DummyProc()

    proj = tmp_path / "demo_proj"
    proj.mkdir()
    (proj / "index.html").write_text("<h1>ok</h1>", encoding="utf-8")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(project_builder, "_find_free_port", lambda: 45123)
    monkeypatch.setattr(project_builder, "_validate_project_working_directory", lambda p, _: str(proj))
    ok, url = project_builder.start_static_preview(str(proj), None)
    assert ok and url == "http://127.0.0.1:45123/"
    assert len(captured) == 1
    flags = captured[0].get("creationflags", 0)
    assert flags & process_utils.WIN_CREATE_NO_WINDOW
    assert (flags & process_utils.WIN_DETACHED_PROCESS) == 0


def test_ollama_provider_logs_to_ollama_log_without_detached_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("JARVIS_LOG_DIR", str(tmp_path / "logs"))
    provider = OllamaChatProvider(
        base_url="http://127.0.0.1:11434",
        default_model="qwen3.5:9b",
        transport=None,
    )
    calls: list[dict] = []

    class DummyProc:
        pid = 7777

    def fake_popen(cmd, **kwargs):
        calls.append({"cmd": cmd, "kwargs": dict(kwargs)})
        return DummyProc()

    with patch.object(shutil, "which", return_value="ollama.exe"), patch.object(
        subprocess, "Popen", side_effect=fake_popen
    ):
        started = provider._ensure_local_daemon_running()

    assert started is True
    assert len(calls) == 1
    if os.name == "nt":
        flags = calls[0]["kwargs"].get("creationflags", 0)
        assert flags == (
            process_utils.WIN_CREATE_NO_WINDOW | process_utils.WIN_CREATE_BREAKAWAY_FROM_JOB
        )
        assert (flags & process_utils.WIN_DETACHED_PROCESS) == 0
    assert calls[0]["kwargs"].get("stderr") == subprocess.STDOUT
    assert (tmp_path / "logs" / "ollama.log").exists()
    events_text = (tmp_path / "logs" / "processes.log").read_text(encoding="utf-8")
    assert "ollama_start" in events_text


def test_windows_subprocess_guard_and_zero_console_windows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    if os.name != "nt":
        pytest.skip("Windows console window monitoring test")

    import ctypes
    from ctypes import wintypes

    logs_dir = tmp_path / "logs"
    monkeypatch.setenv("JARVIS_LOG_DIR", str(logs_dir))
    process_utils.install_windows_no_window_subprocess_guard()

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    EnumWindows = user32.EnumWindows
    IsWindowVisible = user32.IsWindowVisible
    GetClassNameW = user32.GetClassNameW
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def count_console_windows() -> set[int]:
        found: set[int] = set()
        buf = ctypes.create_unicode_buffer(256)

        @WNDENUMPROC
        def cb(hwnd, _lparam):
            if IsWindowVisible(hwnd):
                GetClassNameW(hwnd, buf, 256)
                if buf.value in ("ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS", "PseudoConsoleWindow"):
                    found.add(int(hwnd))
            return True

        EnumWindows(cb, 0)
        return found

    before = count_console_windows()

    # Bare third-party style shell=True and direct Popen + asyncio calls without explicit creationflags
    res1 = subprocess.run("cmd /c echo ok", shell=True, capture_output=True, text=True, timeout=10)
    assert res1.returncode == 0
    res2 = subprocess.run(
        [sys.executable, "-c", "print('hidden-child')"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert res2.returncode == 0 and "hidden-child" in res2.stdout

    async def _run_async() -> int:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "print('hidden-async')",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await proc.communicate()
        assert b"hidden-async" in out
        return int(proc.returncode or 0)

    assert asyncio.run(_run_async()) == 0
    after = count_console_windows()
    assert after - before == set(), f"New visible console windows appeared: {after - before}"

    entries = [
        json.loads(line.strip())
        for line in (logs_dir / "processes.log").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(e.get("event") == "process_start" for e in entries)
    assert any(e.get("event") == "process_exit" and e.get("exit_code") == 0 for e in entries)


def test_no_unwrapped_subprocess_calls_in_runtime_modules() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    runtime_roots = ("agents", "backend", "intelligence", "services", "security", "workers")
    exempt = {
        Path("backend/process_utils.py"),
    }
    subprocess_methods = {"run", "Popen", "check_output", "check_call", "call"}
    missing: list[str] = []

    py_files: list[Path] = [repo_root / "sandbox.py"]
    for root in runtime_roots:
        py_files.extend((repo_root / root).rglob("*.py"))

    for path in py_files:
        rel = path.relative_to(repo_root)
        if rel in exempt:
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(rel))
        uses_helper_in_file = (
            "hidden_subprocess_kwargs" in source
            or "no_window_creationflags" in source
            or "_process_creation_options" in source
        )
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            call_name = None
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "subprocess"
                and func.attr in subprocess_methods
            ):
                call_name = f"subprocess.{func.attr}"
            elif (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "asyncio"
                and func.attr in {"create_subprocess_exec", "create_subprocess_shell"}
            ):
                call_name = f"asyncio.{func.attr}"
            if call_name is None:
                continue

            has_safe_kwargs = any(
                kw.arg is None
                and (
                    (
                        isinstance(kw.value, ast.Call)
                        and isinstance(kw.value.func, ast.Name)
                        and kw.value.func.id
                        in {"hidden_subprocess_kwargs", "_process_creation_options"}
                    )
                    or (
                        uses_helper_in_file
                        and isinstance(kw.value, ast.Name)
                        and kw.value.id in {"kwargs", "run_kwargs", "popen_kwargs"}
                    )
                )
                for kw in node.keywords
            )
            has_explicit_creationflags = any(
                kw.arg == "creationflags" for kw in node.keywords
            )
            if not (has_safe_kwargs or has_explicit_creationflags):
                missing.append(f"{rel.as_posix()}:{node.lineno} ({call_name})")

    assert not missing, f"Bare subprocess calls missing hidden kwargs/flags: {missing}"
