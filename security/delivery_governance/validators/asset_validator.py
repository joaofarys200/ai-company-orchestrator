"""
Validador de Integridade de Recursos e Módulos.
Verifica:
- href, src e imports estáticos em ficheiros HTML, CSS e JavaScript/TypeScript.
- Deteção de ficheiros locais em falta (Missing CSS, Missing JS, Broken Module).
- Validação de caminhos relativos e coerência de extensões.
"""

from __future__ import annotations

import hashlib
import os
import re
import urllib.parse
import urllib.request
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

    @classmethod
    def validate_served_assets(cls, project_root: str, base_url: str) -> Dict[str, Any]:
        """
        Audita a cadeia completa HTTP:
        HTML -> scripts/estilos -> hash HTTP vs hash do disco.
        Garante que o browser recebe efetivamente os assets atualizados do disco.
        """
        violations: List[str] = []
        assets_evaluated: List[Dict[str, Any]] = []

        if not base_url.endswith("/"):
            base_url += "/"

        # 1. Obter HTML servido pelo servidor
        html_body = ""
        try:
            req = urllib.request.Request(
                base_url,
                headers={"User-Agent": "Jarvis-Asset-Validator/1.0", "Cache-Control": "no-cache"},
            )
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                if resp.status >= 400:
                    return {
                        "valid": False,
                        "base_url": base_url,
                        "violations": [f"HTTP_ENTRYPOINT_ERROR: Endpoint {base_url} devolveu status {resp.status}."],
                        "assets": [],
                    }
                html_body = resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            return {
                "valid": False,
                "base_url": base_url,
                "violations": [f"HTTP_CONNECTION_ERROR: Falha ao ligar ao endpoint {base_url}: {e}"],
                "assets": [],
            }

        # 2. Extrair referências de scripts e stylesheets do HTML servido
        script_srcs = re.findall(r'<script[^>]+src=[\'"]([^\'"]+)[\'"]', html_body, re.IGNORECASE)
        style_hrefs = re.findall(r'<link[^>]+rel=[\'"]stylesheet[\'"][^>]+href=[\'"]([^\'"]+)[\'"]', html_body, re.IGNORECASE)

        raw_references = [(s, "script") for s in script_srcs] + [(h, "stylesheet") for h in style_hrefs]

        for ref, kind in raw_references:
            if ref.startswith(("http://", "https://", "//")):
                # Recurso externo CDN (ex: Google Fonts)
                continue

            clean_path = ref.split("?")[0].split("#")[0].lstrip("/")
            disk_path = os.path.join(project_root, clean_path)
            asset_url = urllib.parse.urljoin(base_url, ref)

            asset_record = {
                "reference": ref,
                "kind": kind,
                "expected_disk_path": clean_path,
                "requested_url": asset_url,
                "disk_exists": os.path.isfile(disk_path),
                "http_status": None,
                "disk_hash": "",
                "served_hash": "",
                "matches": False,
            }

            if not os.path.isfile(disk_path):
                violations.append(f"MISSING_DISK_ASSET: Asset '{clean_path}' referenciado no HTML servido não existe no disco.")
                assets_evaluated.append(asset_record)
                continue

            try:
                disk_bytes = Path(disk_path).read_bytes()
                asset_record["disk_hash"] = hashlib.sha256(disk_bytes).hexdigest()[:16]
            except Exception as read_err:
                violations.append(f"DISK_READ_ERROR: Erro ao ler asset '{clean_path}': {read_err}")
                assets_evaluated.append(asset_record)
                continue

            try:
                a_req = urllib.request.Request(
                    asset_url,
                    headers={"User-Agent": "Jarvis-Asset-Validator/1.0", "Cache-Control": "no-cache"},
                )
                with urllib.request.urlopen(a_req, timeout=3.0) as a_resp:
                    asset_record["http_status"] = a_resp.status
                    if a_resp.status >= 400:
                        violations.append(f"ASSET_HTTP_ERROR: Asset '{ref}' falhou com status {a_resp.status}.")
                    else:
                        served_bytes = a_resp.read()
                        asset_record["served_hash"] = hashlib.sha256(served_bytes).hexdigest()[:16]
                        asset_record["matches"] = (asset_record["disk_hash"] == asset_record["served_hash"])
                        if not asset_record["matches"]:
                            violations.append(
                                f"STALE_SERVED_ASSET: O asset '{ref}' servido pelo servidor (hash {asset_record['served_hash']}) "
                                f"não corresponde ao ficheiro atual no disco (hash {asset_record['disk_hash']}). "
                                f"O servidor ou browser está a utilizar uma versão desatualizada ou em cache."
                            )
            except Exception as http_err:
                violations.append(f"ASSET_NETWORK_FAILURE: Falha de rede ao descarregar '{ref}': {http_err}")

            assets_evaluated.append(asset_record)

        return {
            "valid": len(violations) == 0,
            "base_url": base_url,
            "violations": violations,
            "assets": assets_evaluated,
        }

