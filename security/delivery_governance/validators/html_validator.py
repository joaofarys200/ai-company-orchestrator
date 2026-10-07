"""
Validador de Documentos HTML e Estrutura Web.
Garante que:
- Ficheiros HTML possuem casca válida (DOCTYPE, html, head, body).
- Links para stylesheets (<link rel="stylesheet" href="...">) existem fisicamente.
- Tags de script (<script src="...">) existem fisicamente.
- Tags de imagem (<img src="...">) e recursos locais existem fisicamente.
- node --check NUNCA é considerado validação HTML.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


class HtmlDocumentValidator:
    """Valida a conformidade estrutural e de recursos estáticos de ficheiros HTML."""

    @classmethod
    def validate_html_file(
        cls,
        file_path: str,
        project_root: str,
        content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Valida um ficheiro HTML tanto estruturalmente como a nível de integridade de assets.
        """
        if content is None:
            if not os.path.isfile(file_path):
                return {
                    "valid": False,
                    "file": file_path,
                    "violations": [f"Ficheiro HTML não encontrado: {file_path}"],
                    "warnings": [],
                    "checked_assets": [],
                    "has_shell": False,
                }
            try:
                content = Path(file_path).read_text(encoding="utf-8", errors="ignore")
            except Exception as exc:
                return {
                    "valid": False,
                    "file": file_path,
                    "violations": [f"Erro ao ler ficheiro HTML: {exc}"],
                    "warnings": [],
                    "checked_assets": [],
                    "has_shell": False,
                }

        violations: List[str] = []
        warnings: List[str] = []
        checked_assets: List[Dict[str, Any]] = []

        lower = content.lower().strip()
        if not lower:
            return {
                "valid": False,
                "file": file_path,
                "violations": ["Ficheiro HTML está completamente vazio."],
                "warnings": [],
                "checked_assets": [],
                "has_shell": False,
            }

        # 1. Estrutura Canónica do Documento
        has_doctype = "<!doctype html" in lower
        has_html_open = "<html" in lower
        has_html_close = "</html>" in lower
        has_head_open = "<head" in lower
        has_head_close = "</head>" in lower
        has_body_open = "<body" in lower
        has_body_close = "</body>" in lower

        has_shell = has_html_open and has_body_open

        if not has_doctype:
            warnings.append("Documento HTML sem declaração <!DOCTYPE html>.")
        if not has_html_open or not has_html_close:
            violations.append("Documento HTML sem tag <html> raiz válida.")
        if not has_head_open or not has_head_close:
            violations.append("Documento HTML sem secção <head> válida.")
        if not has_body_open or not has_body_close:
            violations.append("Documento HTML sem secção <body> válida.")

        # 2. Verificação de Stylesheets (<link rel="stylesheet" href="...">)
        # Suporta ordem normal e atributos invertidos
        css_links = re.findall(r'<link\b[^>]*\bhref=[\'"]([^\'"]+)[\'"][^>]*\brel=[\'"]stylesheet[\'"]', content, re.IGNORECASE)
        css_links += re.findall(r'<link\b[^>]*\brel=[\'"]stylesheet[\'"][^>]*\bhref=[\'"]([^\'"]+)[\'"]', content, re.IGNORECASE)
        css_links = list(dict.fromkeys(css_links))  # remove duplicados

        html_dir = os.path.dirname(file_path) if os.path.isabs(file_path) else os.path.join(project_root, os.path.dirname(file_path))

        for href in css_links:
            # Ignora links remotos (http, https, //, cdn)
            if href.startswith(("http://", "https://", "//")):
                checked_assets.append({"type": "css", "target": href, "remote": True, "exists": True})
                continue

            clean_href = href.split("?")[0].split("#")[0]
            # Resolução relativa ao ficheiro HTML ou à raiz do projeto
            target_path = os.path.normpath(os.path.join(html_dir, clean_href))
            root_relative_path = os.path.normpath(os.path.join(project_root, clean_href.lstrip("/\\")))

            exists = os.path.isfile(target_path) or os.path.isfile(root_relative_path)
            checked_assets.append({
                "type": "css",
                "target": href,
                "resolved_path": target_path if os.path.isfile(target_path) else root_relative_path,
                "exists": exists,
            })
            if not exists:
                violations.append(f"MISSING_STYLESHEET: Folha de estilos referenciada não existe no disco: '{href}'")

        # 3. Verificação de Scripts (<script src="...">)
        script_srcs = re.findall(r'<script\b[^>]*\bsrc=[\'"]([^\'"]+)[\'"]', content, re.IGNORECASE)
        script_srcs = list(dict.fromkeys(script_srcs))

        for src in script_srcs:
            if src.startswith(("http://", "https://", "//")):
                checked_assets.append({"type": "js", "target": src, "remote": True, "exists": True})
                continue

            clean_src = src.split("?")[0].split("#")[0]
            target_path = os.path.normpath(os.path.join(html_dir, clean_src))
            root_relative_path = os.path.normpath(os.path.join(project_root, clean_src.lstrip("/\\")))

            exists = os.path.isfile(target_path) or os.path.isfile(root_relative_path)
            checked_assets.append({
                "type": "js",
                "target": src,
                "resolved_path": target_path if os.path.isfile(target_path) else root_relative_path,
                "exists": exists,
            })
            if not exists:
                violations.append(f"MISSING_SCRIPT: Script referenciado não existe no disco: '{src}'")

        # 4. Verificação de Imagens locais (<img src="...">)
        img_srcs = re.findall(r'<img\b[^>]*\bsrc=[\'"]([^\'"]+)[\'"]', content, re.IGNORECASE)
        for img in img_srcs:
            if img.startswith(("http://", "https://", "//", "data:")):
                continue
            clean_img = img.split("?")[0].split("#")[0]
            target_path = os.path.normpath(os.path.join(html_dir, clean_img))
            root_relative_path = os.path.normpath(os.path.join(project_root, clean_img.lstrip("/\\")))
            if not (os.path.isfile(target_path) or os.path.isfile(root_relative_path)):
                warnings.append(f"MISSING_IMAGE: Imagem referenciada não existe no disco: '{img}'")

        is_valid = len(violations) == 0

        return {
            "valid": is_valid,
            "file": file_path,
            "has_shell": has_shell,
            "violations": violations,
            "warnings": warnings,
            "checked_assets": checked_assets,
            "total_stylesheets": len(css_links),
            "total_scripts": len(script_srcs),
        }
