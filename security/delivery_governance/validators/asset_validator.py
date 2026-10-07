"""
Validador de Integridade de Recursos e Módulos.
Verifica:
- href, src e imports estáticos em ficheiros HTML, CSS e JavaScript/TypeScript.
- Deteção de ficheiros locais em falta (Missing CSS, Missing JS, Broken Module).
- Validação de caminhos relativos e coerência de extensões.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Set


class AssetIntegrityValidator:
    """Audita a integridade física de todos os assets e imports referenciados no projeto."""

    @classmethod
    def validate_project_assets(cls, project_root: str) -> Dict[str, Any]:
        """Varre o projeto e verifica a existência de todos os assets referenciados."""
        if not os.path.isdir(project_root):
            return {
                "valid": False,
                "project_root": project_root,
                "missing_assets": [f"Diretoria do projeto inexistente: {project_root}"],
                "total_checked": 0,
            }

        missing_assets: List[str] = []
        checked_references: List[Dict[str, Any]] = []

        for root, _, files in os.walk(project_root):
            if any(part in {"node_modules", ".git", "dist", "build", "__pycache__"} for part in Path(root).parts):
                continue

            for fname in files:
                fpath = os.path.join(root, fname)
                ext = Path(fname).suffix.lower()

                if ext in {".html", ".htm"}:
                    cls._check_html_assets(fpath, project_root, missing_assets, checked_references)
                elif ext in {".css"}:
                    cls._check_css_assets(fpath, project_root, missing_assets, checked_references)
                elif ext in {".js", ".mjs", ".ts"}:
                    cls._check_js_imports(fpath, project_root, missing_assets, checked_references)

        return {
            "valid": len(missing_assets) == 0,
            "project_root": project_root,
            "missing_assets": missing_assets,
            "total_checked": len(checked_references),
            "checked_references": checked_references,
        }

    @classmethod
    def _check_html_assets(
        cls,
        fpath: str,
        project_root: str,
        missing: List[str],
        checked: List[Dict[str, Any]],
    ) -> None:
        try:
            content = Path(fpath).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return

        rel_source = os.path.relpath(fpath, project_root).replace("\\", "/")
        source_dir = os.path.dirname(fpath)

        # Links (css, icon, etc.)
        links = re.findall(r'<link\b[^>]*\bhref=[\'"]([^\'"]+)[\'"]', content, re.IGNORECASE)
        for link in links:
            if link.startswith(("http://", "https://", "//", "data:")):
                continue
            clean = link.split("?")[0].split("#")[0]
            target1 = os.path.normpath(os.path.join(source_dir, clean))
            target2 = os.path.normpath(os.path.join(project_root, clean.lstrip("/\\")))
            exists = os.path.isfile(target1) or os.path.isfile(target2)
            checked.append({"source": rel_source, "reference": link, "type": "link", "exists": exists})
            if not exists:
                missing.append(f"Em {rel_source}: recurso <link> '{link}' não encontrado no disco.")

        # Scripts
        scripts = re.findall(r'<script\b[^>]*\bsrc=[\'"]([^\'"]+)[\'"]', content, re.IGNORECASE)
        for script in scripts:
            if script.startswith(("http://", "https://", "//", "data:")):
                continue
            clean = script.split("?")[0].split("#")[0]
            target1 = os.path.normpath(os.path.join(source_dir, clean))
            target2 = os.path.normpath(os.path.join(project_root, clean.lstrip("/\\")))
            exists = os.path.isfile(target1) or os.path.isfile(target2)
            checked.append({"source": rel_source, "reference": script, "type": "script", "exists": exists})
            if not exists:
                missing.append(f"Em {rel_source}: recurso <script> '{script}' não encontrado no disco.")

    @classmethod
    def _check_css_assets(
        cls,
        fpath: str,
        project_root: str,
        missing: List[str],
        checked: List[Dict[str, Any]],
    ) -> None:
        try:
            content = Path(fpath).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return

        rel_source = os.path.relpath(fpath, project_root).replace("\\", "/")
        source_dir = os.path.dirname(fpath)

        # @import url(...)
        imports = re.findall(r'@import\s+(?:url\()?[\'"]([^\'")]+)[\'"]\)?', content, re.IGNORECASE)
        for imp in imports:
            if imp.startswith(("http://", "https://", "//")):
                continue
            clean = imp.split("?")[0].split("#")[0]
            target = os.path.normpath(os.path.join(source_dir, clean))
            exists = os.path.isfile(target)
            checked.append({"source": rel_source, "reference": imp, "type": "css_import", "exists": exists})
            if not exists:
                missing.append(f"Em {rel_source}: @import '{imp}' não encontrado.")

    @classmethod
    def _check_js_imports(
        cls,
        fpath: str,
        project_root: str,
        missing: List[str],
        checked: List[Dict[str, Any]],
    ) -> None:
        try:
            content = Path(fpath).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return

        rel_source = os.path.relpath(fpath, project_root).replace("\\", "/")
        source_dir = os.path.dirname(fpath)

        # Relative ES imports: import ... from './...' or '../...'
        imports = re.findall(r'(?:import|from)\s+[\'"](\.[^\'"]+)[\'"]', content)
        for imp in imports:
            clean = imp.split("?")[0].split("#")[0]
            target = os.path.normpath(os.path.join(source_dir, clean))
            # Pode ser ficheiro direto ou ter extensão omitida (.js, .ts, etc.)
            exists = (
                os.path.isfile(target)
                or os.path.isfile(target + ".js")
                or os.path.isfile(target + ".ts")
                or os.path.isfile(os.path.join(target, "index.js"))
                or os.path.isfile(os.path.join(target, "index.ts"))
            )
            checked.append({"source": rel_source, "reference": imp, "type": "js_import", "exists": exists})
            if not exists:
                missing.append(f"Em {rel_source}: import relativo '{imp}' não existe no disco.")
