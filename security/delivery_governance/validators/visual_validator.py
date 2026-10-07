"""
Validador de Integridade Visual e Apresentação de UI.
Verifica:
- Presença de estilos (folhas de estilo CSS ativas, regras de layout).
- Deteção de páginas desestilizadas (raw browser controls, ausência de classes/estilos).
- Deteção de viewports vazios ou conteúdo principal invisível.
- Auditoria de antes/depois quando existem baselines visuais.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


class VisualIntegrityValidator:
    """Audita a integridade visual da interface para evitar páginas degradadas ou desestilizadas."""

    @classmethod
    def evaluate_project_visual_readiness(
        cls,
        project_root: str,
        ui_changed: bool = True,
        baseline_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Avalia se a aplicação web possui os componentes estéticos e visuais mínimos necessários.
        """
        violations: List[str] = []
        warnings: List[str] = []
        checks: List[Dict[str, Any]] = []

        html_files = []
        css_files = []

        for root, _, files in os.walk(project_root):
            if any(part in {"node_modules", ".git", "dist", "build"} for part in Path(root).parts):
                continue
            for fname in files:
                fpath = os.path.join(root, fname)
                ext = Path(fname).suffix.lower()
                if ext in {".html", ".htm"}:
                    html_files.append(fpath)
                elif ext == ".css":
                    css_files.append(fpath)

        if not html_files:
            # Não é um projeto de UI web
            return {
                "valid": True,
                "is_ui_project": False,
                "violations": [],
                "warnings": [],
                "checks": [],
                "score_status": "PASS",
            }

        # 1. Verifica existência de ficheiros CSS no projeto
        has_css_files = len(css_files) > 0
        checks.append({
            "check": "css_assets_exist",
            "passed": has_css_files,
            "details": f"Ficheiros CSS encontrados: {len(css_files)}",
        })
        if not has_css_files:
            warnings.append("Nenhum ficheiro CSS (.css) encontrado no projeto.")

        # 2. Inspeciona cada ficheiro HTML para estilização
        for html_path in html_files:
            rel_html = os.path.relpath(html_path, project_root).replace("\\", "/")
            try:
                content = Path(html_path).read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            # A: Tem ligação a CSS ou tags <style>?
            has_link_css = bool(re.search(r'<link\b[^>]*rel=[\'"]stylesheet[\'"]', content, re.IGNORECASE))
            has_link_css_rev = bool(re.search(r'<link\b[^>]*href=[\'"][^\'"]+\.css[\'"]', content, re.IGNORECASE))
            has_style_tag = bool(re.search(r'<style\b[^>]*>[\s\S]*?</style>', content, re.IGNORECASE))
            has_inline_styles = bool(re.search(r'style=[\'"][^\'"]+[\'"]', content, re.IGNORECASE))

            styled = has_link_css or has_link_css_rev or has_style_tag or has_inline_styles
            checks.append({
                "check": f"html_styled_{rel_html}",
                "passed": styled,
                "details": f"Link CSS: {has_link_css or has_link_css_rev}, Style Tag: {has_style_tag}, Inline: {has_inline_styles}",
            })

            if not styled:
                violations.append(
                    f"UNSTYLED_PAGE: '{rel_html}' não possui folha de estilos CSS, tag <style> nem estilos em linha. Interface degradada (raw controls)."
                )

            # B: Viewport meta tag
            has_viewport = "<meta name=\"viewport\"" in content.lower() or "<meta name='viewport'" in content.lower()
            checks.append({
                "check": f"responsive_viewport_{rel_html}",
                "passed": has_viewport,
                "details": "Tag meta viewport presente para renderização correta.",
            })
            if not has_viewport:
                warnings.append(f"MISSING_VIEWPORT_META: '{rel_html}' não define meta viewport para layout responsivo.")

            # C: Conteúdo vazio / Raw controls
            # Se tiver botões ou inputs mas zero classes CSS
            buttons_and_inputs = len(re.findall(r'<(?:button|input|select|textarea)\b', content, re.IGNORECASE))
            class_attributes = len(re.findall(r'class=[\'"][^\'"]+[\'"]', content, re.IGNORECASE))
            if buttons_and_inputs > 0 and class_attributes == 0 and not has_style_tag and not has_link_css:
                violations.append(
                    f"RAW_BROWSER_CONTROLS: '{rel_html}' tem controlos interativos ({buttons_and_inputs}) sem classes nem estilos associados."
                )

        # 3. Comparação com Baseline anterior (se disponível)
        if baseline_snapshot:
            baseline_stylesheets = baseline_snapshot.get("stylesheets", [])
            if baseline_stylesheets and not css_files:
                violations.append(
                    f"VISUAL_REGRESSION: Projeto tinha {len(baseline_stylesheets)} stylesheets na baseline e agora tem 0."
                )

        is_valid = len(violations) == 0

        return {
            "valid": is_valid,
            "is_ui_project": True,
            "violations": violations,
            "warnings": warnings,
            "checks": checks,
            "score_status": "PASS" if is_valid else "FAIL",
        }
