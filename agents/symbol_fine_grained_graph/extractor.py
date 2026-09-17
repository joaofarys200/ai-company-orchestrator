from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

from .javascript import JavaScriptSymbolExtractor
from .models import SymbolEdge, SymbolNode
from .python import PythonSymbolExtractor
from .symbols import SymbolManager
from .typescript import TypeScriptSymbolExtractor


class MultiLanguageSymbolExtractor:
    """Dispatches file extraction to Python, TypeScript, or JavaScript extractors."""

    def __init__(self, symbol_mgr: Optional[SymbolManager] = None) -> None:
        self.mgr = symbol_mgr or SymbolManager()
        self.py_extractor = PythonSymbolExtractor(self.mgr)
        self.ts_extractor = TypeScriptSymbolExtractor(self.mgr)
        self.js_extractor = JavaScriptSymbolExtractor(self.mgr)

    def extract_file(
        self, file_path: str, content: Optional[str] = None, module_id: str = ""
    ) -> Tuple[List[SymbolNode], List[SymbolEdge]]:
        """Extract symbols and edges from a single file by determining its language."""
        normalized_path = file_path.replace("\\", "/")
        ext = os.path.splitext(normalized_path)[1].lower()

        if content is None:
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception as e:
                # Return empty extraction on unreadable file
                return [], []

        if ext == ".py":
            res = self.py_extractor.extract(normalized_path, content, module_id=module_id)
        elif ext in (".ts", ".tsx"):
            res = self.ts_extractor.extract(normalized_path, content, module_id=module_id)
        elif ext in (".js", ".jsx", ".mjs", ".cjs"):
            res = self.js_extractor.extract(normalized_path, content, module_id=module_id)
        else:
            return [], []

        return res[0], res[1]

    def extract_files(
        self, file_dict: Dict[str, str]
    ) -> Tuple[Dict[str, List[SymbolNode]], Dict[str, List[SymbolEdge]]]:
        """Extract symbols and edges from a batch of {file_path: content} entries."""
        symbols_by_file: Dict[str, List[SymbolNode]] = {}
        edges_by_file: Dict[str, List[SymbolEdge]] = {}

        for file_path, content in file_dict.items():
            syms, edges = self.extract_file(file_path, content)
            norm = file_path.replace("\\", "/")
            symbols_by_file[norm] = syms
            edges_by_file[norm] = edges

        return symbols_by_file, edges_by_file
