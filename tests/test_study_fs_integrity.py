"""
Regressão Stage 7 — Integridade em `read_json_safe()`: distinguir corrupção de erros I/O transitórios.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from services.study_fs import read_json_safe


def test_read_json_safe_quarantines_actual_corruption_only(tmp_path):
    corrupt_file = tmp_path / "documents.json"
    corrupt_file.write_text("{broken json", encoding="utf-8")

    data, was_corrupt = read_json_safe(
        corrupt_file, default={"docs": []}, expected_type=dict, backup_on_corrupt=True
    )

    assert was_corrupt is True
    assert data == {"docs": []}
    assert not corrupt_file.exists()
    baks = list(tmp_path.glob("documents.json.corrupt.*.bak"))
    assert len(baks) == 1


def test_read_json_safe_never_quarantines_on_permission_or_io_error(tmp_path):
    valid_file = tmp_path / "documents.json"
    original_payload = '{"doc_1": {"title": "Preserved"}}'
    valid_file.write_text(original_payload, encoding="utf-8")

    with patch.object(Path, "read_text", side_effect=PermissionError("Access denied")):
        with pytest.raises(PermissionError):
            read_json_safe(
                valid_file, default={}, expected_type=dict, backup_on_corrupt=True
            )

    assert valid_file.exists()
    assert valid_file.read_text(encoding="utf-8") == original_payload
    assert list(tmp_path.glob("documents.json.corrupt.*.bak")) == []


def test_read_json_safe_never_quarantines_on_oserror(tmp_path):
    valid_file = tmp_path / "srs_state.json"
    valid_file.write_text('{"cards": {}}', encoding="utf-8")

    with patch.object(Path, "read_text", side_effect=OSError("Transient disk I/O error")):
        with pytest.raises(OSError):
            read_json_safe(
                valid_file, default={}, expected_type=dict, backup_on_corrupt=True
            )

    assert valid_file.exists()
    assert list(tmp_path.glob("srs_state.json.corrupt.*.bak")) == []

