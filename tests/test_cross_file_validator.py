"""
JARVIS OS — Test Suite: CrossFileValidator & Contract Integrity (Fase 10)
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from intelligence.cross_file_validator import CrossFileValidator, ContractIssueType
from intelligence.repository_graph import RepositoryGraph


class TestCrossFileValidator(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = tempfile.mkdtemp(prefix="jarvis_test_validator_")

    def tearDown(self) -> None:
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _write(self, rel_path: str, content: str) -> None:
        p = os.path.join(self.workspace, rel_path)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)

    def test_detects_missing_import_and_missing_export(self) -> None:
        self._write("module_a.py", "def existing_fn(): pass\n")
        self._write("module_b.py", "from module_a import missing_fn\n")

        graph = RepositoryGraph(self.workspace).scan()
        validator = CrossFileValidator(graph)
        report = validator.validate()

        self.assertFalse(report.is_valid)
        self.assertEqual(len(report.missing_imports), 1)
        self.assertEqual(report.missing_imports[0].issue_type, ContractIssueType.MISSING_EXPORT.value)

    def test_detects_api_contract_mismatch(self) -> None:
        self._write("backend/server.py", """
from fastapi import FastAPI
app = FastAPI()

@app.get('/api/items')
def get_items():
    return []
""")
        self._write("frontend/app.js", """
function addItem(item) {
    return fetch('/api/items', { method: 'POST' });
}
""")
        graph = RepositoryGraph(self.workspace).scan()
        validator = CrossFileValidator(graph)
        report = validator.validate()

        self.assertFalse(report.is_valid)
        self.assertEqual(len(report.contract_mismatches), 1)
        self.assertIn("CONTRACT_MISMATCH", report.contract_mismatches[0].message)


if __name__ == "__main__":
    unittest.main()
