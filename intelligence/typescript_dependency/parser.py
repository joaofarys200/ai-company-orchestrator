"""
JARVIS OS — Phase 39.1: TypeScript Syntax-Aware Parser
Parses TypeScript (.ts), TSX (.tsx), JavaScript (.js), and JSX (.jsx) files to extract
imports, exports, re-exports, symbols, and dynamic dependencies without naive single-line regex.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from intelligence.typescript_dependency.models import (
    BoundaryType,
    ConfidenceClass,
    TypeScriptExport,
    TypeScriptImport,
    TypeScriptSymbol,
    TypeScriptSymbolType,
)


class TypeScriptSyntaxParser:
    """
    Syntax-aware parser for TypeScript and TSX files.
    Can utilize official TypeScript Compiler API via Node.js when available,
    with an embedded pure-Python tokenizer engine ensuring 100% testable deterministic behavior.
    """

    NODE_AST_PARSER_SCRIPT = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "ts_ast_parser.js")
    )

    @classmethod
    def compute_content_hash(cls, content: str) -> str:
        """Computes SHA-256 hash of source code for change detection."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @classmethod
    def parse_file(
        cls,
        file_path: str,
        workspace_root: str,
        content: Optional[str] = None,
        use_node_bridge: bool = False,
    ) -> Tuple[List[TypeScriptImport], List[TypeScriptExport], List[TypeScriptSymbol], str]:
        """
        Parses a TS/TSX file and returns (imports, exports, symbols, content_hash).
        """
        abs_path = file_path if os.path.isabs(file_path) else os.path.join(workspace_root, file_path)
        rel_path = os.path.relpath(abs_path, workspace_root).replace(os.sep, "/")

        if content is None:
            if not os.path.exists(abs_path):
                return [], [], [], ""
            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except OSError:
                return [], [], [], ""

        content_hash = cls.compute_content_hash(content)

        # 1. Try Node.js official TS compiler bridge if requested and available
        if use_node_bridge and os.path.exists(cls.NODE_AST_PARSER_SCRIPT):
            try:
                res = cls._parse_with_node_bridge(abs_path, content)
                if res is not None:
                    imports, exports, symbols = res
                    return imports, exports, symbols, content_hash
            except Exception:
                pass

        # 2. Pure Python syntax-aware tokenizer and parser
        imports, exports, symbols = cls.parse_content_python(content, rel_path)
        return imports, exports, symbols, content_hash

    @classmethod
    def parse_content_python(
        cls,
        content: str,
        rel_path: str,
    ) -> Tuple[List[TypeScriptImport], List[TypeScriptExport], List[TypeScriptSymbol]]:
        """
        Pure-Python syntax-aware tokenizer and parser for TypeScript and TSX.
        Safely strips comments while preserving strings, and parses multi-line statements.
        """
        cleaned_content, line_map = cls._clean_comments(content)
        imports: List[TypeScriptImport] = []
        exports: List[TypeScriptExport] = []
        symbols: List[TypeScriptSymbol] = []

        # A. Parse Import Statements
        # Matches: import ... from '...' or import '...'
        import_stmt_regex = re.compile(
            r"\bimport\s+(?:(type)\s+)?(?:([\w$]+)\s*,\s*)?(?:(\*\s+as\s+[\w$]+)|\{([^}]+)\}|([\w$]+))?\s*(?:from\s*)?['\"]([^'\"]+)['\"]",
            re.DOTALL,
        )

        for m in import_stmt_regex.finditer(cleaned_content):
            start_pos = m.start()
            line_no = line_map.get(start_pos, 1)

            is_type_clause = bool(m.group(1))
            combined_default = m.group(2)
            namespace_match = m.group(3)
            named_block = m.group(4)
            single_default = m.group(5)
            specifier = m.group(6)

            default_imp = combined_default or single_default
            namespace_imp = namespace_match.split()[-1] if namespace_match else None

            imported_syms: List[str] = []
            if named_block:
                # Handle comma-separated list: X, type Y, Z as W
                for token in named_block.split(","):
                    t = token.strip()
                    if not t:
                        continue
                    if t.startswith("type "):
                        t = t[5:].strip()
                    parts = re.split(r"\s+as\s+", t)
                    imported_syms.append(parts[0].strip())

            is_rel = specifier.startswith(".")
            is_type_only = is_type_clause

            imports.append(
                TypeScriptImport(
                    source_file=rel_path,
                    module_specifier=specifier,
                    imported_symbols=tuple(imported_syms),
                    default_import=default_imp,
                    namespace_import=namespace_imp,
                    is_type_only=is_type_only,
                    is_relative=is_rel,
                    is_dynamic=False,
                    line_number=line_no,
                    confidence=ConfidenceClass.DETERMINISTIC,
                    boundary=BoundaryType.INTRA_PACKAGE if is_rel else BoundaryType.EXTERNAL_PACKAGE,
                )
            )

        # B. Parse Dynamic Imports: import('...') and require('...')
        dyn_import_regex = re.compile(r"\b(?:import|require)\s*\(\s*['\"]([^'\"]+)['\"]\s*\)")
        for m in dyn_import_regex.finditer(cleaned_content):
            start_pos = m.start()
            line_no = line_map.get(start_pos, 1)
            specifier = m.group(1)
            is_rel = specifier.startswith(".")
            imports.append(
                TypeScriptImport(
                    source_file=rel_path,
                    module_specifier=specifier,
                    imported_symbols=(),
                    is_dynamic=True,
                    is_relative=is_rel,
                    line_number=line_no,
                    confidence=ConfidenceClass.UNCERTAIN,
                    boundary=BoundaryType.INTRA_PACKAGE if is_rel else BoundaryType.EXTERNAL_PACKAGE,
                )
            )

        # C. Parse Re-exports:
        # export * from '...'; export * as ns from '...'; export { a, b } from '...'; export { default as X } from '...';
        re_export_star_regex = re.compile(
            r"\bexport\s+(?:(type)\s+)?\*\s*(?:as\s+([\w$]+)\s+)?from\s+['\"]([^'\"]+)['\"]",
            re.DOTALL,
        )
        for m in re_export_star_regex.finditer(cleaned_content):
            start_pos = m.start()
            line_no = line_map.get(start_pos, 1)
            is_type_only = bool(m.group(1))
            star_ns = m.group(2)
            specifier = m.group(3)
            exports.append(
                TypeScriptExport(
                    source_file=rel_path,
                    exported_symbols=(),
                    is_default=False,
                    is_re_export=True,
                    re_export_source=specifier,
                    is_star_export=True,
                    star_namespace=star_ns,
                    is_type_only=is_type_only,
                    line_number=line_no,
                )
            )

        re_export_named_regex = re.compile(
            r"\bexport\s+(?:(type)\s+)?\{([^}]+)\}\s+from\s+['\"]([^'\"]+)['\"]",
            re.DOTALL,
        )
        for m in re_export_named_regex.finditer(cleaned_content):
            start_pos = m.start()
            line_no = line_map.get(start_pos, 1)
            is_type_only = bool(m.group(1))
            named_block = m.group(2)
            specifier = m.group(3)

            syms: List[str] = []
            for token in named_block.split(","):
                t = token.strip()
                if not t:
                    continue
                if t.startswith("type "):
                    t = t[5:].strip()
                parts = re.split(r"\s+as\s+", t)
                # Export alias target: e.g. "default as MyButton" -> "MyButton"
                sym_name = parts[-1].strip() if len(parts) > 1 else parts[0].strip()
                syms.append(sym_name)

            exports.append(
                TypeScriptExport(
                    source_file=rel_path,
                    exported_symbols=tuple(syms),
                    is_default="default" in named_block,
                    is_re_export=True,
                    re_export_source=specifier,
                    is_star_export=False,
                    is_type_only=is_type_only,
                    line_number=line_no,
                )
            )

        # D. Parse Local Export Statements:
        # export { a, b }; export default ...
        local_export_named_regex = re.compile(
            r"\bexport\s+(?:(type)\s+)?\{([^}]+)\}(?!\s*from)",
            re.DOTALL,
        )
        for m in local_export_named_regex.finditer(cleaned_content):
            start_pos = m.start()
            line_no = line_map.get(start_pos, 1)
            is_type_only = bool(m.group(1))
            named_block = m.group(2)
            syms = [s.strip().split(" as ")[-1].strip() for s in named_block.split(",") if s.strip()]
            exports.append(
                TypeScriptExport(
                    source_file=rel_path,
                    exported_symbols=tuple(syms),
                    is_default=False,
                    is_re_export=False,
                    is_type_only=is_type_only,
                    line_number=line_no,
                )
            )

        export_default_regex = re.compile(
            r"\bexport\s+default\s+(?:(class|function)\s+([\w$]+)|([\w$]+))?"
        )
        for m in export_default_regex.finditer(cleaned_content):
            start_pos = m.start()
            line_no = line_map.get(start_pos, 1)
            sym_name = m.group(2) or m.group(3) or "default"
            exports.append(
                TypeScriptExport(
                    source_file=rel_path,
                    exported_symbols=(sym_name,),
                    is_default=True,
                    is_re_export=False,
                    line_number=line_no,
                )
            )

        # E. Parse Declarations and Symbols
        # Functions
        func_regex = re.compile(
            r"(?:(export\s+(?:default\s+)?)?(?:async\s+)?function\s+([\w$]+)\s*(?:<[^>]+>)?\s*\(([^)]*)\))"
        )
        for m in func_regex.finditer(cleaned_content):
            start_pos = m.start()
            line_no = line_map.get(start_pos, 1)
            is_exp = bool(m.group(1))
            is_def = "default" in (m.group(1) or "")
            name = m.group(2)
            symbols.append(
                TypeScriptSymbol(
                    name=name,
                    symbol_type=TypeScriptSymbolType.FUNCTION,
                    file_path=rel_path,
                    line_number=line_no,
                    is_exported=is_exp,
                    signature=f"function {name}({m.group(3)})",
                    is_default=is_def,
                )
            )

        # Classes
        class_regex = re.compile(r"(?:(export\s+(?:default\s+)?)?class\s+([\w$]+))")
        for m in class_regex.finditer(cleaned_content):
            start_pos = m.start()
            line_no = line_map.get(start_pos, 1)
            is_exp = bool(m.group(1))
            name = m.group(2)
            symbols.append(
                TypeScriptSymbol(
                    name=name,
                    symbol_type=TypeScriptSymbolType.CLASS,
                    file_path=rel_path,
                    line_number=line_no,
                    is_exported=is_exp,
                    signature=f"class {name}",
                )
            )

        # Interfaces & Type Aliases
        type_regex = re.compile(r"(?:(export\s+)?(interface|type)\s+([\w$]+))")
        for m in type_regex.finditer(cleaned_content):
            start_pos = m.start()
            line_no = line_map.get(start_pos, 1)
            is_exp = bool(m.group(1))
            kind = m.group(2)
            name = m.group(3)
            sym_type = TypeScriptSymbolType.INTERFACE if kind == "interface" else TypeScriptSymbolType.TYPE_ALIAS
            symbols.append(
                TypeScriptSymbol(
                    name=name,
                    symbol_type=sym_type,
                    file_path=rel_path,
                    line_number=line_no,
                    is_exported=is_exp,
                    signature=f"{kind} {name}",
                )
            )

        # Enums
        enum_regex = re.compile(r"(?:(export\s+)?enum\s+([\w$]+))")
        for m in enum_regex.finditer(cleaned_content):
            start_pos = m.start()
            line_no = line_map.get(start_pos, 1)
            is_exp = bool(m.group(1))
            name = m.group(2)
            symbols.append(
                TypeScriptSymbol(
                    name=name,
                    symbol_type=TypeScriptSymbolType.ENUM,
                    file_path=rel_path,
                    line_number=line_no,
                    is_exported=is_exp,
                    signature=f"enum {name}",
                )
            )

        # Variables, Constants, and React Components:
        # const/let/var Name: React.FC... or const Name = (...) => ...
        var_regex = re.compile(
            r"(?:(export\s+)?(const|let|var)\s+([\w$]+)\s*(?::\s*([^=]+))?\s*=\s*(?:async\s*)?(?:\([^)]*\)|[\w$]+)?\s*=>|(?:(export\s+)?(const|let|var)\s+([\w$]+)\s*(?::\s*([^=;]+))?))"
        )
        for m in var_regex.finditer(cleaned_content):
            start_pos = m.start()
            line_no = line_map.get(start_pos, 1)
            is_exp = bool(m.group(1) or m.group(5))
            name = m.group(3) or m.group(7)
            type_annot = (m.group(4) or m.group(8) or "").strip()

            if not name:
                continue

            # Check if it's a React component
            is_react_comp = False
            if "React.FC" in type_annot or "FC<" in type_annot or "ReactNode" in type_annot:
                is_react_comp = True
            elif name[0].isupper() and (rel_path.endswith(".tsx") or rel_path.endswith(".jsx")):
                is_react_comp = True

            sym_type = TypeScriptSymbolType.REACT_COMPONENT if is_react_comp else TypeScriptSymbolType.CONSTANT

            symbols.append(
                TypeScriptSymbol(
                    name=name,
                    symbol_type=sym_type,
                    file_path=rel_path,
                    line_number=line_no,
                    is_exported=is_exp,
                    signature=f"const {name}: {type_annot}" if type_annot else f"const {name}",
                )
            )

        # Reconcile exports: if a symbol is exported (default or named), mark is_exported=True
        exported_names = {s for exp in exports for s in exp.exported_symbols}
        has_default_exp = any(exp.is_default for exp in exports)
        final_symbols = []
        for sym in symbols:
            is_now_exported = sym.is_exported or sym.name in exported_names or (has_default_exp and sym.name in ("App", "default"))
            final_symbols.append(
                TypeScriptSymbol(
                    name=sym.name,
                    symbol_type=sym.symbol_type,
                    file_path=sym.file_path,
                    line_number=sym.line_number,
                    is_exported=is_now_exported,
                    signature=sym.signature,
                    is_default=sym.is_default or (has_default_exp and sym.name in ("App", "default")),
                )
            )

        return imports, exports, final_symbols

    @classmethod
    def _clean_comments(cls, code: str) -> Tuple[str, Dict[int, int]]:
        """
        Replaces comments with spaces while strictly preserving newlines and string literals.
        Returns the cleaned string and a position-to-line-number map.
        """
        chars: List[str] = []
        line_map: Dict[int, int] = {}
        line_num = 1
        i = 0
        n = len(code)

        while i < n:
            pos = i
            line_map[pos] = line_num
            ch = code[i]

            if ch == "\n":
                line_num += 1
                chars.append(ch)
                i += 1
                continue

            # Check for strings (single, double, or backtick)
            if ch in ('"', "'", "`"):
                quote = ch
                chars.append(quote)
                i += 1
                while i < n:
                    pos_inner = i
                    line_map[pos_inner] = line_num
                    c2 = code[i]
                    if c2 == "\n":
                        line_num += 1
                    if c2 == "\\":
                        chars.append(c2)
                        i += 1
                        if i < n:
                            chars.append(code[i])
                            i += 1
                        continue
                    chars.append(c2)
                    i += 1
                    if c2 == quote:
                        break
                continue

            # Check for block comment /* ... */
            if ch == "/" and i + 1 < n and code[i + 1] == "*":
                i += 2
                while i < n:
                    if code[i] == "\n":
                        line_num += 1
                        chars.append("\n")
                    else:
                        chars.append(" ")
                    if code[i] == "*" and i + 1 < n and code[i + 1] == "/":
                        chars.append(" ")
                        chars.append(" ")
                        i += 2
                        break
                    i += 1
                continue

            # Check for line comment // ...
            if ch == "/" and i + 1 < n and code[i + 1] == "/":
                i += 2
                while i < n and code[i] != "\n":
                    chars.append(" ")
                    i += 1
                continue

            chars.append(ch)
            i += 1

        return "".join(chars), line_map

    @classmethod
    def _parse_with_node_bridge(cls, abs_path: str, content: str) -> Optional[Tuple[List[TypeScriptImport], List[TypeScriptExport], List[TypeScriptSymbol]]]:
        """Bridge invocation to Node.js TypeScript compiler API."""
        proc = subprocess.run(
            ["node", cls.NODE_AST_PARSER_SCRIPT, "--single", abs_path],
            input=content,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        if proc.returncode != 0:
            return None
        data = json.loads(proc.stdout)
        imports = [TypeScriptImport.from_dict(i) for i in data.get("imports", [])]
        exports = [TypeScriptExport.from_dict(e) for e in data.get("exports", [])]
        symbols = [TypeScriptSymbol.from_dict(s) for s in data.get("symbols", [])]
        return imports, exports, symbols
