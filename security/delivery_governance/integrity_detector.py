"""
Analisador de Integridade e Preservação de Produto.
Deteta:
- Remoção destrutiva de cascas HTML, scripts, stylesheets e rotas.
- Regressões em capacidades previamente existentes.
- Substituições destrutivas de ficheiros sensíveis (> threshold).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from security.delivery_governance.models import ProductIntegrityDiff


class PreservationAnalyzer:
    """Audita a preservação de capacidades técnicas e visuais entre versões."""

    SENSITIVE_FILES = {
        "index.html",
        "package.json",
        "app.js",
        "server.js",
        "main.py",
        "app.py",
        "index.js",
        "vite.config.ts",
        "vite.config.js",
    }

    @classmethod
    def snapshot_project_state(cls, project_dir: str) -> Dict[str, Any]:
        """Captura o estado funcional e estrutural de um projeto antes de qualquer edição."""
        snapshot: Dict[str, Any] = {
            "html_files": {},
            "scripts": set(),
            "stylesheets": set(),
            "endpoints": set(),
            "event_listeners": set(),
            "buttons": set(),
            "forms": set(),
        }

        if not os.path.isdir(project_dir):
            return snapshot

        for root, _, files in os.walk(project_dir):
            # Ignora node_modules, .git, dist, etc.
            if any(part in {"node_modules", ".git", "dist", "build", "__pycache__"} for part in Path(root).parts):
                continue

            for fname in files:
                fpath = os.path.join(root, fname)
                rel_path = os.path.relpath(fpath, project_dir).replace("\\", "/")
                ext = Path(fname).suffix.lower()

                try:
                    content = Path(fpath).read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                if ext in {".html", ".htm"}:
                    html_info = cls._parse_html_structure(content)
                    snapshot["html_files"][rel_path] = html_info
                    snapshot["scripts"].update(html_info["scripts"])
                    snapshot["stylesheets"].update(html_info["stylesheets"])
                    snapshot["buttons"].update(html_info["buttons"])
                    snapshot["forms"].update(html_info["forms"])

                elif ext in {".js", ".mjs", ".ts", ".py"}:
                    endpoints = cls._parse_endpoints(content)
                    listeners = cls._parse_event_listeners(content)
                    snapshot["endpoints"].update(endpoints)
                    snapshot["event_listeners"].update(listeners)

        # Converte sets em listas para serialização
        return {
            "html_files": snapshot["html_files"],
            "scripts": sorted(list(snapshot["scripts"])),
            "stylesheets": sorted(list(snapshot["stylesheets"])),
            "endpoints": sorted(list(snapshot["endpoints"])),
            "event_listeners": sorted(list(snapshot["event_listeners"])),
            "buttons": sorted(list(snapshot["buttons"])),
            "forms": sorted(list(snapshot["forms"])),
        }

    @classmethod
    def compare_integrity(
        cls,
        before_snapshot: Dict[str, Any],
        project_dir: str,
        changes: Optional[List[Dict[str, Any]]] = None,
        project_id: str = "",
    ) -> ProductIntegrityDiff:
        """Compara o estado pós-alteração com o snapshot pré-alteração e gera ProductIntegrityDiff."""
        diff = ProductIntegrityDiff(project_id=project_id)
        after_snapshot = cls.snapshot_project_state(project_dir)

        # 1. Verificação de Scripts removidos
        before_scripts = set(before_snapshot.get("scripts", []))
        after_scripts = set(after_snapshot.get("scripts", []))
        removed_scripts = before_scripts - after_scripts
        if removed_scripts:
            diff.removed_scripts = sorted(list(removed_scripts))
            diff.violations.append(
                f"REMOVED_SCRIPTS: Scripts essenciais foram removidos do HTML: {diff.removed_scripts}"
            )
            diff.has_critical_regression = True

        # 2. Verificação de Stylesheets removidas
        before_css = set(before_snapshot.get("stylesheets", []))
        after_css = set(after_snapshot.get("stylesheets", []))
        removed_css = before_css - after_css
        if removed_css:
            diff.removed_stylesheets = sorted(list(removed_css))
            diff.violations.append(
                f"REMOVED_STYLESHEETS: Folhas de estilo CSS foram removidas do HTML: {diff.removed_stylesheets}"
            )
            diff.has_critical_regression = True

        # 3. Verificação de casca HTML e estrutura raiz
        before_html_files = before_snapshot.get("html_files", {})
        after_html_files = after_snapshot.get("html_files", {})
        for html_path, before_info in before_html_files.items():
            if html_path in after_html_files:
                after_info = after_html_files[html_path]
                if before_info.get("has_doctype") and not after_info.get("has_doctype"):
                    diff.missing_html_roots.append(f"{html_path}: DOCTYPE removido")
                    diff.has_critical_regression = True
                if before_info.get("has_html_tag") and not after_info.get("has_html_tag"):
                    diff.missing_html_roots.append(f"{html_path}: tag <html> removida")
                    diff.has_critical_regression = True
                if before_info.get("has_head_tag") and not after_info.get("has_head_tag"):
                    diff.missing_html_roots.append(f"{html_path}: tag <head> removida")
                    diff.has_critical_regression = True
                if before_info.get("has_body_tag") and not after_info.get("has_body_tag"):
                    diff.missing_html_roots.append(f"{html_path}: tag <body> removida")
                    diff.has_critical_regression = True

        # 4. Verificação de Botões / Funcionalidades prévias da UI
        before_buttons = set(before_snapshot.get("buttons", []))
        after_buttons = set(after_snapshot.get("buttons", []))
        dropped_buttons = before_buttons - after_buttons
        if dropped_buttons:
            diff.deleted_existing_features.extend([f"botão '{b}'" for b in dropped_buttons])
            diff.warnings.append(
                f"DROPPED_BUTTONS: Controles de UI existentes foram eliminados: {sorted(list(dropped_buttons))}"
            )

        # 5. Deteção de substituições destrutivas de ficheiros
        if changes:
            for item in changes:
                fname = item.get("file", "")
                old_text = item.get("previous_excerpt") or ""
                new_text = item.get("proposed_excerpt") or ""
                eval_res = DestructiveChangeDetector.evaluate_change_destructiveness(fname, old_text, new_text)
                if eval_res["is_destructive"]:
                    diff.destructive_file_replacements.append(eval_res)
                    if eval_res["severity"] == "CRITICAL":
                        diff.violations.append(
                            f"CRITICAL_DESTRUCTIVE_REPLACEMENT em {fname}: {eval_res['reason']}"
                        )
                        diff.has_critical_regression = True
                    else:
                        diff.warnings.append(
                            f"DESTRUCTIVE_FILE_REPLACEMENT em {fname}: {eval_res['reason']}"
                        )

        return diff

    @classmethod
    def _parse_html_structure(cls, html: str) -> Dict[str, Any]:
        """Extrai meta-informações estruturais de um documento HTML."""
        lower = html.lower()
        scripts = re.findall(r'<script\b[^>]*src=[\'"]([^\'"]+)[\'"]', html, re.IGNORECASE)
        stylesheets = re.findall(r'<link\b[^>]*rel=[\'"]stylesheet[\'"][^>]*href=[\'"]([^\'"]+)[\'"]', html, re.IGNORECASE)
        # Suporta também ordem inversa dos atributos no link
        stylesheets += re.findall(r'<link\b[^>]*href=[\'"]([^\'"]+)[\'"][^>]*rel=[\'"]stylesheet[\'"]', html, re.IGNORECASE)

        buttons = re.findall(r'<button\b[^>]*id=[\'"]([^\'"]+)[\'"]', html, re.IGNORECASE)
        forms = re.findall(r'<form\b[^>]*id=[\'"]([^\'"]+)[\'"]', html, re.IGNORECASE)

        return {
            "has_doctype": "<!doctype" in lower,
            "has_html_tag": "<html" in lower,
            "has_head_tag": "<head" in lower,
            "has_body_tag": "<body" in lower,
            "scripts": scripts,
            "stylesheets": stylesheets,
            "buttons": buttons,
            "forms": forms,
        }

    @classmethod
    def _parse_endpoints(cls, code: str) -> List[str]:
        """Extrai endpoints declarados em código Express / Flask / FastAPI."""
        patterns = [
            r'app\.(?:get|post|put|delete|patch)\([\'"]([^\'"]+)[\'"]',
            r'router\.(?:get|post|put|delete|patch)\([\'"]([^\'"]+)[\'"]',
            r'@app\.(?:get|post|put|delete|patch)\([\'"]([^\'"]+)[\'"]',
        ]
        results = []
        for pat in patterns:
            results.extend(re.findall(pat, code))
        return results

    @classmethod
    def _parse_event_listeners(cls, code: str) -> List[str]:
        """Extrai listeners de eventos registrados em JavaScript."""
        matches = re.findall(r'getElementById\([\'"]([^\'"]+)[\'"]\)\.addEventListener\([\'"]([^\'"]+)[\'"]', code)
        return [f"{elem}:{ev}" for elem, ev in matches]


class DestructiveChangeDetector:
    """Deteta se uma proposta de alteração sobrescreve destrutivamente código existente."""

    THRESHOLD_REPLACEMENT_RATIO = 0.50

    @classmethod
    def evaluate_change_destructiveness(
        cls,
        file_path: str,
        old_content: str,
        new_content: str,
    ) -> Dict[str, Any]:
        basename = os.path.basename(file_path).lower()
        is_sensitive = basename in PreservationAnalyzer.SENSITIVE_FILES

        result = {
            "file": file_path,
            "is_destructive": False,
            "severity": "NORMAL",
            "reason": "",
            "replacement_ratio": 0.0,
        }

        if not old_content or not old_content.strip():
            # Criação de ficheiro novo não é substituição destrutiva
            return result

        old_lines = len(old_content.splitlines())
        new_lines = len(new_content.splitlines())

        # Caso crítico especial: index.html
        if basename == "index.html":
            old_lower = old_content.lower()
            new_lower = new_content.lower()

            had_root = ("<!doctype" in old_lower or "<html" in old_lower or "<body" in old_lower)
            lost_root = had_root and ("<html" not in new_lower and "<body" not in new_lower)

            had_css = "<link" in old_lower and "stylesheet" in old_lower
            lost_css = had_css and ("<link" not in new_lower or "stylesheet" not in new_lower)

            had_js = "<script" in old_lower and "src=" in old_lower
            lost_js = had_js and ("<script" not in new_lower or "src=" not in new_lower)

            if lost_root or lost_css or lost_js:
                reasons = []
                if lost_root:
                    reasons.append("casca HTML (<html>/<body>) foi eliminada")
                if lost_css:
                    reasons.append("ligação para stylesheet CSS foi eliminada")
                if lost_js:
                    reasons.append("ligação para script JS foi eliminada")

                result["is_destructive"] = True
                result["severity"] = "CRITICAL"
                result["reason"] = f"Destruição de estrutura web fundamental em index.html: {', '.join(reasons)}"
                return result

        # Avaliação por proporção de substituição
        if old_lines > 5:
            # Se mais de 50% das linhas foram eliminadas ou substituídas em bloco
            ratio = abs(new_lines - old_lines) / max(old_lines, 1)
            result["replacement_ratio"] = round(ratio, 2)
            if ratio >= cls.THRESHOLD_REPLACEMENT_RATIO and is_sensitive:
                result["is_destructive"] = True
                result["severity"] = "HIGH" if is_sensitive else "MEDIUM"
                result["reason"] = f"Alteração substitui {int(ratio * 100)}% das linhas de ficheiro sensível ({basename})"

        return result
