from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import SymbolEdge, SymbolEdgeType, SymbolKind, SymbolNode
from .symbols import SymbolManager


class TypeScriptSymbolExtractor:
    """Extracts fine-grained symbol definitions and relationships from TypeScript and TSX."""

    INTERFACE_REGEX = re.compile(r"""(?:export\s+)?interface\s+([A-Za-z0-9_$]+)(?:\s+extends\s+([A-Za-z0-9_$,\s]+))?""")
    TYPE_REGEX = re.compile(r"""(?:export\s+)?type\s+([A-Za-z0-9_$]+)(?:<[^>]+>)?\s*=""")
    CLASS_REGEX = re.compile(r"""(?:export\s+)?(?:abstract\s+)?class\s+([A-Za-z0-9_$]+)(?:\s+extends\s+([A-Za-z0-9_$]+))?(?:\s+implements\s+([A-Za-z0-9_$,\s]+))?""")
    FUNC_REGEX = re.compile(r"""(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_$]+)\s*\(""")
    CONST_FUNC_REGEX = re.compile(r"""(?:export\s+)?const\s+([A-Za-z0-9_$]+)\s*(?::\s*[^=]+)?\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z0-9_$]+)\s*=>""")
    ENUM_REGEX = re.compile(r"""(?:export\s+)?enum\s+([A-Za-z0-9_$]+)""")

    # Imports
    NAMED_IMPORT_REGEX = re.compile(r"""import\s+(type\s+)?\{([^}]+)\}\s+from\s+['"]([^'"]+)['"]""")
    DEFAULT_IMPORT_REGEX = re.compile(r"""import\s+([A-Za-z0-9_$]+)\s+from\s+['"]([^'"]+)['"]""")
    NAMESPACE_IMPORT_REGEX = re.compile(r"""import\s+\*\s+as\s+([A-Za-z0-9_$]+)\s+from\s+['"]([^'"]+)['"]""")

    # Reexports
    REEXPORT_NAMED_REGEX = re.compile(r"""export\s+\{([^}]+)\}\s+from\s+['"]([^'"]+)['"]""")
    REEXPORT_ALL_REGEX = re.compile(r"""export\s+\*\s+from\s+['"]([^'"]+)['"]""")
    REEXPORT_ALL_AS_REGEX = re.compile(r"""export\s+\*\s+as\s+([A-Za-z0-9_$]+)\s+from\s+['"]([^'"]+)['"]""")

    def __init__(self, symbol_mgr: Optional[SymbolManager] = None) -> None:
        self.mgr = symbol_mgr or SymbolManager()

    @classmethod
    def extract(cls, file_id: str, content: str, module_id: str = "") -> Tuple[List[SymbolNode], List[SymbolEdge], Dict[str, Any]]:
        file_id = file_id.replace("\\", "/")
        symbols: List[SymbolNode] = []
        edges: List[SymbolEdge] = []
        import_map: Dict[str, Dict[str, Any]] = {}
        reexport_list: List[Dict[str, Any]] = []

        lines = content.splitlines()

        # 1. Interfaces
        for line_no, line in enumerate(lines, 1):
            for match in cls.INTERFACE_REGEX.finditer(line):
                name, extends_clause = match.groups()
                is_exported = "export" in line[:match.start() + 7]
                sym = SymbolManager.build_symbol(
                    file_id=file_id,
                    name=name,
                    kind=SymbolKind.INTERFACE,
                    language="typescript",
                    exported=is_exported,
                    line=line_no,
                )
                symbols.append(sym)

                if extends_clause:
                    for base in [b.strip() for b in extends_clause.split(",") if b.strip()]:
                        edges.append(
                            SymbolEdge(
                                source_symbol=sym.symbol_id,
                                target_symbol=f"unresolved::{base}",
                                edge_type=SymbolEdgeType.EXTENDS,
                                provenance={"base_interface": base},
                                source_location={"line": line_no},
                            )
                        )

        # 2. Types
        for line_no, line in enumerate(lines, 1):
            for match in cls.TYPE_REGEX.finditer(line):
                name = match.group(1)
                is_exported = "export" in line[:match.start() + 7]
                sym = SymbolManager.build_symbol(
                    file_id=file_id,
                    name=name,
                    kind=SymbolKind.TYPE,
                    language="typescript",
                    exported=is_exported,
                    line=line_no,
                )
                symbols.append(sym)

        # 3. Classes
        for line_no, line in enumerate(lines, 1):
            for match in cls.CLASS_REGEX.finditer(line):
                name, extends_clause, implements_clause = match.groups()
                is_exported = "export" in line[:match.start() + 7]
                sym = SymbolManager.build_symbol(
                    file_id=file_id,
                    name=name,
                    kind=SymbolKind.CLASS,
                    language="typescript",
                    exported=is_exported,
                    line=line_no,
                )
                symbols.append(sym)

                if extends_clause:
                    edges.append(
                        SymbolEdge(
                            source_symbol=sym.symbol_id,
                            target_symbol=f"unresolved::{extends_clause.strip()}",
                            edge_type=SymbolEdgeType.EXTENDS,
                            provenance={"base_class": extends_clause.strip()},
                            source_location={"line": line_no},
                        )
                    )
                if implements_clause:
                    for iface in [i.strip() for i in implements_clause.split(",") if i.strip()]:
                        edges.append(
                            SymbolEdge(
                                source_symbol=sym.symbol_id,
                                target_symbol=f"unresolved::{iface}",
                                edge_type=SymbolEdgeType.IMPLEMENTS,
                                provenance={"interface": iface},
                                source_location={"line": line_no},
                            )
                        )

        # 4. Functions & Arrow Functions
        for line_no, line in enumerate(lines, 1):
            for match in cls.FUNC_REGEX.finditer(line):
                name = match.group(1)
                is_exported = "export" in line[:match.start() + 7]
                sym = SymbolManager.build_symbol(
                    file_id=file_id,
                    name=name,
                    kind=SymbolKind.FUNCTION,
                    language="typescript",
                    exported=is_exported,
                    line=line_no,
                )
                symbols.append(sym)

            for match in cls.CONST_FUNC_REGEX.finditer(line):
                name = match.group(1)
                is_exported = "export" in line[:match.start() + 7]
                sym = SymbolManager.build_symbol(
                    file_id=file_id,
                    name=name,
                    kind=SymbolKind.FUNCTION,
                    language="typescript",
                    exported=is_exported,
                    line=line_no,
                )
                symbols.append(sym)

        # 5. Enums
        for line_no, line in enumerate(lines, 1):
            for match in cls.ENUM_REGEX.finditer(line):
                name = match.group(1)
                is_exported = "export" in line[:match.start() + 7]
                sym = SymbolManager.build_symbol(
                    file_id=file_id,
                    name=name,
                    kind=SymbolKind.ENUM,
                    language="typescript",
                    exported=is_exported,
                    line=line_no,
                )
                symbols.append(sym)

        # 6. Imports
        for line_no, line in enumerate(lines, 1):
            # Named imports
            for match in cls.NAMED_IMPORT_REGEX.finditer(line):
                type_prefix, names_str, mod = match.groups()
                is_type = bool(type_prefix)
                for item in names_str.split(","):
                    item = item.strip()
                    if not item:
                        continue
                    if " as " in item:
                        orig, alias = [x.strip() for x in item.split(" as ")]
                    else:
                        orig, alias = item, item

                    import_map[alias] = {
                        "source_module": mod,
                        "imported_name": orig,
                        "is_type_only": is_type,
                        "line": line_no,
                    }

                    imp_sym = SymbolManager.build_symbol(
                        file_id=file_id,
                        name=alias,
                        kind=SymbolKind.IMPORT,
                        language="typescript",
                        imported=True,
                        line=line_no,
                        provenance={"source_module": mod, "original_name": orig, "is_type_only": is_type},
                    )
                    symbols.append(imp_sym)
                    edges.append(
                        SymbolEdge(
                            source_symbol=imp_sym.symbol_id,
                            target_symbol=f"{mod}::{orig}",
                            edge_type=SymbolEdgeType.TYPE_USES if is_type else SymbolEdgeType.IMPORTS,
                            provenance={"source_module": mod, "is_type_only": is_type},
                            source_location={"line": line_no},
                        )
                    )

            # Default imports
            for match in cls.DEFAULT_IMPORT_REGEX.finditer(line):
                alias, mod = match.groups()
                if "{" not in line and "*" not in line:
                    alias_clean = alias.strip()
                    import_map[alias_clean] = {
                        "source_module": mod,
                        "imported_name": "default",
                        "is_type_only": False,
                        "line": line_no,
                    }
                    imp_sym = SymbolManager.build_symbol(
                        file_id=file_id,
                        name=alias_clean,
                        kind=SymbolKind.IMPORT,
                        language="typescript",
                        imported=True,
                        line=line_no,
                        provenance={"source_module": mod, "default": True},
                    )
                    symbols.append(imp_sym)
                    edges.append(
                        SymbolEdge(
                            source_symbol=imp_sym.symbol_id,
                            target_symbol=f"{mod}::default",
                            edge_type=SymbolEdgeType.IMPORTS,
                            provenance={"source_module": mod, "default": True},
                            source_location={"line": line_no},
                        )
                    )

            # Namespace imports
            for match in cls.NAMESPACE_IMPORT_REGEX.finditer(line):
                alias, mod = match.groups()
                alias_clean = alias.strip()
                import_map[alias_clean] = {
                    "source_module": mod,
                    "imported_name": "*",
                    "is_type_only": False,
                    "line": line_no,
                }
                imp_sym = SymbolManager.build_symbol(
                    file_id=file_id,
                    name=alias_clean,
                    kind=SymbolKind.IMPORT,
                    language="typescript",
                    imported=True,
                    line=line_no,
                    provenance={"source_module": mod, "namespace": True},
                )
                symbols.append(imp_sym)
                edges.append(
                    SymbolEdge(
                        source_symbol=imp_sym.symbol_id,
                        target_symbol=f"{mod}::*",
                        edge_type=SymbolEdgeType.IMPORTS,
                        provenance={"source_module": mod, "namespace": True},
                        source_location={"line": line_no},
                    )
                )

        # 7. Re-exports (Barrels)
        for line_no, line in enumerate(lines, 1):
            for match in cls.REEXPORT_NAMED_REGEX.finditer(line):
                names_str, mod = match.groups()
                for item in names_str.split(","):
                    item = item.strip()
                    if not item:
                        continue
                    if " as " in item:
                        orig, alias = [x.strip() for x in item.split(" as ")]
                    else:
                        orig, alias = item, item

                    reexport_list.append({
                        "exported_name": alias,
                        "original_name": orig,
                        "source_module": mod,
                        "line": line_no,
                    })

                    sym = SymbolManager.build_symbol(
                        file_id=file_id,
                        name=alias,
                        kind=SymbolKind.EXPORT,
                        language="typescript",
                        exported=True,
                        imported=True,
                        line=line_no,
                        provenance={"source_module": mod, "original_name": orig},
                    )
                    symbols.append(sym)
                    edges.append(
                        SymbolEdge(
                            source_symbol=sym.symbol_id,
                            target_symbol=f"{mod}::{orig}",
                            edge_type=SymbolEdgeType.REEXPORTS,
                            provenance={"source_module": mod, "original_name": orig},
                            source_location={"line": line_no},
                        )
                    )

            for match in cls.REEXPORT_ALL_REGEX.finditer(line):
                mod = match.group(1) if match.groups() else ""
                reexport_list.append({
                    "exported_name": "*",
                    "original_name": "*",
                    "source_module": mod,
                    "line": line_no,
                })

        return symbols, edges, {
            "import_map": import_map,
            "reexports": reexport_list,
        }
