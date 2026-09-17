from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .edges import SymbolEdgeBuilder
from .models import SymbolEdge, SymbolEdgeType, SymbolKind, SymbolNode
from .symbols import SymbolManager


class JavaScriptSymbolExtractor:
    """Extracts symbols and granular dependency edges from JavaScript files (ESM & CommonJS)."""

    def __init__(self, symbol_mgr: Optional[SymbolManager] = None) -> None:
        self.mgr = symbol_mgr or SymbolManager()
        self.edge_builder = SymbolEdgeBuilder()

    def extract(self, file_id: str, content: str, module_id: str = "") -> Tuple[List[SymbolNode], List[SymbolEdge]]:
        """Extract JavaScript symbols and edges handling ESM and CommonJS."""
        symbols: List[SymbolNode] = []
        edges: List[SymbolEdge] = []
        lines = content.splitlines()
        normalized_file = file_id.replace("\\", "/")
        mod_id = module_id or normalized_file.split("/")[-1].replace(".js", "").replace(".jsx", "").replace(".mjs", "").replace(".cjs", "")

        # Track defined symbols
        defined_names: Set[str] = set()

        # 1. Module Symbol
        mod_sym = self.mgr.build_symbol(
            file_id=normalized_file,
            qualified_name=mod_id,
            name=mod_id,
            kind=SymbolKind.MODULE,
            language="javascript",
            exported=True,
            line=1,
            column=1,
            signature_hash=self.mgr.compute_signature_hash(f"module {mod_id}"),
            body_hash=self.mgr.compute_body_hash(content),
            provenance={"parser": "javascript_regex_ast", "type": "module"},
        )
        symbols.append(mod_sym)
        defined_names.add(mod_id)

        # 2. ESM Imports
        # import { a, b as c } from 'lib'
        import_named_pattern = re.compile(
            r"""import\s+(?:type\s+)?(?:\{\s*([^}]+)\s*\}|\*\s+as\s+([a-zA-Z_$][0-9a-zA-Z_$]*)|([a-zA-Z_$][0-9a-zA-Z_$]*))\s+from\s+['"]([^'"]+)['"]""",
            re.MULTILINE,
        )
        for idx, line in enumerate(lines, 1):
            for match in import_named_pattern.finditer(line):
                named_clause, namespace_clause, default_clause, import_source = match.groups()
                edge_type = SymbolEdgeType.TYPE_USES if "import type" in match.group(0) else SymbolEdgeType.IMPORTS

                if named_clause:
                    for item in named_clause.split(","):
                        item = item.strip()
                        if not item:
                            continue
                        if " as " in item:
                            orig_name, local_name = [x.strip() for x in item.split(" as ")]
                        else:
                            orig_name, local_name = item, item

                        sym = self.mgr.build_symbol(
                            file_id=normalized_file,
                            qualified_name=local_name,
                            name=local_name,
                            kind=SymbolKind.IMPORT,
                            language="javascript",
                            imported=True,
                            line=idx,
                            column=match.start(),
                            signature_hash=self.mgr.compute_signature_hash(f"import {orig_name}"),
                            body_hash=self.mgr.compute_body_hash(orig_name),
                            provenance={"import_source": import_source, "original_name": orig_name, "alias": local_name != orig_name},
                        )
                        symbols.append(sym)
                        defined_names.add(local_name)

                        edges.append(
                            self.edge_builder.build_edge(
                                source_symbol=sym.symbol_id,
                                target_symbol=f"{import_source}::{orig_name}",
                                edge_type=edge_type,
                                provenance={"import_source": import_source, "source_location": {"line": idx, "file": normalized_file}},
                                confidence=1.0,
                            )
                        )
                elif namespace_clause:
                    sym = self.mgr.build_symbol(
                        file_id=normalized_file,
                        qualified_name=namespace_clause,
                        name=namespace_clause,
                        kind=SymbolKind.IMPORT,
                        language="javascript",
                        imported=True,
                        line=idx,
                        column=match.start(),
                        signature_hash=self.mgr.compute_signature_hash(f"import * as {namespace_clause}"),
                        body_hash="",
                        provenance={"import_source": import_source, "namespace": True},
                    )
                    symbols.append(sym)
                    defined_names.add(namespace_clause)
                    edges.append(
                        self.edge_builder.build_edge(
                            source_symbol=sym.symbol_id,
                            target_symbol=f"{import_source}::*",
                            edge_type=SymbolEdgeType.IMPORTS,
                            provenance={"import_source": import_source},
                        )
                    )
                elif default_clause:
                    sym = self.mgr.build_symbol(
                        file_id=normalized_file,
                        qualified_name=default_clause,
                        name=default_clause,
                        kind=SymbolKind.IMPORT,
                        language="javascript",
                        imported=True,
                        line=idx,
                        column=match.start(),
                        signature_hash=self.mgr.compute_signature_hash(f"import default {default_clause}"),
                        body_hash="",
                        provenance={"import_source": import_source, "default": True},
                    )
                    symbols.append(sym)
                    defined_names.add(default_clause)
                    edges.append(
                        self.edge_builder.build_edge(
                            source_symbol=sym.symbol_id,
                            target_symbol=f"{import_source}::default",
                            edge_type=SymbolEdgeType.IMPORTS,
                            provenance={"import_source": import_source},
                        )
                    )

        # 3. CommonJS require: const x = require('lib') or const { a, b } = require('lib')
        require_named_pattern = re.compile(
            r"""(?:const|let|var)\s+\{\s*([^}]+)\s*\}\s*=\s*require\(\s*['"]([^'"]+)['"]\s*\)"""
        )
        require_default_pattern = re.compile(
            r"""(?:const|let|var)\s+([a-zA-Z_$][0-9a-zA-Z_$]*)\s*=\s*require\(\s*['"]([^'"]+)['"]\s*\)"""
        )
        dynamic_require_pattern = re.compile(r"""require\(([^)]+)\)""")

        for idx, line in enumerate(lines, 1):
            # Named destructured require
            for match in require_named_pattern.finditer(line):
                clause, req_source = match.groups()
                for item in clause.split(","):
                    item = item.strip()
                    if not item:
                        continue
                    if ":" in item:
                        orig_name, local_name = [x.strip() for x in item.split(":")]
                    else:
                        orig_name, local_name = item, item

                    sym = self.mgr.build_symbol(
                        file_id=normalized_file,
                        qualified_name=local_name,
                        name=local_name,
                        kind=SymbolKind.IMPORT,
                        language="javascript",
                        imported=True,
                        line=idx,
                        column=match.start(),
                        signature_hash=self.mgr.compute_signature_hash(f"require {orig_name}"),
                        body_hash="",
                        provenance={"require_source": req_source, "commonjs": True},
                    )
                    symbols.append(sym)
                    defined_names.add(local_name)
                    edges.append(
                        self.edge_builder.build_edge(
                            source_symbol=sym.symbol_id,
                            target_symbol=f"{req_source}::{orig_name}",
                            edge_type=SymbolEdgeType.IMPORTS,
                            provenance={"require_source": req_source, "commonjs": True},
                        )
                    )

            # Default require
            for match in require_default_pattern.finditer(line):
                var_name, req_source = match.groups()
                sym = self.mgr.build_symbol(
                    file_id=normalized_file,
                    qualified_name=var_name,
                    name=var_name,
                    kind=SymbolKind.IMPORT,
                    language="javascript",
                    imported=True,
                    line=idx,
                    column=match.start(),
                    signature_hash=self.mgr.compute_signature_hash(f"require default {var_name}"),
                    body_hash="",
                    provenance={"require_source": req_source, "commonjs": True},
                )
                symbols.append(sym)
                defined_names.add(var_name)
                edges.append(
                    self.edge_builder.build_edge(
                        source_symbol=sym.symbol_id,
                        target_symbol=f"{req_source}::default",
                        edge_type=SymbolEdgeType.IMPORTS,
                        provenance={"require_source": req_source, "commonjs": True},
                    )
                )

            # Dynamic require check (e.g. require(variable) or require(path.join(...)))
            for match in dynamic_require_pattern.finditer(line):
                arg = match.group(1).strip()
                if not (arg.startswith(("'", '"', "`")) and arg.endswith(("'", '"', "`"))):
                    # Dynamic require expression
                    edge = self.edge_builder.build_dynamic_edge(
                        source_symbol=mod_sym.symbol_id,
                        target_symbol=f"unknown_dynamic::{arg}",
                        provenance={"line": idx, "expression": arg, "kind": "dynamic_require"},
                    )
                    edges.append(edge)

        # 4. Classes
        class_pattern = re.compile(
            r"""(?:export\s+)?class\s+([a-zA-Z_$][0-9a-zA-Z_$]*)(?:\s+extends\s+([a-zA-Z_$][0-9a-zA-Z_$]*))?"""
        )
        for idx, line in enumerate(lines, 1):
            for match in class_pattern.finditer(line):
                cls_name, base_name = match.groups()
                is_exported = "export" in match.group(0)
                sym = self.mgr.build_symbol(
                    file_id=normalized_file,
                    qualified_name=cls_name,
                    name=cls_name,
                    kind=SymbolKind.CLASS,
                    language="javascript",
                    exported=is_exported,
                    line=idx,
                    column=match.start(),
                    signature_hash=self.mgr.compute_signature_hash(f"class {cls_name}"),
                    body_hash=self.mgr.compute_body_hash(line),
                )
                symbols.append(sym)
                defined_names.add(cls_name)

                if base_name:
                    edges.append(
                        self.edge_builder.build_extends_edge(
                            source_symbol=sym.symbol_id,
                            target_symbol=base_name,
                            provenance={"base": base_name, "line": idx},
                        )
                    )

        # 5. Functions
        func_pattern = re.compile(
            r"""(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z_$][0-9a-zA-Z_$]*)\s*\(([^)]*)\)"""
        )
        for idx, line in enumerate(lines, 1):
            for match in func_pattern.finditer(line):
                fn_name, params = match.groups()
                is_exported = "export" in match.group(0)
                sym = self.mgr.build_symbol(
                    file_id=normalized_file,
                    qualified_name=fn_name,
                    name=fn_name,
                    kind=SymbolKind.FUNCTION,
                    language="javascript",
                    exported=is_exported,
                    line=idx,
                    column=match.start(),
                    signature_hash=self.mgr.compute_signature_hash(f"function {fn_name}({params})"),
                    body_hash=self.mgr.compute_body_hash(line),
                )
                symbols.append(sym)
                defined_names.add(fn_name)

        # 6. Variables and Constants (including Arrow functions)
        general_var_pattern = re.compile(
            r"""(?:export\s+)?(const|let|var)\s+([a-zA-Z_$][0-9a-zA-Z_$]*)\s*="""
        )
        for idx, line in enumerate(lines, 1):
            for match in general_var_pattern.finditer(line):
                keyword, var_name = match.groups()
                is_exported = "export" in line[:match.start() + 7]
                is_arrow = "=>" in line[match.end():]
                if is_arrow:
                    kind = SymbolKind.FUNCTION
                elif keyword == "const":
                    kind = SymbolKind.CONSTANT
                else:
                    kind = SymbolKind.VARIABLE

                sym = self.mgr.build_symbol(
                    file_id=normalized_file,
                    qualified_name=var_name,
                    name=var_name,
                    kind=kind,
                    language="javascript",
                    exported=is_exported,
                    line=idx,
                    column=match.start(),
                    signature_hash=self.mgr.compute_signature_hash(f"{keyword} {var_name}"),
                    body_hash=self.mgr.compute_body_hash(line),
                )
                symbols.append(sym)
                defined_names.add(var_name)

        # 7. CommonJS Exports: module.exports = ... / exports.foo = ...
        cjs_export_prop_pattern = re.compile(r"""(?:module\.)?exports\.([a-zA-Z_$][0-9a-zA-Z_$]*)\s*=\s*([a-zA-Z_$][0-9a-zA-Z_$]*)""")
        for idx, line in enumerate(lines, 1):
            for match in cjs_export_prop_pattern.finditer(line):
                export_name, value_name = match.groups()
                sym = self.mgr.build_symbol(
                    file_id=normalized_file,
                    qualified_name=export_name,
                    name=export_name,
                    kind=SymbolKind.EXPORT,
                    language="javascript",
                    exported=True,
                    line=idx,
                    column=match.start(),
                    signature_hash=self.mgr.compute_signature_hash(f"exports.{export_name}"),
                    body_hash="",
                    provenance={"commonjs": True, "target": value_name},
                )
                symbols.append(sym)
                edges.append(
                    self.edge_builder.build_reexports_edge(
                        source_symbol=sym.symbol_id,
                        target_symbol=value_name,
                        provenance={"commonjs": True, "line": idx},
                    )
                )

        # 8. ESM Re-exports: export { x, y as z } from './m' or export * from './m'
        reexport_named_pattern = re.compile(r"""export\s*\{\s*([^}]+)\s*\}\s*from\s*['"]([^'"]+)['"]""")
        reexport_all_pattern = re.compile(r"""export\s*\*\s*(?:as\s+([a-zA-Z_$][0-9a-zA-Z_$]*)\s*)?from\s*['"]([^'"]+)['"]""")

        for idx, line in enumerate(lines, 1):
            for match in reexport_named_pattern.finditer(line):
                clause, target_module = match.groups()
                for item in clause.split(","):
                    item = item.strip()
                    if not item:
                        continue
                    if " as " in item:
                        orig_name, exp_name = [x.strip() for x in item.split(" as ")]
                    else:
                        orig_name, exp_name = item, item

                    sym = self.mgr.build_symbol(
                        file_id=normalized_file,
                        qualified_name=exp_name,
                        name=exp_name,
                        kind=SymbolKind.EXPORT,
                        language="javascript",
                        exported=True,
                        line=idx,
                        column=match.start(),
                        signature_hash=self.mgr.compute_signature_hash(f"reexport {exp_name}"),
                        body_hash="",
                        provenance={"reexport_source": target_module, "original_name": orig_name},
                    )
                    symbols.append(sym)
                    edges.append(
                        self.edge_builder.build_reexports_edge(
                            source_symbol=sym.symbol_id,
                            target_symbol=f"{target_module}::{orig_name}",
                            provenance={"target_module": target_module, "original_name": orig_name},
                        )
                    )

            for match in reexport_all_pattern.finditer(line):
                as_name, target_module = match.groups()
                exp_name = as_name or "*"
                sym = self.mgr.build_symbol(
                    file_id=normalized_file,
                    qualified_name=exp_name,
                    name=exp_name,
                    kind=SymbolKind.EXPORT,
                    language="javascript",
                    exported=True,
                    line=idx,
                    column=match.start(),
                    signature_hash=self.mgr.compute_signature_hash(f"reexport * {exp_name}"),
                    body_hash="",
                    provenance={"reexport_source": target_module, "wildcard": True},
                )
                symbols.append(sym)
                edges.append(
                    self.edge_builder.build_reexports_edge(
                        source_symbol=sym.symbol_id,
                        target_symbol=f"{target_module}::*",
                        provenance={"target_module": target_module, "wildcard": True},
                    )
                )

        # 9. Function calls and References
        call_pattern = re.compile(r"""([a-zA-Z_$][0-9a-zA-Z_$]*)\s*\(""")
        for sym in symbols:
            if sym.kind in (SymbolKind.FUNCTION, SymbolKind.METHOD):
                # Search within lines
                for idx, line in enumerate(lines, 1):
                    for match in call_pattern.finditer(line):
                        callee = match.group(1)
                        if callee in defined_names and callee != sym.name:
                            edges.append(
                                self.edge_builder.build_calls_edge(
                                    source_symbol=sym.symbol_id,
                                    target_symbol=callee,
                                    provenance={"caller": sym.name, "callee": callee, "line": idx},
                                )
                            )

        return symbols, edges
