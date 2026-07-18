import hashlib
import os
import shutil
from pathlib import Path

import pytest

from intelligence.coding_session import CodingSessionService
from intelligence.project_context import MAX_VIEW_FILE_BYTES, ProjectContextService


FORMAT_CASES = [
    pytest.param(
        b"function value() {\n  return 1;\n}\n",
        b"function value() {\n  return 2;\n}\n",
        "utf-8",
        "lf",
        True,
        id="lf",
    ),
    pytest.param(
        b"function value() {\r\n  return 1;\r\n}\r\n",
        b"function value() {\r\n  return 2;\r\n}\r\n",
        "utf-8",
        "crlf",
        True,
        id="crlf",
    ),
    pytest.param(
        b"\xef\xbb\xbffunction value() {\n  return 1;\n}\n",
        b"\xef\xbb\xbffunction value() {\n  return 2;\n}\n",
        "utf-8-sig",
        "lf",
        True,
        id="utf8-bom",
    ),
    pytest.param(
        b"function value() {\n  return 1;\n}",
        b"function value() {\n  return 2;\n}",
        "utf-8",
        "lf",
        False,
        id="no-final-newline",
    ),
]


def make_text_project(tmp_path: Path, original: bytes, project_id: str = "atomic-text"):
    root = tmp_path / "workspace" / "projects" / project_id
    root.mkdir(parents=True)
    (root / "app.js").write_bytes(original)
    (root / "index.html").write_bytes(b'<script src="app.js"></script>\n')
    projects = ProjectContextService(workspace_root=str(tmp_path))
    projects.index_project(project_id)
    return CodingSessionService(projects), projects, root


@pytest.mark.skipif(shutil.which("node") is None, reason="node indisponivel")
@pytest.mark.parametrize("original,expected,encoding,newline,final_newline", FORMAT_CASES)
def test_atomic_text_patch_preserves_format(
    tmp_path: Path,
    original: bytes,
    expected: bytes,
    encoding: str,
    newline: str,
    final_newline: bool,
):
    sessions, _projects, root = make_text_project(tmp_path, original)
    session = sessions.create_session("atomic-text", "Alterar retorno", [{
        "file": "app.js",
        "operation": "replace_text",
        "old_text": "return 1;",
        "new_text": "return 2;",
        "reason": "Alteracao localizada.",
    }])

    applied = sessions.apply_session("atomic-text", session.session_id)

    assert applied.status == "SUCCEEDED"
    assert (root / "app.js").read_bytes() == expected
    metadata = applied.applied_changes[0]
    assert metadata["physical_write_strategy"] == "atomic_full_file_replace"
    assert metadata["encoding"] == encoding
    assert metadata["newline"] == newline
    assert metadata["final_newline"] is final_newline
    assert metadata["changed_line_count"] == 1
    assert metadata["full_file_logical_rewrite"] is False
    sessions.rollback_session("atomic-text", session.session_id, confirmed=True)
    assert (root / "app.js").read_bytes() == original


def test_atomic_replace_failure_does_not_corrupt_original(tmp_path: Path, monkeypatch):
    path = tmp_path / "app.js"
    original = b"const value = 1;\r\n"
    path.write_bytes(original)

    def fail_replace(_source, _destination):
        raise OSError("injected replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected replace failure"):
        CodingSessionService._atomic_replace_bytes(str(path), b"const value = 2;\r\n")

    assert path.read_bytes() == original
    assert not list(tmp_path.glob("*.jarvis-tmp"))
    assert not list(tmp_path.glob(".*.jarvis-tmp"))


@pytest.mark.skipif(shutil.which("node") is None, reason="node indisponivel")
def test_large_logical_patch_is_atomic_and_unrelated_file_is_unchanged(tmp_path: Path):
    prefix = b"// context line\n" * ((MAX_VIEW_FILE_BYTES // 16) + 2000)
    original = prefix + b"function compute(value) { return value + 1; }\n"
    sessions, projects, root = make_text_project(tmp_path, original, "large-atomic")
    context = projects.open_project("large-atomic")
    unrelated_before = hashlib.sha256((root / "index.html").read_bytes()).hexdigest()
    metadata_before = context.ast_index["files"]["app.js"]
    session = sessions.create_session("large-atomic", "Alterar compute", [{
        "file": "app.js",
        "operation": "replace_symbol",
        "symbol": "compute",
        "new_code": "function compute(value) { return value + 2; }",
        "reason": "Alteracao localizada em ficheiro grande.",
    }])

    applied = sessions.apply_session("large-atomic", session.session_id)

    expected = original.replace(b"value + 1", b"value + 2", 1)
    write = applied.applied_changes[0]
    assert len(original) > MAX_VIEW_FILE_BYTES
    assert metadata_before["hash_available"] is True
    assert "app.js" not in projects.read_project_files("large-atomic")
    assert applied.status == "SUCCEEDED"
    assert (root / "app.js").read_bytes() == expected
    assert write["physical_write_strategy"] == "atomic_full_file_replace"
    assert write["changed_line_count"] == 1
    assert write["logical_change_ratio"] < 0.001
    assert write["full_file_logical_rewrite"] is False
    assert hashlib.sha256((root / "index.html").read_bytes()).hexdigest() == unrelated_before
    sessions.rollback_session("large-atomic", session.session_id, confirmed=True)
    assert (root / "app.js").read_bytes() == original
    assert hashlib.sha256((root / "index.html").read_bytes()).hexdigest() == unrelated_before
