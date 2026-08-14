from __future__ import annotations

import unittest
from backend.model_harness.context_builder import (
    ContextBuilder,
    ContextBuildRequest,
    ContextCandidate,
)


class TestLargeFileContextASTFallback(unittest.TestCase):
    def setUp(self):
        self.builder = ContextBuilder()

    def test_small_file_included_in_full(self):
        code = "def small_func(): return 42\n"
        candidate = ContextCandidate(
            source="src/small.py",
            kind="code",
            content=code,
            relevance_score=0.9,
        )
        req = ContextBuildRequest(
            task_summary="Analyze small file",
            candidates=(candidate,),
            max_chars=1000,
        )
        ctx = self.builder.build(req)
        self.assertEqual(len(ctx.items), 1)
        self.assertEqual(ctx.items[0].kind, "code")
        self.assertEqual(ctx.items[0].content, code)

    def test_large_python_file_falls_back_to_ast_outline(self):
        # Generate 5,000 chars of python code with classes and functions
        large_code_lines = [
            "import os",
            "import sys",
            "from typing import Any, Optional",
            "",
            "class HeavyProcessor:",
            '    """Main heavy batch processing class."""',
            "    def __init__(self, name: str):",
            "        self.name = name",
            "",
            "    def process_item(self, item_id: int) -> dict[str, Any]:",
            '        """Process single item with retry."""',
            "        return {'status': 'OK', 'id': item_id}",
            "",
            "def standalone_helper(x: int, y: int) -> int:",
            '    """Helper function."""',
            "    return x + y",
            "",
        ]
        # Append padding comments to inflate size beyond budget
        for i in range(100):
            large_code_lines.append(f"# Padding line {i} with lots of filler text to exceed character budget limits...")
        
        full_content = "\n".join(large_code_lines)
        self.assertTrue(len(full_content) > 3000)

        candidate = ContextCandidate(
            source="src/heavy_processor.py",
            kind="code",
            content=full_content,
            relevance_score=0.95,
        )

        # Restrict max_chars to 1,500 so full content cannot fit, but AST outline (approx 400 chars) fits!
        req = ContextBuildRequest(
            task_summary="Understand HeavyProcessor",
            candidates=(candidate,),
            max_chars=1500,
        )
        ctx = self.builder.build(req)

        self.assertEqual(len(ctx.items), 1)
        item = ctx.items[0]
        self.assertEqual(item.kind, "structural_outline")
        self.assertIn("HeavyProcessor", item.content)
        self.assertIn("process_item", item.content)
        self.assertIn("standalone_helper", item.content)
        self.assertIn("import os", item.content)
        self.assertTrue(len(item.content) < 1500)
        self.assertIn("ast_outline_budget_fallback", item.inclusion_reason)

    def test_large_javascript_file_falls_back_to_symbols(self):
        js_code_lines = [
            "import React from 'react';",
            "import { useState, useEffect } from 'react';",
            "export const API_URL = 'https://api.example.com';",
            "export function HeaderComponent(props) { return null; }",
            "export class DataManager { fetch() {} }",
        ]
        for i in range(80):
            js_code_lines.append(f"// Very long padding comment line {i} to blow past the character budget limit...")

        full_content = "\n".join(js_code_lines)
        candidate = ContextCandidate(
            source="frontend/Header.jsx",
            kind="code",
            content=full_content,
            relevance_score=0.8,
        )

        req = ContextBuildRequest(
            task_summary="Inspect Header JSX",
            candidates=(candidate,),
            max_chars=800,
        )
        ctx = self.builder.build(req)

        self.assertEqual(len(ctx.items), 1)
        item = ctx.items[0]
        self.assertEqual(item.kind, "structural_outline")
        self.assertIn("HeaderComponent", item.content)
        self.assertIn("DataManager", item.content)


if __name__ == "__main__":
    unittest.main()
