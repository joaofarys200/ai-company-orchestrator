from __future__ import annotations

import ast
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import SymbolEdge, SymbolEdgeType, SymbolKind, SymbolNode
from .symbols import SymbolManager


class PythonSymbolExtractor:
    """Extracts fine-grained symbol definitions and intra-file references from Python AST."""

    def __init__(self, symbol_mgr: Optional[SymbolManager] = None) -> None:
        self.mgr = symbol_mgr or SymbolManager()

    @classmethod
    def extract(cls, file_id: str, content: str, module_id: str = "") -> Tuple[List[SymbolNode], List[SymbolEdge], Dict[str, Any]]:
        file_id = file_id.replace("\\", "/")
        try:
            tree = ast.parse(content, filename=file_id)
        except Exception:
            return [], [], {"error": "syntax_error"}

        symbols: List[SymbolNode] = []
        edges: List[SymbolEdge] = []
        import_map: Dict[str, Dict[str, Any]] = {}
        exports: Set[str] = set()

        # Check __all__ for explicit exports
        for stmt in tree.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(stmt.value, (ast.List, ast.Tuple)):
                            for elt in stmt.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    exports.add(elt.value)
                        # Add __all__ as a symbol
                        all_sym = SymbolManager.build_symbol(
                            file_id=file_id,
                            name="__all__",
                            kind=SymbolKind.CONSTANT,
                            exported=True,
                            line=stmt.lineno,
                            column=stmt.col_offset,
                        )
                        symbols.append(all_sym)

        # Module-level imports
        is_barrel = file_id.endswith("__init__.py")
        for stmt in tree.body:
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    local_name = alias.asname or alias.name
                    import_map[local_name] = {
                        "source_module": alias.name,
                        "imported_name": alias.name,
                        "is_type_only": False,
                    }
                    imp_sym = SymbolManager.build_symbol(
                        file_id=file_id,
                        name=local_name,
                        kind=SymbolKind.IMPORT,
                        imported=True,
                        line=stmt.lineno,
                        column=stmt.col_offset,
                        provenance={"source_module": alias.name, "alias": bool(alias.asname), "original_name": alias.name},
                    )
                    symbols.append(imp_sym)
                    edges.append(
                        SymbolEdge(
                            source_symbol=imp_sym.symbol_id,
                            target_symbol=f"{alias.name}::MODULE",
                            edge_type=SymbolEdgeType.IMPORTS,
                            provenance={"import_source": alias.name},
                            source_location={"line": stmt.lineno},
                        )
                    )

            elif isinstance(stmt, ast.ImportFrom):
                mod = stmt.module or ""
                for alias in stmt.names:
                    local_name = alias.asname or alias.name
                    import_map[local_name] = {
                        "source_module": mod,
                        "imported_name": alias.name,
                        "is_type_only": False,
                    }
                    imp_sym = SymbolManager.build_symbol(
                        file_id=file_id,
                        name=local_name,
                        kind=SymbolKind.IMPORT,
                        imported=True,
                        line=stmt.lineno,
                        column=stmt.col_offset,
                        provenance={"source_module": mod, "alias": bool(alias.asname), "original_name": alias.name},
                    )
                    symbols.append(imp_sym)

                    # Import edge
                    edges.append(
                        SymbolEdge(
                            source_symbol=imp_sym.symbol_id,
                            target_symbol=f"{mod}::{alias.name}",
                            edge_type=SymbolEdgeType.IMPORTS,
                            provenance={"source_module": mod, "target_name": alias.name},
                            source_location={"line": stmt.lineno},
                        )
                    )

                    # Re-export check
                    if is_barrel or local_name in exports:
                        exp_sym = SymbolManager.build_symbol(
                            file_id=file_id,
                            name=local_name,
                            kind=SymbolKind.EXPORT,
                            exported=True,
                            imported=True,
                            line=stmt.lineno,
                            provenance={"source_module": mod, "target_name": alias.name},
                        )
                        symbols.append(exp_sym)
                        edges.append(
                            SymbolEdge(
                                source_symbol=exp_sym.symbol_id,
                                target_symbol=f"{mod}::{alias.name}",
                                edge_type=SymbolEdgeType.REEXPORTS,
                                provenance={"source_module": mod, "target_name": alias.name},
                                source_location={"line": stmt.lineno},
                            )
                        )

        # Visitor for declarations and references
        class Visitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.current_class: Optional[str] = None
                self.current_function: Optional[str] = None

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                qname = f"{self.current_class}.{node.name}" if self.current_class else node.name
                is_exported = bool(not node.name.startswith("_") or node.name in exports)
                cls_sym = SymbolManager.build_symbol(
                    file_id=file_id,
                    name=node.name,
                    qualified_name=qname,
                    kind=SymbolKind.CLASS,
                    exported=is_exported,
                    line=node.lineno,
                    column=node.col_offset,
                )
                symbols.append(cls_sym)

                # Inheritance
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        base_name = base.id
                        edges.append(
                            SymbolEdge(
                                source_symbol=cls_sym.symbol_id,
                                target_symbol=f"unresolved::{base_name}",
                                edge_type=SymbolEdgeType.EXTENDS,
                                provenance={"base_name": base_name},
                                source_location={"line": node.lineno, "col": node.col_offset},
                            )
                        )

                prev_class = self.current_class
                self.current_class = qname
                self.generic_visit(node)
                self.current_class = prev_class

            def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
                is_method = self.current_class is not None
                kind = SymbolKind.METHOD if is_method else SymbolKind.FUNCTION
                qname = f"{self.current_class}.{node.name}" if self.current_class else node.name
                is_exported = bool(not node.name.startswith("_") or node.name in exports)

                fn_sym = SymbolManager.build_symbol(
                    file_id=file_id,
                    name=node.name,
                    qualified_name=qname,
                    kind=kind,
                    exported=is_exported,
                    line=node.lineno,
                    column=node.col_offset,
                )
                symbols.append(fn_sym)

                # Type annotations on arguments
                for arg in node.args.args + getattr(node.args, "kwonlyargs", []):
                    if arg.annotation and isinstance(arg.annotation, ast.Name):
                        edges.append(
                            SymbolEdge(
                                source_symbol=fn_sym.symbol_id,
                                target_symbol=f"unresolved::{arg.annotation.id}",
                                edge_type=SymbolEdgeType.TYPE_USES,
                                provenance={"type_annotation": arg.annotation.id},
                                source_location={"line": arg.lineno, "col": arg.col_offset},
                            )
                        )

                prev_fn = self.current_function
                self.current_function = qname

                # Calls inside function
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        callee_name = None
                        if isinstance(child.func, ast.Name):
                            callee_name = child.func.id
                        elif isinstance(child.func, ast.Attribute):
                            callee_name = child.func.attr
                        if callee_name and callee_name != node.name:
                            edges.append(
                                SymbolEdge(
                                    source_symbol=fn_sym.symbol_id,
                                    target_symbol=f"unresolved::{callee_name}",
                                    edge_type=SymbolEdgeType.CALLS,
                                    provenance={"callee": callee_name},
                                    source_location={"line": child.lineno, "col": child.col_offset},
                                )
                            )

                self.current_function = prev_fn

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self.visit_FunctionDef(node)

        Visitor().visit(tree)
        return symbols, edges, {"import_map": import_map, "exports": list(exports)}
