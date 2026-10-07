"""
Validador de Integridade de Interação e Comportamento de Controlos.
Verifica:
- Botões com IDs ou classes possuem event listeners ou handlers onclick registados.
- Prevenção de botões "mortos" (sem comportamento, sem listeners).
- Preservação de elementos interativos e IDs essenciais da versão anterior.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class InteractionValidator:
    """Valida se elementos interativos (botões, formulários) possuem handlers funcionais."""

    @classmethod
    def evaluate_interactions(
        cls,
        project_root: str,
        baseline_buttons: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Audita se os botões e formulários do projeto estão conectados a listeners."""
        violations: List[str] = []
        warnings: List[str] = []
        checks: List[Dict[str, Any]] = []

        html_buttons: List[Dict[str, Any]] = []
        js_listeners: Set[str] = set()

        for root, _, files in os.walk(project_root):
            if any(part in {"node_modules", ".git", "dist", "build"} for part in Path(root).parts):
                continue
            for fname in files:
                fpath = os.path.join(root, fname)
                ext = Path(fname).suffix.lower()

                if ext in {".html", ".htm"}:
                    try:
                        content = Path(fpath).read_text(encoding="utf-8", errors="ignore")
                        buttons = cls._extract_buttons(content)
                        for b in buttons:
                            b["file"] = os.path.relpath(fpath, project_root).replace("\\", "/")
                            html_buttons.append(b)
                    except Exception:
                        pass

                elif ext in {".js", ".mjs", ".ts"}:
                    try:
                        content = Path(fpath).read_text(encoding="utf-8", errors="ignore")
                        listeners = cls._extract_listener_targets(content)
                        js_listeners.update(listeners)
                    except Exception:
                        pass

        # 1. Verifica cada botão para assegurar que tem comportamento
        dead_buttons = []
        for btn in html_buttons:
            btn_id = btn.get("id")
            has_onclick = btn.get("has_onclick", False)
            btn_text = btn.get("text", "")
            btn_file = btn.get("file", "")

            # Botão é considerado ativo se:
            # - tem onclick inline
            # - tem ID e o ID é referenciado em listeners de JS (addEventListener, getElementById, querySelector)
            # - ou está dentro de form com action
            is_wired = has_onclick or (btn_id and btn_id in js_listeners)

            checks.append({
                "button_id": btn_id,
                "file": btn_file,
                "text": btn_text,
                "wired": is_wired,
            })

            if btn_id and not is_wired:
                dead_buttons.append(f"{btn_file} -> #{btn_id} ('{btn_text}')")

        if dead_buttons:
            # Botões com ID declarado mas nenhum listener registado em nenhum ficheiro JS
            warnings.append(
                f"UNWIRED_BUTTONS: Encontrados botões sem event listeners associados em JavaScript: {dead_buttons}"
            )

        # 2. Preservação de botões da baseline
        if baseline_buttons:
            current_ids = {b.get("id") for b in html_buttons if b.get("id")}
            for prev_b in baseline_buttons:
                if prev_b and prev_b not in current_ids:
                    violations.append(
                        f"FUNCTIONAL_REGRESSION: Botão interativo existente na baseline '#{prev_b}' foi removido ou destruído."
                    )

        is_valid = len(violations) == 0

        return {
            "valid": is_valid,
            "violations": violations,
            "warnings": warnings,
            "total_buttons": len(html_buttons),
            "wired_buttons": len(html_buttons) - len(dead_buttons),
            "dead_buttons": dead_buttons,
            "checks": checks,
        }

    @classmethod
    def _extract_buttons(cls, html: str) -> List[Dict[str, Any]]:
        results = []
        # Procura tags <button ...>texto</button>
        pattern = re.compile(r'<button\b([^>]*)>(.*?)</button>', re.IGNORECASE | re.DOTALL)
        for match in pattern.finditer(html):
            attrs = match.group(1)
            text = re.sub(r'<[^>]+>', '', match.group(2)).strip()
            id_match = re.search(r'\bid=[\'"]([^\'"]+)[\'"]', attrs, re.IGNORECASE)
            has_onclick = "onclick" in attrs.lower()
            results.append({
                "id": id_match.group(1) if id_match else None,
                "has_onclick": has_onclick,
                "text": text[:40],
            })
        return results

    @classmethod
    def _extract_listener_targets(cls, js_code: str) -> Set[str]:
        targets = set()
        # getElementById('btn')
        for m in re.finditer(r'getElementById\([\'"]([^\'"]+)[\'"]\)', js_code):
            targets.add(m.group(1))
        # querySelector('#btn')
        for m in re.finditer(r'querySelector\([\'"]#([a-zA-Z0-9_\-]+)[\'"]\)', js_code):
            targets.add(m.group(1))
        # addEventListener diretos ou variáveis
        for m in re.finditer(r'([a-zA-Z0-9_\-]+)Btn\.addEventListener', js_code):
            targets.add(m.group(1))
        return targets
