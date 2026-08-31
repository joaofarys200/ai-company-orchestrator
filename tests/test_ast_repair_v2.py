"""
JARVIS OS — Test Suite: ASTRepairEngineV2 (Fase 10)
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from intelligence.ast_repair_v2 import ASTRepairEngineV2, RepairStrategy
from intelligence.repository_graph import RepositoryGraph


class TestASTRepairEngineV2(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = tempfile.mkdtemp(prefix="jarvis_test_ast_repair_")

    def tearDown(self) -> None:
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _write(self, rel_path: str, content: str) -> None:
        p = os.path.join(self.workspace, rel_path)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)

    def test_repair_python_syntax_header_and_brackets(self) -> None:
        engine = ASTRepairEngineV2()
        bad_code = "def process(items, config\n    result = [x for x in items\n    return result\n"
        res = engine.repair_syntax_python(bad_code, "test.py")
        self.assertTrue(res.success)
        self.assertIn("def process(items, config):", res.repaired_content)

    def test_repair_javascript_syntax_braces(self) -> None:
        engine = ASTRepairEngineV2()
        bad_js = "function test() {\n    const obj = { a: 1, b: 2 };\n"
        res = engine.repair_syntax_javascript(bad_js, "test.js")
        self.assertTrue(res.success)
        self.assertTrue(res.repaired_content.count("{") == res.repaired_content.count("}"))

    def test_repair_missing_import_via_symbol_graph(self) -> None:
        self._write("utils/helpers.py", "def format_currency(val: float) -> str: return f'${val:.2f}'\n")
        graph = RepositoryGraph(self.workspace).scan()

        engine = ASTRepairEngineV2(graph)
        consumer_code = "def render_price(p: float): return format_currency(p)\n"
        res = engine.repair_missing_import(consumer_code, "format_currency", "views/price.py")

        self.assertTrue(res.success)
        self.assertIn("from utils.helpers import format_currency", res.repaired_content)


if __name__ == "__main__":
    unittest.main()
