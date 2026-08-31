"""
JARVIS OS — Repository Understanding & Symbol Graph Engine (Fase 10.1: Coding Agent 2.1)
Mapeamento estrutural profundo de repositórios, símbolos, dependências, rotas, TypeScript path aliases e monorepos.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field, asdict
from enum import Enum
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from intelligence.tsconfig_resolver import (
    MonorepoResolver,
    PackageJsonData,
    TSConfigData,
    TSConfigResolver,
)


class SymbolType(str, Enum):
    FUNCTION = "FUNCTION"
    CLASS = "CLASS"
    METHOD = "METHOD"
    VARIABLE = "VARIABLE"
    TYPE_ALIAS = "TYPE_ALIAS"
    CONSTANT = "CONSTANT"
    MODULE = "MODULE"
    ENDPOINT = "ENDPOINT"


@dataclass(slots=True)
class SymbolDefinition:
    """Definição formal de um símbolo no repositório."""
    name: str
    file_path: str
    line_number: int
    end_line: int
    symbol_type: str
    signature: str = ""
    docstring: str = ""
    is_exported: bool = True
    parent_symbol: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SymbolReference:
    """Referência ou utilização de um símbolo por outro ficheiro."""
    symbol_name: str
    source_file: str
    line_number: int
    target_file: Optional[str] = None
    is_import: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ModuleImport:
    """Registo de importação entre módulos."""
    source_file: str
    module_name: str
    imported_symbols: List[str]
    is_relative: bool
    line_number: int
    resolved_target: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ApiEndpoint:
    """Endpoint HTTP definido no backend (FastAPI, Flask, Express, etc.)."""
    file_path: str
    line_number: int
    http_method: str  # GET, POST, PUT, DELETE, PATCH
    route_path: str   # ex: /api/tasks, /api/users/{id}
    handler_name: str
    framework: str = "fastapi"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ApiClientCall:
    """Chamada de API efetuada pelo frontend ou cliente (fetch, axios, requests)."""
    file_path: str
    line_number: int
    http_method: str  # GET, POST, PUT, DELETE, PATCH
    route_path: str   # ex: /api/tasks
    client_library: str = "fetch"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BlastRadius:
    """Raio de impacto de alterações calculadas sobre o grafo."""
    changed_targets: List[str]
    directly_affected_files: List[str]
    transitively_affected_files: List[str]
    affected_symbols: List[str]
    affected_tests: List[str]
    affected_api_contracts: List[str]
    risk_score: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


IGNORED_DIRECTORIES = {
    ".git", ".jarvis", ".mypy_cache", ".next", ".pytest_cache",
    ".ruff_cache", ".venv", "__pycache__", "build", "coverage",
    "dist", "htmlcov", "node_modules", "out", "venv",
}


class RepositoryGraph:
    """Grafo de símbolos, módulos, importações, TypeScript aliases, monorepos e testes."""

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = os.path.realpath(os.path.abspath(workspace_root))
        self.files: Set[str] = set()
        self.symbols: Dict[str, List[SymbolDefinition]] = {}  # symbol_name -> [SymbolDefinition]
        self.file_symbols: Dict[str, List[SymbolDefinition]] = {}  # file_path -> [SymbolDefinition]
        self.references: Dict[str, List[SymbolReference]] = {}  # symbol_name -> [SymbolReference]
        self.imports: Dict[str, List[ModuleImport]] = {}  # file_path -> [ModuleImport]
        self.endpoints: List[ApiEndpoint] = []
        self.api_calls: List[ApiClientCall] = []
        self.test_mappings: Dict[str, List[str]] = {}  # test_file -> [impl_file]
        self.entrypoints: List[str] = []
        self.configs: List[str] = []
        self.tsconfigs: Dict[str, TSConfigData] = {}  # rel_path -> TSConfigData
        self.monorepo_packages: Dict[str, PackageJsonData] = {}  # pkg_name -> PackageJsonData
        self.barrel_exports: Dict[str, List[Dict[str, Any]]] = {}  # file_path -> list of re-exports
        self.circular_dependencies: List[List[str]] = []

    def scan(self) -> RepositoryGraph:
        """Executa scan determinístico sobre o workspace para popular o grafo completo."""
        self.files.clear()
        self.symbols.clear()
        self.file_symbols.clear()
        self.references.clear()
        self.imports.clear()
        self.endpoints.clear()
        self.api_calls.clear()
        self.test_mappings.clear()
        self.entrypoints.clear()
        self.configs.clear()
        self.tsconfigs.clear()
        self.monorepo_packages.clear()
        self.barrel_exports.clear()
        self.circular_dependencies.clear()

        # 1. Primeira Passagem: Indexação de ficheiros e configurações
        for root, dirs, filenames in os.walk(self.workspace_root):
            dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRECTORIES)
            for fname in sorted(filenames):
                abs_path = os.path.join(root, fname)
                rel_path = os.path.relpath(abs_path, self.workspace_root).replace(os.sep, "/")
                self.files.add(rel_path)

                lower = fname.lower()
                if lower in ("package.json", "requirements.txt", "pyproject.toml", "vite.config.ts"):
                    self.configs.append(rel_path)
                if lower.startswith("tsconfig") and lower.endswith(".json"):
                    self.configs.append(rel_path)
                    ts_data = TSConfigResolver.load_tsconfig(abs_path)
                    if ts_data:
                        self.tsconfigs[rel_path] = ts_data

                if lower in ("main.py", "server.py", "app.py", "index.html", "index.js", "main.tsx", "app.tsx"):
                    self.entrypoints.append(rel_path)

        # 2. Descobre pacotes em monorepo
        self.monorepo_packages = MonorepoResolver.discover_monorepo_packages(self.workspace_root)

        # 3. Segunda Passagem: Parser por linguagem
        for rel_path in sorted(self.files):
            abs_path = os.path.join(self.workspace_root, rel_path)
            lower = rel_path.lower()
            if lower.endswith(".py"):
                self._parse_python_file(abs_path, rel_path)
            elif lower.endswith((".js", ".jsx", ".ts", ".tsx")):
                self._parse_javascript_file(abs_path, rel_path)
            elif lower.endswith(".html"):
                self._parse_html_file(abs_path, rel_path)

        # 4. Resolução de dependências, barrel files e ciclos
        self._resolve_dependencies_and_tests()
        return self

    def _parse_python_file(self, abs_path: str, rel_path: str) -> None:
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            return

        self.file_symbols[rel_path] = []
        self.imports[rel_path] = []

        try:
            tree = ast.parse(content, filename=rel_path)
        except SyntaxError:
            self._parse_python_regex_fallback(content, rel_path)
            return

        lines = content.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sym = SymbolDefinition(
                    name=node.name,
                    file_path=rel_path,
                    line_number=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    symbol_type=SymbolType.FUNCTION.value,
                    signature=self._extract_py_signature(node, lines),
                    docstring=ast.get_docstring(node) or "",
                )
                self._add_symbol(sym)
                self._detect_python_endpoints(node, rel_path)

            elif isinstance(node, ast.ClassDef):
                sym = SymbolDefinition(
                    name=node.name,
                    file_path=rel_path,
                    line_number=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    symbol_type=SymbolType.CLASS.value,
                    docstring=ast.get_docstring(node) or "",
                )
                self._add_symbol(sym)

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imp = ModuleImport(
                        source_file=rel_path,
                        module_name=alias.name,
                        imported_symbols=[alias.asname or alias.name],
                        is_relative=False,
                        line_number=node.lineno,
                    )
                    self.imports[rel_path].append(imp)

            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                symbols = [a.name for a in node.names]
                imp = ModuleImport(
                    source_file=rel_path,
                    module_name=mod,
                    imported_symbols=symbols,
                    is_relative=node.level > 0,
                    line_number=node.lineno,
                )
                self.imports[rel_path].append(imp)

            elif isinstance(node, ast.Call):
                func_name = self._get_call_func_name(node.func)
                if func_name:
                    ref = SymbolReference(
                        symbol_name=func_name,
                        source_file=rel_path,
                        line_number=node.lineno,
                    )
                    self.references.setdefault(func_name, []).append(ref)
                self._detect_python_api_client_call(node, rel_path)

    def _extract_py_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef, lines: List[str]) -> str:
        try:
            line = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
            return line.strip()
        except Exception:
            return f"def {node.name}(...)"

    def _detect_python_endpoints(self, node: ast.FunctionDef | ast.AsyncFunctionDef, rel_path: str) -> None:
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                method = dec.func.attr.upper()
                if method in ("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"):
                    if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
                        route = dec.args[0].value
                        self.endpoints.append(ApiEndpoint(
                            file_path=rel_path,
                            line_number=node.lineno,
                            http_method=method,
                            route_path=self._normalize_route(route),
                            handler_name=node.name,
                            framework="fastapi",
                        ))

    def _detect_python_api_client_call(self, node: ast.Call, rel_path: str) -> None:
        if isinstance(node.func, ast.Attribute):
            method = node.func.attr.upper()
            if method in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    url = node.args[0].value
                    if url.startswith("/") or url.startswith("http://") or url.startswith("https://"):
                        route = self._extract_path_from_url(url)
                        self.api_calls.append(ApiClientCall(
                            file_path=rel_path,
                            line_number=node.lineno,
                            http_method=method,
                            route_path=self._normalize_route(route),
                            client_library="requests",
                        ))

    def _parse_javascript_file(self, abs_path: str, rel_path: str) -> None:
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            return

        self.file_symbols[rel_path] = []
        self.imports[rel_path] = []
        self.barrel_exports[rel_path] = []
        lines = content.splitlines()

        # 1. Regex de Funções, Classes, Constantes e Tipos JS/TS
        fn_pattern = re.compile(r"(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_$]+)\s*\(")
        arrow_pattern = re.compile(r"(?:export\s+)?(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>")
        class_pattern = re.compile(r"(?:export\s+)?class\s+([a-zA-Z0-9_$]+)")
        type_pattern = re.compile(r"(?:export\s+)?(?:type|interface)\s+([a-zA-Z0-9_$]+)")

        for idx, line in enumerate(lines, start=1):
            fn_match = fn_pattern.search(line)
            if fn_match:
                name = fn_match.group(1)
                self._add_symbol(SymbolDefinition(
                    name=name,
                    file_path=rel_path,
                    line_number=idx,
                    end_line=idx,
                    symbol_type=SymbolType.FUNCTION.value,
                    signature=line.strip(),
                ))
                if name.upper() in ("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD") and "export" in line:
                    derived_route = self._derive_route_from_filepath(rel_path)
                    if derived_route:
                        self.endpoints.append(ApiEndpoint(
                            file_path=rel_path,
                            line_number=idx,
                            http_method=name.upper(),
                            route_path=self._normalize_route(derived_route),
                            handler_name=name,
                            framework="nextjs",
                        ))

            arrow_match = arrow_pattern.search(line)
            if arrow_match:
                name = arrow_match.group(1)
                self._add_symbol(SymbolDefinition(
                    name=name,
                    file_path=rel_path,
                    line_number=idx,
                    end_line=idx,
                    symbol_type=SymbolType.FUNCTION.value,
                    signature=line.strip(),
                ))

            class_match = class_pattern.search(line)
            if class_match:
                name = class_match.group(1)
                self._add_symbol(SymbolDefinition(
                    name=name,
                    file_path=rel_path,
                    line_number=idx,
                    end_line=idx,
                    symbol_type=SymbolType.CLASS.value,
                ))

            type_match = type_pattern.search(line)
            if type_match:
                name = type_match.group(1)
                self._add_symbol(SymbolDefinition(
                    name=name,
                    file_path=rel_path,
                    line_number=idx,
                    end_line=idx,
                    symbol_type=SymbolType.TYPE_ALIAS.value,
                ))

        # 2. Imports JS/TS
        import_pattern = re.compile(r"import\s+(?:\{([^}]+)\}|([a-zA-Z0-9_$]+)|\*\s+as\s+([a-zA-Z0-9_$]+))\s+from\s+['\"]([^'\"]+)['\"]")
        for idx, line in enumerate(lines, start=1):
            m = import_pattern.search(line)
            if m:
                syms_group = m.group(1) or m.group(2) or m.group(3) or ""
                symbols = [s.strip().split(" as ")[0] for s in syms_group.split(",") if s.strip()]
                mod_path = m.group(4)
                self.imports[rel_path].append(ModuleImport(
                    source_file=rel_path,
                    module_name=mod_path,
                    imported_symbols=symbols,
                    is_relative=mod_path.startswith("."),
                    line_number=idx,
                ))

        # 3. Re-exports & Barrel Files: export * from './...' ou export { a, b } from './...'
        re_export_star = re.compile(r"export\s+\*\s+from\s+['\"]([^'\"]+)['\"]")
        re_export_named = re.compile(r"export\s+\{([^}]+)\}\s+from\s+['\"]([^'\"]+)['\"]")

        for idx, line in enumerate(lines, start=1):
            m_star = re_export_star.search(line)
            if m_star:
                self.barrel_exports[rel_path].append({
                    "source": m_star.group(1),
                    "symbols": "*",
                    "line": idx,
                })

            m_named = re_export_named.search(line)
            if m_named:
                syms = [s.strip().split(" as ")[0] for s in m_named.group(1).split(",") if s.strip()]
                self.barrel_exports[rel_path].append({
                    "source": m_named.group(2),
                    "symbols": syms,
                    "line": idx,
                })

        # 4. Chamadas de API do Frontend
        fetch_pattern = re.compile(r"fetch\s*\(\s*['\"`](/api/[^'\"`]+)['\"`]\s*(?:,\s*\{[^}]*method\s*:\s*['\"]([A-Z]+)['\"])?")
        axios_pattern = re.compile(r"axios\.(get|post|put|delete|patch)\s*\(\s*['\"`](/api/[^'\"`]+)['\"`]")

        for idx, line in enumerate(lines, start=1):
            f_match = fetch_pattern.search(line)
            if f_match:
                route = f_match.group(1)
                method = (f_match.group(2) or "GET").upper()
                self.api_calls.append(ApiClientCall(
                    file_path=rel_path,
                    line_number=idx,
                    http_method=method,
                    route_path=self._normalize_route(route),
                    client_library="fetch",
                ))

            a_match = axios_pattern.search(line)
            if a_match:
                method = a_match.group(1).upper()
                route = a_match.group(2)
                self.api_calls.append(ApiClientCall(
                    file_path=rel_path,
                    line_number=idx,
                    http_method=method,
                    route_path=self._normalize_route(route),
                    client_library="axios",
                ))

    def _parse_html_file(self, abs_path: str, rel_path: str) -> None:
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            return

        lines = content.splitlines()
        script_pattern = re.compile(r"<script[^>]+src=['\"]([^'\"]+)['\"]")
        link_pattern = re.compile(r"<link[^>]+href=['\"]([^'\"]+)['\"]")

        for idx, line in enumerate(lines, start=1):
            s_match = script_pattern.search(line)
            if s_match:
                ref_src = s_match.group(1)
                self.references.setdefault("html:script", []).append(SymbolReference(
                    symbol_name=ref_src,
                    source_file=rel_path,
                    line_number=idx,
                    is_import=True,
                ))

            l_match = link_pattern.search(line)
            if l_match:
                ref_href = l_match.group(1)
                self.references.setdefault("html:stylesheet", []).append(SymbolReference(
                    symbol_name=ref_href,
                    source_file=rel_path,
                    line_number=idx,
                    is_import=True,
                ))

    def _parse_python_regex_fallback(self, content: str, rel_path: str) -> None:
        fn_pattern = re.compile(r"def\s+([a-zA-Z0-9_]+)\s*\(")
        cls_pattern = re.compile(r"class\s+([a-zA-Z0-9_]+)")
        lines = content.splitlines()
        for idx, line in enumerate(lines, start=1):
            m_fn = fn_pattern.search(line)
            if m_fn:
                self._add_symbol(SymbolDefinition(
                    name=m_fn.group(1),
                    file_path=rel_path,
                    line_number=idx,
                    end_line=idx,
                    symbol_type=SymbolType.FUNCTION.value,
                ))
            m_cls = cls_pattern.search(line)
            if m_cls:
                self._add_symbol(SymbolDefinition(
                    name=m_cls.group(1),
                    file_path=rel_path,
                    line_number=idx,
                    end_line=idx,
                    symbol_type=SymbolType.CLASS.value,
                ))

    def _add_symbol(self, sym: SymbolDefinition) -> None:
        self.symbols.setdefault(sym.name, []).append(sym)
        self.file_symbols.setdefault(sym.file_path, []).append(sym)

    def _get_call_func_name(self, node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return None

    def _normalize_route(self, route: str) -> str:
        clean = route.split("?")[0].rstrip("/")
        if not clean.startswith("/"):
            clean = "/" + clean
        clean = re.sub(r":([a-zA-Z0-9_]+)", r"{\1}", clean)
        return clean.lower()

    def _derive_route_from_filepath(self, rel_path: str) -> Optional[str]:
        """Infere a rota HTTP a partir do caminho do ficheiro (ex: app/api/tasks/route.ts -> /api/tasks)."""
        clean = rel_path.replace(os.sep, "/")
        clean = os.path.splitext(clean)[0]
        clean = re.sub(r"/(?:route|index)$", "", clean)
        if "/api/" in clean:
            clean = clean[clean.index("/api/"):]
        elif clean.startswith("api/"):
            clean = "/" + clean
        elif clean.startswith("app/api/"):
            clean = clean[len("app"):]
        else:
            clean = "/" + clean
        return clean

    def _extract_path_from_url(self, url: str) -> str:
        if "://" in url:
            parts = url.split("://", 1)[1].split("/", 1)
            return "/" + parts[1] if len(parts) > 1 else "/"
        return url

    def _resolve_dependencies_and_tests(self) -> None:
        """Resolve importações (incluindo aliases de tsconfig e monorepo), propaga re-exports e mapeia testes."""
        # 1. Resolve imports
        for src_file, imp_list in self.imports.items():
            for imp in imp_list:
                resolved = self._resolve_import_path(src_file, imp.module_name)
                imp.resolved_target = resolved

        # 2. Propaga símbolos através de Barrel Files (ex: index.ts com export * from './X')
        self._propagate_barrel_exports()

        # 3. Mapeia testes aos ficheiros de implementação
        for file_path in self.files:
            lower = file_path.lower()
            if "test" in lower or lower.endswith("_test.py") or lower.endswith(".test.ts") or lower.endswith(".spec.ts"):
                impl_candidates = []
                for other_file in self.files:
                    if other_file == file_path:
                        continue
                    base_name = Path(other_file).stem
                    if base_name in lower:
                        impl_candidates.append(other_file)
                self.test_mappings[file_path] = impl_candidates

        # 4. Deteta dependências circulares no grafo de imports
        self.circular_dependencies = self.detect_circular_dependencies()

    def _propagate_barrel_exports(self) -> None:
        """Garante que importar de um barrel file (ex: index.ts) expõe os símbolos dos alvos re-exportados."""
        for barrel_file, re_exports in self.barrel_exports.items():
            for re_exp in re_exports:
                src_mod = re_exp["source"]
                target_file = self._resolve_import_path(barrel_file, src_mod)
                if target_file and target_file in self.file_symbols:
                    target_syms = self.file_symbols[target_file]
                    if re_exp["symbols"] == "*":
                        for sym in target_syms:
                            # Adiciona símbolo virtualmente ao barrel file se ainda não estiver
                            if sym not in self.file_symbols[barrel_file]:
                                self.file_symbols[barrel_file].append(sym)
                                self.symbols.setdefault(sym.name, []).append(sym)
                    elif isinstance(re_exp["symbols"], list):
                        for sym_name in re_exp["symbols"]:
                            matching = [s for s in target_syms if s.name == sym_name]
                            for sym in matching:
                                if sym not in self.file_symbols[barrel_file]:
                                    self.file_symbols[barrel_file].append(sym)
                                    self.symbols.setdefault(sym.name, []).append(sym)

    def _resolve_import_path(self, src_file: str, module_name: str) -> Optional[str]:
        if not module_name:
            return None
        src_dir = os.path.dirname(src_file)

        # 1. Imports Relativos (./... ou ../...)
        if module_name.startswith("."):
            norm = os.path.normpath(os.path.join(src_dir, module_name)).replace(os.sep, "/")
            found = TSConfigResolver._probe_file_extensions(norm, self.files)
            if found:
                return found

        # 2. Resolução via TSConfig Path Aliases (ex: '@/components/*' ou '@core/*')
        # Encontra o tsconfig mais próximo do ficheiro de origem
        active_tsconfig = self._find_matching_tsconfig(src_file)
        if active_tsconfig:
            resolved_alias = TSConfigResolver.resolve_alias_path(
                module_name,
                active_tsconfig,
                self.files,
                self.workspace_root,
            )
            if resolved_alias:
                return resolved_alias

        # Também tenta com qualquer outro tsconfig carregado no workspace
        for ts_data in self.tsconfigs.values():
            if ts_data != active_tsconfig:
                resolved_alias = TSConfigResolver.resolve_alias_path(
                    module_name,
                    ts_data,
                    self.files,
                    self.workspace_root,
                )
                if resolved_alias:
                    return resolved_alias

        # 3. Resolução via Monorepo Packages (ex: '@org/core' ou '@org/core/utils')
        if self.monorepo_packages:
            resolved_pkg = MonorepoResolver.resolve_package_import(
                module_name,
                self.monorepo_packages,
                self.files,
                self.workspace_root,
            )
            if resolved_pkg:
                return resolved_pkg

        # 4. Módulos Python Absolutos (ex: intelligence.project_context)
        parts = module_name.replace(".", "/")
        for ext in (".py", "/__init__.py"):
            candidate = parts + ext
            if candidate in self.files:
                return candidate
            if f"src/{candidate}" in self.files:
                return f"src/{candidate}"

        return None

    def _find_matching_tsconfig(self, src_file: str) -> Optional[TSConfigData]:
        """Localiza o tsconfig.json mais próximo subindo na hierarquia de diretórios."""
        src_dir = os.path.dirname(os.path.join(self.workspace_root, src_file))
        current = src_dir
        while current.startswith(self.workspace_root):
            cand_path = os.path.join(current, "tsconfig.json")
            rel_cand = os.path.relpath(cand_path, self.workspace_root).replace(os.sep, "/")
            if rel_cand in self.tsconfigs:
                return self.tsconfigs[rel_cand]
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent

        # Fallback para tsconfig.json na raiz se existir
        return self.tsconfigs.get("tsconfig.json")

    def detect_circular_dependencies(self) -> List[List[str]]:
        """Deteta ciclos no grafo de dependências entre ficheiros (A -> B -> C -> A)."""
        adj: Dict[str, Set[str]] = {}
        for src_file, imp_list in self.imports.items():
            adj.setdefault(src_file, set())
            for imp in imp_list:
                if imp.resolved_target and imp.resolved_target != src_file:
                    adj[src_file].add(imp.resolved_target)

        cycles: List[List[str]] = []
        visited: Set[str] = set()
        rec_stack: List[str] = []

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.append(node)

            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    # Ciclo encontrado
                    idx = rec_stack.index(neighbor)
                    cycle = rec_stack[idx:] + [neighbor]
                    cycles.append(cycle)

            rec_stack.pop()

        for f in self.files:
            if f not in visited:
                dfs(f)

        return cycles

    def find_definition(self, symbol_name: str, file_hint: Optional[str] = None) -> Optional[SymbolDefinition]:
        defs = self.symbols.get(symbol_name, [])
        if not defs:
            return None
        if file_hint:
            for d in defs:
                if d.file_path == file_hint:
                    return d
        return defs[0]

    def find_references(self, symbol_name: str, file_filter: Optional[str] = None) -> List[SymbolReference]:
        refs = self.references.get(symbol_name, [])
        if file_filter:
            return [r for r in refs if r.source_file == file_filter]
        return list(refs)

    def compute_blast_radius(self, changed_targets: List[str]) -> BlastRadius:
        directly_affected: Set[str] = set()
        transitively_affected: Set[str] = set()
        affected_symbols: Set[str] = set()
        affected_tests: Set[str] = set()
        affected_contracts: Set[str] = set()

        changed_files = set()
        for t in changed_targets:
            if t in self.files:
                changed_files.add(t)
            elif t in self.symbols:
                for sym_def in self.symbols[t]:
                    changed_files.add(sym_def.file_path)
                    affected_symbols.add(t)

        for src_file, imp_list in self.imports.items():
            for imp in imp_list:
                if imp.resolved_target in changed_files:
                    directly_affected.add(src_file)

        queue = list(directly_affected)
        while queue:
            current = queue.pop(0)
            transitively_affected.add(current)
            for src_file, imp_list in self.imports.items():
                if src_file not in transitively_affected and src_file not in changed_files:
                    for imp in imp_list:
                        if imp.resolved_target == current:
                            queue.append(src_file)

        all_affected = changed_files | directly_affected | transitively_affected
        for test_file, impl_list in self.test_mappings.items():
            if any(impl in all_affected for impl in impl_list) or test_file in all_affected:
                affected_tests.add(test_file)

        for endpoint in self.endpoints:
            if endpoint.file_path in all_affected:
                affected_contracts.add(f"{endpoint.http_method} {endpoint.route_path}")

        total_files = max(len(self.files), 1)
        impact_ratio = len(all_affected) / total_files
        risk_score = round(min(1.0, impact_ratio * 1.5 + (0.3 if affected_contracts else 0.0)), 2)

        return BlastRadius(
            changed_targets=list(changed_targets),
            directly_affected_files=sorted(directly_affected),
            transitively_affected_files=sorted(transitively_affected),
            affected_symbols=sorted(affected_symbols),
            affected_tests=sorted(affected_tests),
            affected_api_contracts=sorted(affected_contracts),
            risk_score=risk_score,
        )
