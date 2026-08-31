"""
JARVIS OS — Test Suite: RepositoryGraph & Symbol Graph Engine (Fase 10)
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from intelligence.repository_graph import (
    BlastRadius,
    RepositoryGraph,
    SymbolDefinition,
    SymbolType,
)


class TestRepositoryGraph(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = tempfile.mkdtemp(prefix="jarvis_test_repo_graph_")

    def tearDown(self) -> None:
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _write(self, rel_path: str, content: str) -> None:
        p = os.path.join(self.workspace, rel_path)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)

    def test_python_symbol_and_endpoint_extraction(self) -> None:
        self._write("api/routes.py", """
from fastapi import FastAPI

app = FastAPI()

@app.get('/api/users')
def list_users():
    return []

@app.post('/api/users')
async def create_user(user: dict):
    return user
""")
        graph = RepositoryGraph(self.workspace).scan()
        self.assertIn("list_users", graph.symbols)
        self.assertIn("create_user", graph.symbols)
        self.assertEqual(len(graph.endpoints), 2)
        methods = {ep.http_method for ep in graph.endpoints}
        self.assertEqual(methods, {"GET", "POST"})

    def test_javascript_symbol_and_api_call_extraction(self) -> None:
        self._write("frontend/app.js", """
export function loadData() {
    return fetch('/api/users', { method: 'GET' });
}

export const sendData = async (payload) => {
    return axios.post('/api/users', payload);
};
""")
        graph = RepositoryGraph(self.workspace).scan()
        self.assertIn("loadData", graph.symbols)
        self.assertIn("sendData", graph.symbols)
        self.assertEqual(len(graph.api_calls), 2)

    def test_blast_radius_calculation_direct_and_transitive(self) -> None:
        self._write("core/base.py", "def base_helper(): return 1\n")
        self._write("services/user_service.py", "from core.base import base_helper\ndef get_user(): return base_helper()\n")
        self._write("api/user_api.py", "from services.user_service import get_user\ndef user_endpoint(): return get_user()\n")
        self._write("tests/test_user_api.py", "from api.user_api import user_endpoint\ndef test_user(): assert user_endpoint() == 1\n")

        graph = RepositoryGraph(self.workspace).scan()
        blast = graph.compute_blast_radius(["core/base.py"])

        self.assertIn("services/user_service.py", blast.directly_affected_files)
        self.assertIn("api/user_api.py", blast.transitively_affected_files)
        self.assertIn("tests/test_user_api.py", blast.affected_tests)
        self.assertGreater(blast.risk_score, 0.0)


if __name__ == "__main__":
    unittest.main()
