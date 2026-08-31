"""
JARVIS OS — TSConfig & Monorepo Configuration Resolver (Fase 10.1: Coding Agent 2.1)
Parser e resolvedor dinâmico de tsconfig.json (paths, baseUrl, extends, references) e package.json (workspaces, exports).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass(slots=True)
class TSConfigData:
    """Configuração parseada e resolvida de um tsconfig.json."""
    file_path: str
    base_dir: str
    base_url: str = "."
    paths: Dict[str, List[str]] = field(default_factory=dict)
    extends: Optional[str] = None
    references: List[str] = field(default_factory=list)
    include: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)
    module_resolution: str = "node"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PackageJsonData:
    """Configuração parseada de um package.json dentro de um monorepo ou projeto."""
    file_path: str
    package_dir: str
    name: str
    version: str = "1.0.0"
    main: Optional[str] = None
    module: Optional[str] = None
    types: Optional[str] = None
    exports: Dict[str, Any] = field(default_factory=dict)
    workspaces: List[str] = field(default_factory=list)
    dependencies: Dict[str, str] = field(default_factory=dict)
    dev_dependencies: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def strip_json_comments(text: str) -> str:
    """Remove comentários de linha única (//) e multi-linha (/* ... */) e trailing commas comuns em tsconfig.json."""
    # Remove comentários de bloco
    text = re.sub(r"/\*[\s\S]*?\*/", "", text)
    # Remove comentários de linha única mantendo URLs como http:// intactas se dentro de aspas
    lines = []
    for line in text.splitlines():
        in_quotes = False
        res = []
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == '"' and (i == 0 or line[i - 1] != "\\"):
                in_quotes = not in_quotes
                res.append(ch)
            elif not in_quotes and ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
                break  # Linha comentada a partir daqui
            else:
                res.append(ch)
            i += 1
        lines.append("".join(res))
    clean = "\n".join(lines)
    # Remove trailing commas antes de } ou ]
    clean = re.sub(r",\s*([\]}])", r"\1", clean)
    return clean


class TSConfigResolver:
    """Resolvedor de configurações TypeScript com suporte a extends recursivo e aliases de caminho."""

    @classmethod
    def load_tsconfig(cls, file_path: str, visited: Optional[Set[str]] = None) -> Optional[TSConfigData]:
        """Carrega e resolve um tsconfig.json, mesclando com o ficheiro base se houver 'extends'."""
        if visited is None:
            visited = set()

        abs_path = os.path.realpath(os.path.abspath(file_path))
        if not os.path.isfile(abs_path) or abs_path in visited:
            return None

        visited.add(abs_path)
        base_dir = os.path.dirname(abs_path)

        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()
            clean_json = strip_json_comments(raw)
            data = json.loads(clean_json) if clean_json.strip() else {}
        except Exception:
            return None

        compiler_opts = data.get("compilerOptions", {})
        base_url = compiler_opts.get("baseUrl", ".")
        paths = compiler_opts.get("paths", {})
        extends_target = data.get("extends")
        references_raw = data.get("references", [])
        references = [r.get("path", "") for r in references_raw if isinstance(r, dict) and "path" in r]
        include = data.get("include", [])
        exclude = data.get("exclude", [])
        mod_res = compiler_opts.get("moduleResolution", "node")

        # Se houver 'extends', resolve a base primeiro
        merged_paths = dict(paths)
        if extends_target:
            extends_path = os.path.normpath(os.path.join(base_dir, extends_target))
            if not extends_path.endswith(".json"):
                extends_path += ".json"
            base_config = cls.load_tsconfig(extends_path, visited.copy())
            if base_config:
                # Herda paths da base para aliases que não foram sobrepostos
                for k, v in base_config.paths.items():
                    if k not in merged_paths:
                        # Ajusta os caminhos herdados para serem relativos à localização da base
                        merged_paths[k] = v
                if base_url == "." and base_config.base_url != ".":
                    base_url = base_config.base_url

        return TSConfigData(
            file_path=abs_path,
            base_dir=base_dir,
            base_url=base_url,
            paths=merged_paths,
            extends=extends_target,
            references=references,
            include=include,
            exclude=exclude,
            module_resolution=mod_res,
        )

    @classmethod
    def resolve_alias_path(
        cls,
        import_specifier: str,
        tsconfig: TSConfigData,
        workspace_files: Set[str],
        workspace_root: str,
    ) -> Optional[str]:
        """Tenta resolver um alias de importação (ex: '@/components/Button') para um ficheiro real no workspace."""
        if not tsconfig or not tsconfig.paths:
            return None

        # Ordena chaves de paths pelo comprimento do prefixo para casamento de maior especificidade
        sorted_patterns = sorted(tsconfig.paths.keys(), key=lambda k: len(k), reverse=True)

        for pattern in sorted_patterns:
            target_templates = tsconfig.paths[pattern]
            if pattern.endswith("/*"):
                prefix = pattern[:-2]
                if import_specifier == prefix or import_specifier.startswith(prefix + "/"):
                    subpath = import_specifier[len(prefix):].lstrip("/")
                    for template in target_templates:
                        if template == "*":
                            target_base = ""
                        elif template.endswith("/*"):
                            target_base = template[:-2]
                        else:
                            target_base = template
                        resolved_candidate = os.path.normpath(
                            os.path.join(tsconfig.base_dir, tsconfig.base_url, target_base, subpath)
                        ).replace(os.sep, "/")
                        rel_candidate = os.path.relpath(resolved_candidate, workspace_root).replace(os.sep, "/")

                        found = cls._probe_file_extensions(rel_candidate, workspace_files)
                        if found:
                            return found
            elif pattern == import_specifier:
                for template in target_templates:
                    resolved_candidate = os.path.normpath(
                        os.path.join(tsconfig.base_dir, tsconfig.base_url, template)
                    ).replace(os.sep, "/")
                    rel_candidate = os.path.relpath(resolved_candidate, workspace_root).replace(os.sep, "/")

                    found = cls._probe_file_extensions(rel_candidate, workspace_files)
                    if found:
                        return found

        return None

    @staticmethod
    def _probe_file_extensions(candidate_rel: str, workspace_files: Set[str]) -> Optional[str]:
        """Verifica se o caminho existe com extensões TypeScript/JavaScript padrão ou como barrel file."""
        if candidate_rel in workspace_files:
            return candidate_rel

        # Tenta extensões diretas
        for ext in (".ts", ".tsx", ".d.ts", ".js", ".jsx", ".mjs", ".cjs", ".json"):
            with_ext = candidate_rel + ext
            if with_ext in workspace_files:
                return with_ext

        # Tenta barrel files (index)
        for barrel in ("/index.ts", "/index.tsx", "/index.js", "/index.jsx", "/index.d.ts"):
            with_barrel = candidate_rel.rstrip("/") + barrel
            if with_barrel in workspace_files:
                return with_barrel

        return None


class MonorepoResolver:
    """Descobridor e resolvedor de pacotes e subpath exports em monorepos."""

    @classmethod
    def load_package_json(cls, file_path: str) -> Optional[PackageJsonData]:
        """Carrega e analisa um ficheiro package.json."""
        abs_path = os.path.realpath(os.path.abspath(file_path))
        if not os.path.isfile(abs_path):
            return None

        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
        except Exception:
            return None

        name = data.get("name", "")
        if not name:
            name = os.path.basename(os.path.dirname(abs_path))

        workspaces_raw = data.get("workspaces", [])
        if isinstance(workspaces_raw, dict):
            workspaces = workspaces_raw.get("packages", [])
        elif isinstance(workspaces_raw, list):
            workspaces = workspaces_raw
        else:
            workspaces = []

        return PackageJsonData(
            file_path=abs_path,
            package_dir=os.path.dirname(abs_path),
            name=name,
            version=data.get("version", "1.0.0"),
            main=data.get("main"),
            module=data.get("module"),
            types=data.get("types") or data.get("typings"),
            exports=data.get("exports") if isinstance(data.get("exports"), dict) else {},
            workspaces=workspaces,
            dependencies=data.get("dependencies", {}) if isinstance(data.get("dependencies"), dict) else {},
            dev_dependencies=data.get("devDependencies", {}) if isinstance(data.get("devDependencies"), dict) else {},
        )

    @classmethod
    def discover_monorepo_packages(cls, workspace_root: str) -> Dict[str, PackageJsonData]:
        """Varre todo o workspace e constrói o mapa de pacotes {package_name: PackageJsonData}."""
        packages: Dict[str, PackageJsonData] = {}
        abs_root = os.path.realpath(os.path.abspath(workspace_root))

        for root, dirs, files in os.walk(abs_root):
            # Ignora node_modules e diretórios de build
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "dist", "build", ".next", ".venv", "__pycache__")]
            if "package.json" in files:
                pkg_path = os.path.join(root, "package.json")
                pkg_data = cls.load_package_json(pkg_path)
                if pkg_data and pkg_data.name:
                    packages[pkg_data.name] = pkg_data

        return packages

    @classmethod
    def resolve_package_import(
        cls,
        import_specifier: str,
        packages: Dict[str, PackageJsonData],
        workspace_files: Set[str],
        workspace_root: str,
    ) -> Optional[str]:
        """Resolve imports entre pacotes do monorepo (ex: '@org/core' ou '@org/core/utils')."""
        # 1. Tenta match exato do nome do pacote
        if import_specifier in packages:
            pkg = packages[import_specifier]
            return cls._resolve_package_entrypoint(pkg, workspace_files, workspace_root)

        # 2. Tenta subpath export (ex: '@org/core/utils')
        for pkg_name, pkg in packages.items():
            if import_specifier.startswith(pkg_name + "/"):
                subpath = "." + import_specifier[len(pkg_name):]
                # Verifica no mapa de exports do package.json
                if pkg.exports and subpath in pkg.exports:
                    target_entry = pkg.exports[subpath]
                    if isinstance(target_entry, dict):
                        target_entry = target_entry.get("import") or target_entry.get("default") or target_entry.get("require")
                    if isinstance(target_entry, str):
                        cand = os.path.normpath(os.path.join(pkg.package_dir, target_entry))
                        rel_cand = os.path.relpath(cand, workspace_root).replace(os.sep, "/")
                        return TSConfigResolver._probe_file_extensions(rel_cand, workspace_files)

                # Fallback: subpath direto na pasta do pacote
                direct_sub = import_specifier[len(pkg_name):].lstrip("/")
                for base_sub in ("src", "lib", ""):
                    cand = os.path.normpath(os.path.join(pkg.package_dir, base_sub, direct_sub))
                    rel_cand = os.path.relpath(cand, workspace_root).replace(os.sep, "/")
                    found = TSConfigResolver._probe_file_extensions(rel_cand, workspace_files)
                    if found:
                        return found

        return None

    @classmethod
    def _resolve_package_entrypoint(
        cls,
        pkg: PackageJsonData,
        workspace_files: Set[str],
        workspace_root: str,
    ) -> Optional[str]:
        """Determina o ponto de entrada principal de um pacote no monorepo."""
        # 1. Se tiver export default/root no exports map
        if pkg.exports and "." in pkg.exports:
            root_exp = pkg.exports["."]
            if isinstance(root_exp, dict):
                root_exp = root_exp.get("import") or root_exp.get("default") or root_exp.get("types")
            if isinstance(root_exp, str):
                cand = os.path.normpath(os.path.join(pkg.package_dir, root_exp))
                rel = os.path.relpath(cand, workspace_root).replace(os.sep, "/")
                found = TSConfigResolver._probe_file_extensions(rel, workspace_files)
                if found:
                    return found

        # 2. Main / Module / Types
        for entry_field in (pkg.module, pkg.main, pkg.types):
            if entry_field:
                cand = os.path.normpath(os.path.join(pkg.package_dir, entry_field))
                rel = os.path.relpath(cand, workspace_root).replace(os.sep, "/")
                found = TSConfigResolver._probe_file_extensions(rel, workspace_files)
                if found:
                    return found

        # 3. Convenções padrão src/index.ts ou index.ts
        for default_cand in ("src/index.ts", "src/index.tsx", "index.ts", "index.tsx", "src/index.js", "index.js"):
            cand = os.path.normpath(os.path.join(pkg.package_dir, default_cand))
            rel = os.path.relpath(cand, workspace_root).replace(os.sep, "/")
            if rel in workspace_files:
                return rel

        return None
