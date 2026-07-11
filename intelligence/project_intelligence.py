from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path
from typing import Any, Iterator

try:
    import tree_sitter_javascript as tsjavascript
    import tree_sitter_python as tspython
    from tree_sitter import Language, Parser
except ImportError:
    Language = None
    Parser = None
    tspython = None
    tsjavascript = None


IGNORED_DIRECTORIES = {
    ".git",
    ".jarvis",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "htmlcov",
    "node_modules",
    "out",
    "venv",
}
GENERATED_SUFFIXES = (".min.js", ".min.css", ".map", ".pyc")
SUPPORTED_SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx")
# AST parsing has its own ceiling and is independent from the 500 KB UI limit
# and the much larger transactional integrity limit.
MAX_AST_FILE_BYTES = int(os.getenv("JARVIS_MAX_AST_FILE_BYTES", str(2 * 1024 * 1024)))


class ProjectIntelligenceEngine:
    def __init__(self, workspace_root: str):
        self.workspace_root = os.path.realpath(os.path.abspath(workspace_root))
        self.py_parser = self._build_parser(tspython)
        self.js_parser = self._build_parser(tsjavascript)
        self.symbol_graph: dict[str, dict[str, Any]] = {}
        self.errors: list[dict[str, str]] = []
        self.skipped_files: list[dict[str, Any]] = []

    @staticmethod
    def _build_parser(grammar):
        if Parser is None or Language is None or grammar is None:
            return None
        parser = Parser()
        parser.language = Language(grammar.language())
        return parser

    @staticmethod
    def _is_python_file(filepath: str) -> bool:
        return filepath.lower().endswith(".py")

    @staticmethod
    def _is_js_ts_file(filepath: str) -> bool:
        return filepath.lower().endswith((".js", ".jsx", ".ts", ".tsx"))

    @staticmethod
    def _get_ignored_dirs() -> set[str]:
        return set(IGNORED_DIRECTORIES)

    def iter_supported_files(self) -> Iterator[tuple[str, str]]:
        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRECTORIES)
            for filename in sorted(files):
                lower_name = filename.lower()
                if not lower_name.endswith(SUPPORTED_SUFFIXES):
                    continue
                if lower_name.endswith(GENERATED_SUFFIXES):
                    continue
                absolute_path = os.path.join(root, filename)
                relative_path = os.path.relpath(absolute_path, self.workspace_root).replace(os.sep, "/")
                try:
                    size_bytes = os.path.getsize(absolute_path)
                except OSError:
                    continue
                if size_bytes > MAX_AST_FILE_BYTES:
                    self.skipped_files.append({
                        "file": relative_path,
                        "reason": "ast_size_limit_exceeded",
                        "size_bytes": size_bytes,
                    })
                    continue
                yield absolute_path, relative_path

    def scan_workspace(self) -> dict[str, dict[str, Any]]:
        """Index only supported source files below this engine's project root."""
        self.symbol_graph = {}
        self.errors = []
        self.skipped_files = []
        for filepath, rel_path in self.iter_supported_files():
            try:
                if self._is_python_file(filepath):
                    parsed = self._parse_python(filepath)
                elif self._is_js_ts_file(filepath):
                    parsed = self._parse_javascript(filepath)
                else:
                    continue
                self.symbol_graph[rel_path] = parsed
                for diagnostic in parsed.get("diagnostics", []):
                    self.errors.append({"file": rel_path, "error": diagnostic})
            except Exception as exc:
                self.errors.append({"file": rel_path, "error": str(exc)})
        return self.symbol_graph

    def _parse_python(self, filepath: str) -> dict[str, Any]:
        src = Path(filepath).read_bytes()
        if self.py_parser is None:
            return self._parse_python_fallback(src, filepath)

        tree = self.py_parser.parse(src)
        symbols: dict[str, Any] = {
            "type": "python",
            "classes": [],
            "functions": [],
            "imports": [],
            "exports": [],
        }

        def text(node) -> str:
            return src[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")

        def traverse(node) -> None:
            if node.type in {"class_definition", "function_definition"}:
                name_node = node.child_by_field_name("name")
                if name_node is not None:
                    item = {
                        "name": text(name_node),
                        "line": node.start_point[0] + 1,
                        "end_line": node.end_point[0] + 1,
                        "code": text(node),
                    }
                    target = "classes" if node.type == "class_definition" else "functions"
                    symbols[target].append(item)
            elif node.type in {"import_statement", "import_from_statement"}:
                symbols["imports"].append(text(node))
            for child in node.children:
                traverse(child)

        traverse(tree.root_node)
        if tree.root_node.has_error:
            symbols["diagnostics"] = ["Tree-sitter encontrou sintaxe incompleta neste ficheiro."]
        return symbols

    @staticmethod
    def _parse_python_fallback(src: bytes, filepath: str) -> dict[str, Any]:
        source = src.decode("utf-8", errors="replace")
        tree = ast.parse(source, filename=filepath)
        symbols: dict[str, Any] = {
            "type": "python",
            "classes": [],
            "functions": [],
            "imports": [],
            "exports": [],
        }
        lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                end_line = getattr(node, "end_lineno", node.lineno)
                item = {
                    "name": node.name,
                    "line": node.lineno,
                    "end_line": end_line,
                    "code": "\n".join(lines[node.lineno - 1:end_line]),
                }
                symbols["classes" if isinstance(node, ast.ClassDef) else "functions"].append(item)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                symbols["imports"].append(ast.get_source_segment(source, node) or "")
        return symbols

    def _parse_javascript(self, filepath: str) -> dict[str, Any]:
        src = Path(filepath).read_bytes()
        if self.js_parser is None:
            return self._parse_javascript_fallback(src)

        tree = self.js_parser.parse(src)
        symbols: dict[str, Any] = {
            "type": "javascript/typescript",
            "classes": [],
            "functions": [],
            "imports": [],
            "exports": [],
        }

        def text(node) -> str:
            return src[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")

        def add_symbol(target: str, node, name_node) -> None:
            if name_node is None:
                return
            symbols[target].append({
                "name": text(name_node),
                "line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "code": text(node),
            })

        def traverse(node, parent=None) -> None:
            if node.type == "class_declaration":
                add_symbol("classes", node, node.child_by_field_name("name"))
            elif node.type in {"function_declaration", "generator_function_declaration"}:
                add_symbol("functions", node, node.child_by_field_name("name"))
            elif node.type in {"arrow_function", "function_expression"} and parent is not None and parent.type == "variable_declarator":
                add_symbol("functions", parent, parent.child_by_field_name("name"))
            elif node.type == "import_statement":
                symbols["imports"].append(text(node))
            elif node.type == "export_statement":
                symbols["exports"].append(text(node))
            for child in node.children:
                traverse(child, node)

        traverse(tree.root_node)
        if tree.root_node.has_error:
            symbols["diagnostics"] = ["Tree-sitter encontrou sintaxe incompleta neste ficheiro."]
        return symbols

    @staticmethod
    def _parse_javascript_fallback(src: bytes) -> dict[str, Any]:
        source = src.decode("utf-8", errors="replace")
        symbols: dict[str, Any] = {
            "type": "javascript/typescript",
            "classes": [],
            "functions": [],
            "imports": [],
            "exports": [],
        }
        patterns = (
            ("classes", re.compile(r"^\s*class\s+([A-Za-z_$][\w$]*)", re.MULTILINE)),
            ("functions", re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)", re.MULTILINE)),
            ("functions", re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>", re.MULTILINE)),
        )
        for target, pattern in patterns:
            for match in pattern.finditer(source):
                line = source.count("\n", 0, match.start()) + 1
                symbols[target].append({"name": match.group(1), "line": line, "end_line": line, "code": match.group(0)})
        symbols["imports"] = re.findall(r"^\s*import\s+.+$", source, re.MULTILINE)
        symbols["exports"] = re.findall(r"^\s*export\s+.+$", source, re.MULTILINE)
        return symbols

    def identifier_lines(self, filepath: str, symbol_name: str) -> set[int]:
        parser = self.py_parser if self._is_python_file(filepath) else self.js_parser
        if parser is None:
            return set()
        src = Path(filepath).read_bytes()
        tree = parser.parse(src)
        lines: set[int] = set()

        def traverse(node) -> None:
            if node.type == "identifier":
                name = src[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")
                if name == symbol_name:
                    lines.add(node.start_point[0] + 1)
            for child in node.children:
                traverse(child)

        traverse(tree.root_node)
        return lines

    def save_index(self, output_path: str) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.symbol_graph, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    engine = ProjectIntelligenceEngine(".")
    graph = engine.scan_workspace()
    engine.save_index("symbols_index.json")
    print(f"Indexacao concluida: {len(graph)} ficheiros, {len(engine.errors)} erros.")
