import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from intelligence.coding_session import CodingSessionService
from intelligence.project_context import ProjectContextService


BYTE_CASES = [
    pytest.param(b'function value() {\n  return "old";\n}\n', id="lf"),
    pytest.param(b'function value() {\r\n  return "old";\r\n}\r\n', id="crlf"),
    pytest.param(b'function value() {\n  return "old";\n}', id="no-final-newline"),
    pytest.param('function value() {\n  return "Ol\u00e1";\n}\n'.encode("utf-8"), id="utf8"),
]


@pytest.mark.skipif(shutil.which("git") is None, reason="git indisponivel")
@pytest.mark.skipif(shutil.which("node") is None, reason="node indisponivel")
@pytest.mark.parametrize("original_bytes", BYTE_CASES)
def test_git_checkpoint_preserves_exact_worktree_bytes(tmp_path: Path, original_bytes: bytes):
    root = tmp_path / "workspace" / "projects" / "git-bytes"
    root.mkdir(parents=True)
    source = root / "app.js"
    source.write_bytes(original_bytes)
    (root / ".gitattributes").write_bytes(b"* text=auto\n")
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "core.autocrlf", "true"],
        check=True,
        capture_output=True,
    )

    projects = ProjectContextService(workspace_root=str(tmp_path))
    projects.index_project("git-bytes")
    sessions = CodingSessionService(projects)
    session = sessions.create_session("git-bytes", "Alterar value", [{
        "file": "app.js",
        "operation": "replace_symbol",
        "symbol": "value",
        "new_code": 'function value() {\n  return "new";\n}',
        "reason": "Exercitar checkpoint binario Git.",
    }])

    applied = sessions.apply_session("git-bytes", session.session_id)

    assert applied.status == "SUCCEEDED"
    record = applied.checkpoint["files"]["app.js"]
    original_sha256 = hashlib.sha256(original_bytes).hexdigest()
    assert record == {
        **record,
        "relative_path": "app.js",
        "checkpoint_method": "git_blob",
        "original_sha256": original_sha256,
        "size_bytes": len(original_bytes),
        "existed_before": True,
    }
    assert record["git_blob_oid"]

    restored = sessions.rollback_session("git-bytes", session.session_id, confirmed=True)

    restored_bytes = source.read_bytes()
    assert restored.status == "ROLLED_BACK"
    assert restored_bytes == original_bytes
    assert hashlib.sha256(restored_bytes).hexdigest() == original_sha256
