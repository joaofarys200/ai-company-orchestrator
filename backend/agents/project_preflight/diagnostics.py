"""
JARVIS OS — Phase 53: Universal Project Preflight & Runtime Failure Auto-Recovery
Runtime Diagnostic Engine: Classifies crash logs and stack traces into structured
RuntimeDiagnostic objects with deterministic symbol extraction and suggested fixes.
"""

from __future__ import annotations

import os
import re
from typing import List, Optional

from agents.project_preflight.models import (
    DiagnosticErrorClass,
    RuntimeDiagnostic,
    compute_deterministic_hash,
)


class RuntimeDiagnosticEngine:
    """
    Parses process crash logs and standard error streams into deterministic diagnostic objects.
    """

    def diagnose_crash(
        self, logs: List[str] | str, root_dir: Optional[str] = None
    ) -> Optional[RuntimeDiagnostic]:
        if isinstance(logs, list):
            text = "\n".join(logs)
            raw_lines = logs
        else:
            text = logs
            raw_lines = text.splitlines()

        if not text.strip():
            return None

        # 1. ReferenceError (JavaScript)
        ref_match = re.search(r'ReferenceError:\s*(\w+)\s*is not defined', text)
        if ref_match:
            symbol = ref_match.group(1)
            file_path, line_num = self._extract_file_and_line(text, root_dir)
            evidence = [l for l in raw_lines if "ReferenceError" in l or (file_path and os.path.basename(file_path) in l)]
            diag_id = compute_deterministic_hash({"err": "ref", "sym": symbol, "f": file_path, "l": line_num}, prefix="diag_ref_")

            suggested = f"Adicione a declaração ou importação de '{symbol}' antes do uso."
            if symbol == "app":
                suggested = "Instancie o app Express: const express = require('express'); const app = express();"
            elif symbol == "axios":
                suggested = "Importe o axios: const axios = require('axios');"

            return RuntimeDiagnostic(
                diagnostic_id=diag_id,
                error_class=DiagnosticErrorClass.REFERENCE_ERROR,
                message=f"ReferenceError: {symbol} is not defined",
                file_path=file_path,
                line=line_num,
                symbol=symbol,
                probable_cause=f"O símbolo '{symbol}' foi invocado ou referenciado sem declaração prévia ou require no escopo atual.",
                evidence=evidence[:4],
                confidence=0.95,
                suggested_fix=suggested,
            )

        # 2. Cannot find module (Node.js)
        mod_match = re.search(r"Cannot find module ['\"]([^'\"]+)['\"]", text)
        if mod_match:
            module_name = mod_match.group(1)
            file_path, line_num = self._extract_file_and_line(text, root_dir)
            evidence = [l for l in raw_lines if "Cannot find module" in l or (file_path and os.path.basename(file_path) in l)]
            diag_id = compute_deterministic_hash({"err": "mod", "sym": module_name, "f": file_path}, prefix="diag_mod_")

            return RuntimeDiagnostic(
                diagnostic_id=diag_id,
                error_class=DiagnosticErrorClass.MODULE_NOT_FOUND,
                message=f"Cannot find module '{module_name}'",
                file_path=file_path,
                line=line_num,
                symbol=module_name,
                probable_cause=f"O módulo ou pacote '{module_name}' foi importado mas não está instalado em node_modules nem é relativo.",
                evidence=evidence[:4],
                confidence=0.92,
                suggested_fix=f"Execute 'npm install {module_name}' ou declare '{module_name}' nas dependências do package.json.",
            )

        # 3. NameError (Python)
        name_match = re.search(r"NameError:\s*name ['\"](\w+)['\"] is not defined", text)
        if name_match:
            symbol = name_match.group(1)
            file_path, line_num = self._extract_python_file_and_line(text)
            evidence = [l for l in raw_lines if "NameError" in l]
            diag_id = compute_deterministic_hash({"err": "name", "sym": symbol, "f": file_path, "l": line_num}, prefix="diag_name_")

            return RuntimeDiagnostic(
                diagnostic_id=diag_id,
                error_class=DiagnosticErrorClass.NAME_ERROR,
                message=f"NameError: name '{symbol}' is not defined",
                file_path=file_path,
                line=line_num,
                symbol=symbol,
                probable_cause=f"A variável ou função '{symbol}' foi utilizada sem definição ou import prévio no script Python.",
                evidence=evidence[:4],
                confidence=0.95,
                suggested_fix=f"Importe ou defina '{symbol}' antes da utilização.",
            )

        # 4. ModuleNotFoundError (Python)
        py_mod_match = re.search(r"ModuleNotFoundError:\s*No module named ['\"]([^'\"]+)['\"]", text)
        if py_mod_match:
            mod_name = py_mod_match.group(1)
            file_path, line_num = self._extract_python_file_and_line(text)
            evidence = [l for l in raw_lines if "ModuleNotFoundError" in l]
            diag_id = compute_deterministic_hash({"err": "pymod", "sym": mod_name}, prefix="diag_pymod_")

            return RuntimeDiagnostic(
                diagnostic_id=diag_id,
                error_class=DiagnosticErrorClass.IMPORT_ERROR,
                message=f"ModuleNotFoundError: No module named '{mod_name}'",
                file_path=file_path,
                line=line_num,
                symbol=mod_name,
                probable_cause=f"O pacote Python '{mod_name}' não está instalado no ambiente virtual.",
                evidence=evidence[:4],
                confidence=0.92,
                suggested_fix=f"Execute 'pip install {mod_name}' ou adicione '{mod_name}' ao requirements.txt.",
            )

        # 5. EADDRINUSE Port conflict
        port_match = re.search(r'EADDRINUSE.*:+\s*(\d+)', text)
        if port_match:
            port_num = int(port_match.group(1))
            diag_id = compute_deterministic_hash({"err": "port", "p": port_num}, prefix="diag_port_")
            return RuntimeDiagnostic(
                diagnostic_id=diag_id,
                error_class=DiagnosticErrorClass.PORT_CONFLICT,
                message=f"listen EADDRINUSE: address already in use ::: {port_num}",
                symbol=str(port_num),
                probable_cause=f"A porta {port_num} já está em uso por outro processo em execução.",
                evidence=[l for l in raw_lines if "EADDRINUSE" in l],
                confidence=0.98,
                suggested_fix=f"Encerre o processo ativo na porta {port_num} ou configure uma porta alternativa.",
            )

        # 6. SyntaxError
        syntax_match = re.search(r'SyntaxError:\s*(.+)', text)
        if syntax_match:
            syn_msg = syntax_match.group(1).strip()
            file_path, line_num = self._extract_file_and_line(text, root_dir)
            diag_id = compute_deterministic_hash({"err": "syn", "msg": syn_msg, "f": file_path, "l": line_num}, prefix="diag_syn_")
            return RuntimeDiagnostic(
                diagnostic_id=diag_id,
                error_class=DiagnosticErrorClass.SYNTAX_ERROR,
                message=f"SyntaxError: {syn_msg}",
                file_path=file_path,
                line=line_num,
                probable_cause="Erro de sintaxe encontrado durante a avaliação do código.",
                evidence=[l for l in raw_lines if "SyntaxError" in l],
                confidence=0.99,
                suggested_fix="Corrija o erro de sintaxe na linha indicada.",
            )

        return None

    def _extract_file_and_line(
        self, text: str, root_dir: Optional[str] = None
    ) -> tuple[Optional[str], Optional[int]]:
        # Matches: C:\...\app.js:79:1 or /path/to/app.js:79
        m = re.search(r'([A-Za-z]:\\[^:\n\r]+\.js|/[^:\n\r]+\.js):(\d+)', text)
        if m:
            return m.group(1), int(m.group(2))
        # Matches: at Object.<anonymous> (app.js:79:1)
        m2 = re.search(r'\(([^:\n\r]+\.js):(\d+):(\d+)\)', text)
        if m2:
            return m2.group(1), int(m2.group(2))
        return None, None

    def _extract_python_file_and_line(self, text: str) -> tuple[Optional[str], Optional[int]]:
        # Matches: File "app.py", line 42, in <module>
        m = re.search(r'File "([^"]+\.py)", line (\d+)', text)
        if m:
            return m.group(1), int(m.group(2))
        return None, None
