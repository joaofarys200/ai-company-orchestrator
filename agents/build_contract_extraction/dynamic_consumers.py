"""
JARVIS OS — Phase 49: Dynamic Consumer Pattern Scanner
Detects dynamic reflection, subscripting, registries, and dispatch tables across Python and TypeScript ASTs.
"""

from __future__ import annotations

import ast
import re
import uuid
from typing import Any, List, Optional, Set, Tuple

from agents.build_contract_extraction.models import (
    DynamicConsumerPattern,
    PatternType,
)


class DynamicConsumerScanner:
    """
    Scans source code files to identify reflection, dynamic key lookups, dispatch tables, and registries.
    Classifies whether the key expression is bounded by a known literal set or open/unbounded.
    """

    # -------------------------------------------------------------
    # Python AST Scanning
    # -------------------------------------------------------------
    @classmethod
    def scan_python_code(
        cls,
        code_content: str,
        source_file: str = "app.py",
        known_literal_unions: Optional[dict[str, list[str]]] = None,
    ) -> list[DynamicConsumerPattern]:
        """Scans Python code via AST for getattr(), dynamic subscription, and registry access."""
        patterns: list[DynamicConsumerPattern] = []
        known_unions = known_literal_unions or {}

        try:
            tree = ast.parse(code_content, filename=source_file)
        except SyntaxError:
            # Fallback to regex scanner if syntax is partial
            return cls._scan_python_regex(code_content, source_file, known_unions)

        lines = code_content.splitlines()

        for node in ast.walk(tree):
            # 1. Detect getattr(obj, key_expr)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr":
                if len(node.args) >= 2:
                    target_obj = cls._node_to_str(node.args[0])
                    key_node = node.args[1]
                    key_expr = cls._node_to_str(key_node)
                    line_no = node.lineno
                    snippet = lines[line_no - 1].strip() if line_no <= len(lines) else ""

                    is_bounded, literals = cls._check_bounded(key_node, key_expr, known_unions)
                    patterns.append(DynamicConsumerPattern(
                        pattern_id=f"pat_py_getattr_{uuid.uuid4().hex[:8]}",
                        pattern_type=PatternType.DYNAMIC_GETATTR,
                        source_file=source_file,
                        line_number=line_no,
                        target_object_expr=target_obj,
                        key_expression=key_expr,
                        is_literal_or_bounded=is_bounded,
                        bounded_literals=literals,
                        context_snippet=snippet,
                        language="Python",
                    ))

            # 2. Detect dict/object dynamic subscription: obj[key] where key is not a literal
            elif isinstance(node, ast.Subscript):
                target_obj = cls._node_to_str(node.value)
                # Ignore Python typing annotations
                if target_obj.lower() in (
                    "dict", "list", "tuple", "set", "frozenset", "type", "optional",
                    "union", "callable", "mapping", "sequence", "iterable", "any",
                    "literal", "classvar", "final", "annotated", "match"
                ):
                    continue

                slice_node = node.slice
                # In Python 3.9+, slice is directly the Index value
                if not isinstance(slice_node, ast.Constant):
                    key_expr = cls._node_to_str(slice_node)
                    line_no = node.lineno
                    snippet = lines[line_no - 1].strip() if line_no <= len(lines) else ""

                    # Check pattern type (registry vs dispatch vs dynamic index)
                    p_type = PatternType.DYNAMIC_INDEX
                    if "registry" in target_obj.lower():
                        p_type = PatternType.REGISTRY_LOOKUP
                    elif "handler" in target_obj.lower() or "dispatcher" in target_obj.lower():
                        p_type = PatternType.DISPATCH_TABLE

                    is_bounded, literals = cls._check_bounded(slice_node, key_expr, known_unions)
                    patterns.append(DynamicConsumerPattern(
                        pattern_id=f"pat_py_index_{uuid.uuid4().hex[:8]}",
                        pattern_type=p_type,
                        source_file=source_file,
                        line_number=line_no,
                        target_object_expr=target_obj,
                        key_expression=key_expr,
                        is_literal_or_bounded=is_bounded,
                        bounded_literals=literals,
                        context_snippet=snippet,
                        language="Python",
                    ))

            # 3. Detect dict.get(key) on handlers, registries, dispatchers
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and len(node.args) >= 1
            ):
                target_obj = cls._node_to_str(node.func.value)
                if any(kw in target_obj.lower() for kw in ("handler", "registry", "dispatcher", "table", "consumer", "route")):
                    key_node = node.args[0]
                    if not isinstance(key_node, ast.Constant):
                        key_expr = cls._node_to_str(key_node)
                        line_no = node.lineno
                        snippet = lines[line_no - 1].strip() if line_no <= len(lines) else ""
                        p_type = PatternType.REGISTRY_LOOKUP if "registry" in target_obj.lower() else PatternType.DISPATCH_TABLE
                        is_bounded, literals = cls._check_bounded(key_node, key_expr, known_unions)
                        patterns.append(DynamicConsumerPattern(
                            pattern_id=f"pat_py_get_{uuid.uuid4().hex[:8]}",
                            pattern_type=p_type,
                            source_file=source_file,
                            line_number=line_no,
                            target_object_expr=target_obj,
                            key_expression=key_expr,
                            is_literal_or_bounded=is_bounded,
                            bounded_literals=literals,
                            context_snippet=snippet,
                            language="Python",
                        ))

        return patterns

    @classmethod
    def _scan_python_regex(
        cls,
        code_content: str,
        source_file: str,
        known_unions: dict[str, list[str]],
    ) -> list[DynamicConsumerPattern]:
        patterns = []
        for idx, line in enumerate(code_content.splitlines(), start=1):
            m_getattr = re.search(r"getattr\s*\(\s*(\w+)\s*,\s*([^)]+)\)", line)
            if m_getattr:
                target = m_getattr.group(1)
                key_expr = m_getattr.group(2).strip()
                is_bounded = key_expr in known_unions
                literals = known_unions.get(key_expr, [])
                patterns.append(DynamicConsumerPattern(
                    pattern_id=f"pat_py_getattr_{uuid.uuid4().hex[:8]}",
                    pattern_type=PatternType.DYNAMIC_GETATTR,
                    source_file=source_file,
                    line_number=idx,
                    target_object_expr=target,
                    key_expression=key_expr,
                    is_literal_or_bounded=is_bounded,
                    bounded_literals=literals,
                    context_snippet=line.strip(),
                    language="Python",
                ))
        return patterns

    # -------------------------------------------------------------
    # TypeScript / JavaScript Scanning
    # -------------------------------------------------------------
    @classmethod
    def scan_typescript_code(
        cls,
        code_content: str,
        source_file: str = "consumer.ts",
        known_literal_unions: Optional[dict[str, list[str]]] = None,
    ) -> list[DynamicConsumerPattern]:
        """Scans TypeScript / JavaScript code for obj[key], registry[event], handlers[type], service[method]()."""
        patterns: list[DynamicConsumerPattern] = []
        known_unions = known_literal_unions or {}
        lines = code_content.splitlines()

        # Regular expressions for dynamic access in TS/JS
        # 1. registry[eventName] or handlers[type]
        subscript_regex = re.compile(r"(\b\w+)\s*\[\s*([a-zA-Z_$][\w.$]*)\s*\]")
        # 2. service[method](payload)
        method_dispatch_regex = re.compile(r"(\b\w+)\s*\[\s*([a-zA-Z_$][\w.$]*)\s*\]\s*\(")

        for line_idx, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if (
                not line
                or line.startswith("//")
                or line.startswith("/*")
                or line.startswith("import ")
                or line.startswith("export type ")
                or line.startswith("export interface ")
                or line.startswith("interface ")
                or line.startswith("type ")
            ):
                continue

            # Check method dispatch first
            m_disp = method_dispatch_regex.search(line)
            if m_disp:
                target_obj = m_disp.group(1)
                if target_obj in ("Record", "Array", "Map", "Set", "Promise", "Pick", "Omit"):
                    continue
                key_expr = m_disp.group(2)
                # Ignore string literals: obj["literal"]
                if not (key_expr.startswith("'") or key_expr.startswith('"')):
                    is_bounded = key_expr in known_unions
                    literals = known_unions.get(key_expr, [])
                    patterns.append(DynamicConsumerPattern(
                        pattern_id=f"pat_ts_method_{uuid.uuid4().hex[:8]}",
                        pattern_type=PatternType.METHOD_DISPATCH,
                        source_file=source_file,
                        line_number=line_idx,
                        target_object_expr=target_obj,
                        key_expression=key_expr,
                        is_literal_or_bounded=is_bounded,
                        bounded_literals=literals,
                        context_snippet=line,
                        language="TypeScript",
                    ))
                    continue

            # Check generic dynamic index / registry
            m_sub = subscript_regex.search(line)
            if m_sub:
                target_obj = m_sub.group(1)
                if target_obj in ("Record", "Array", "Map", "Set", "Promise", "Pick", "Omit", "Partial", "Required"):
                    continue
                key_expr = m_sub.group(2)
                if not (key_expr.startswith("'") or key_expr.startswith('"')):
                    p_type = PatternType.DYNAMIC_INDEX
                    if "registry" in target_obj.lower():
                        p_type = PatternType.REGISTRY_LOOKUP
                    elif "handler" in target_obj.lower() or "dispatch" in target_obj.lower():
                        p_type = PatternType.DISPATCH_TABLE

                    is_bounded = key_expr in known_unions
                    literals = known_unions.get(key_expr, [])
                    patterns.append(DynamicConsumerPattern(
                        pattern_id=f"pat_ts_sub_{uuid.uuid4().hex[:8]}",
                        pattern_type=p_type,
                        source_file=source_file,
                        line_number=line_idx,
                        target_object_expr=target_obj,
                        key_expression=key_expr,
                        is_literal_or_bounded=is_bounded,
                        bounded_literals=literals,
                        context_snippet=line,
                        language="TypeScript",
                    ))

        return patterns

    @classmethod
    def _node_to_str(cls, node: ast.AST) -> str:
        if hasattr(ast, "unparse"):
            return ast.unparse(node)
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return str(node.value)
        return "expr"

    @classmethod
    def _check_bounded(
        cls,
        node: ast.AST,
        key_expr: str,
        known_unions: dict[str, list[str]],
    ) -> Tuple[bool, list[str]]:
        """Checks if a key expression is bounded by a known set of literals."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return True, [node.value]
        if key_expr in known_unions:
            return True, known_unions[key_expr]
        return False, []
