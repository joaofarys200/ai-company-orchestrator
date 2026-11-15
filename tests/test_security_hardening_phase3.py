from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.atomic_io import (
    atomic_write_bytes,
    atomic_write_json,
    atomic_write_text,
)
from services.url_ssrf_guard import (
    is_forbidden_ip,
    validate_remote_url,
    validate_remote_url_syntax,
)
from workspace_policy import validate_local_command


def test_atomic_io_writes_atomically_with_zero_leftover_tmp_files(tmp_path: Path):
    target_json = tmp_path / "nested" / "state.json"
    atomic_write_json(target_json, {"step": 1, "status": "ok"})
    assert target_json.is_file()
    assert not list(target_json.parent.glob("*.tmp"))

    # Overwrite cleanly without residual temp files
    atomic_write_json(target_json, {"step": 2, "status": "updated"})
    assert '"step": 2' in target_json.read_text(encoding="utf-8")
    assert not list(target_json.parent.glob("*.tmp"))

    target_bin = tmp_path / "payload.bin"
    atomic_write_bytes(target_bin, b"\x00\x01\x02hello")
    assert target_bin.read_bytes() == b"\x00\x01\x02hello"
    assert not list(tmp_path.glob("*.tmp"))


def test_atomic_io_preserves_original_file_and_cleans_tmp_on_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    target = tmp_path / "critical.json"
    atomic_write_text(target, '{"intact": true}')

    def fail_replace(src, dst):
        raise OSError("simulated power loss during replace")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated power loss"):
        atomic_write_text(target, '{"corrupt": false}')

    assert target.read_text(encoding="utf-8") == '{"intact": true}'
    assert not list(tmp_path.glob("*.tmp"))


def test_ssrf_guard_blocks_cgnat_mapped_ipv6_credentials_and_fail_closed_dns(
    monkeypatch: pytest.MonkeyPatch,
):
    for bad_ip in [
        "127.0.0.1",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.50",
        "169.254.169.254",
        "100.64.10.20",
        "0.0.0.0",
        "198.18.0.10",
        "::1",
        "fe80::1",
        "fc00::1",
        "::ffff:127.0.0.1",
        "::ffff:169.254.169.254",
    ]:
        assert is_forbidden_ip(bad_ip), f"expected forbidden IP: {bad_ip}"

    assert not is_forbidden_ip("93.184.216.34")

    for bad_url in [
        "file:///C:/Windows/win.ini",
        "http://127.0.0.1:8000/video.mp4",
        "http://[::ffff:127.0.0.1]/video.mp4",
        "http://100.64.0.1/video.mp4",
        "https://user:pass@youtube.com/watch?v=dQw4w9WgXcQ",
        "http://internal-nas.local/video.mp4",
        "http://metadata.internal/latest",
        "http://0x7f000001/video.mp4",
        "http://2130706433/video.mp4",
    ]:
        with pytest.raises(ValueError, match="SECURITY_VIOLATION"):
            validate_remote_url_syntax(bad_url)

    def raise_gaierror(*args, **kwargs):
        raise socket.gaierror("DNS lookup failed")

    monkeypatch.setattr(socket, "getaddrinfo", raise_gaierror)
    with pytest.raises(ValueError, match="fail-closed"):
        validate_remote_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ", resolve_dns=True)

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))],
    )
    ok = validate_remote_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ", resolve_dns=True)
    assert ok["hostname"] == "www.youtube.com"
    assert ok["resolved_ips"] == ["93.184.216.34"]


def test_workspace_policy_command_guard_blocks_shells_metachars_and_preserves_safe_cmds():
    assert validate_local_command("python --version") == (True, "")
    assert validate_local_command("python -m pytest -q")[0] is True
    assert validate_local_command("git status")[0] is True

    blocked_commands = [
        "",
        "python --version && calc.exe",
        "python --version | more",
        "python --version; whoami",
        "powershell -Command Get-Process",
        "cmd.exe /c dir",
        'python -c "import os; os.system(\'whoami\')"',
        "python \"unclosed",
        "Remove-Item important.txt",
        "taskkill /F /PID 1234",
        "Get-Content ..\\secret.txt",
        "Get-Content C:\\Windows\\win.ini",
    ]
    for cmd in blocked_commands:
        allowed, reason = validate_local_command(cmd)
        assert not allowed, f"expected blocked command: {cmd!r}"
        assert reason
