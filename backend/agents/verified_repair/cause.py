"""
JARVIS OS — Phase 54: Root Cause Hypothesis Engine
Derives evidence-backed root cause hypotheses from runtime diagnostics, stack traces, and static code context.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from agents.project_preflight.models import DiagnosticErrorClass, RuntimeDiagnostic
from agents.verified_repair.models import (
    RootCauseCategory,
    RootCauseHypothesis,
    compute_deterministic_hash,
)


class RootCauseEngine:
    """
    Evidence-backed root cause diagnosis engine.
    Ensures that no hypothesis is emitted without concrete textual, lexical, or environmental evidence.
    """

    def analyze_failure(
        self,
        diagnostic: Optional[RuntimeDiagnostic] = None,
        raw_log: str = "",
        workspace_dir: str = "",
        project_id: str = "",
    ) -> RootCauseHypothesis:
        """Derives a primary RootCauseHypothesis with supporting and contradicting observations."""
        failure_id = diagnostic.diagnostic_id if diagnostic else compute_deterministic_hash(raw_log, prefix="fail_")

        # 1. Evaluate from structured RuntimeDiagnostic if available
        if diagnostic:
            return self._derive_from_diagnostic(diagnostic, workspace_dir, failure_id)

        # 2. Evaluate from raw log
        return self._derive_from_raw_log(raw_log, workspace_dir, failure_id)

    def _derive_from_diagnostic(
        self,
        diag: RuntimeDiagnostic,
        workspace_dir: str,
        failure_id: str,
    ) -> RootCauseHypothesis:
        category = RootCauseCategory.UNKNOWN
        evidence = f"Diagnóstico estruturado: {diag.error_class.value} no símbolo '{diag.symbol}'"
        supporting: List[str] = [f"Linha {diag.line}: {diag.message}"]
        contradicting: List[str] = []
        locations: List[str] = []

        if diag.file_path:
            loc = f"{diag.file_path}:{diag.line}" if diag.line else diag.file_path
            locations.append(loc)

        if diag.error_class == DiagnosticErrorClass.REFERENCE_ERROR:
            # Check if symbol is an uninstantiated framework object like 'app'
            if diag.symbol == "app":
                category = RootCauseCategory.RUNTIME_SCOPE_ERROR
                evidence = "O identificador 'app' foi invocado sem instanciação ou importação prévia de framework HTTP (ex: Express)."
                supporting.append("Chamada de método de rota detetada sem declaração do objeto 'app'.")
                predicted_effect = "Declarar ou instanciar 'app = express()' resolverá o ReferenceError."
            else:
                category = RootCauseCategory.MISSING_SYMBOL
                evidence = f"O símbolo '{diag.symbol}' foi referenciado mas não está definido no escopo local ou global."
                predicted_effect = f"Declarar ou importar '{diag.symbol}' resolverá o erro de escopo."

        elif diag.error_class in (DiagnosticErrorClass.MODULE_NOT_FOUND, DiagnosticErrorClass.IMPORT_ERROR):
            category = RootCauseCategory.MISSING_DEPENDENCY
            evidence = f"O módulo '{diag.symbol}' requerido em runtime não foi encontrado nas dependências ou caminhos de resolução."
            supporting.append(f"Módulo '{diag.symbol}' ausente em node_modules ou venv.")
            predicted_effect = f"Adicionar '{diag.symbol}' ao manifesto ou corrigir o caminho de importação resolverá a falha."

        elif diag.error_class == DiagnosticErrorClass.PORT_CONFLICT:
            category = RootCauseCategory.PORT_CONFLICT
            evidence = f"Conflito de socket de rede: a porta {diag.symbol} já está vinculada (EADDRINUSE)."
            supporting.append(f"Porta {diag.symbol} ocupada por outro processo.")
            predicted_effect = f"Alterar a porta do servidor para uma porta livre ou liberar a porta {diag.symbol} resolverá o conflito."

        elif diag.error_class == DiagnosticErrorClass.SYNTAX_ERROR:
            category = RootCauseCategory.TYPE_ERROR
            evidence = f"Erro de sintaxe estática detetado: {diag.message}"
            supporting.append(f"Ficheiro {diag.file_path} falhou na verificação de sintaxe.")
            predicted_effect = "Corrigir a construção de sintaxe permitirá a compilação do ficheiro."

        else:
            category = RootCauseCategory.STARTUP_FAILURE
            evidence = f"Processo encerrou inesperadamente: {diag.message}"
            predicted_effect = "Identificar e retificar a causa do encerramento precoce."

        # Verify source code on disk if accessible to check contradicting observations
        if diag.file_path and workspace_dir:
            full_path = os.path.join(workspace_dir, diag.file_path) if not os.path.isabs(diag.file_path) else diag.file_path
            if os.path.exists(full_path):
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    if diag.symbol and f"const {diag.symbol}" in content:
                        contradicting.append(f"O ficheiro contém declaração de 'const {diag.symbol}', possível erro de hoisting ou escopo aninhado.")
                except Exception:
                    pass

        cause_id = compute_deterministic_hash(
            {"fail": failure_id, "cat": category.value, "sym": diag.symbol, "loc": locations},
            prefix="cause_",
        )

        confidence = 0.95 if not contradicting else 0.70

        return RootCauseHypothesis(
            cause_id=cause_id,
            failure_id=failure_id,
            category=category,
            evidence=evidence,
            source_locations=locations,
            confidence=confidence,
            supporting_observations=supporting,
            contradicting_observations=contradicting,
            predicted_effect=predicted_effect if "predicted_effect" in locals() else "Resolver o problema estabilizará a execução.",
        )

    def _derive_from_raw_log(
        self,
        raw_log: str,
        workspace_dir: str,
        failure_id: str,
    ) -> RootCauseHypothesis:
        # Fallback raw log parser
        if "ReferenceError: app is not defined" in raw_log:
            category = RootCauseCategory.RUNTIME_SCOPE_ERROR
            evidence = "Log de crash contém ReferenceError explícito para o símbolo 'app'."
            supporting = ["ReferenceError detetado no stack trace."]
            locations = ["app.js:1"]
            predicted = "Instanciar Express e declarar 'app' resolverá a falha."
            conf = 0.95
        elif "Cannot find module" in raw_log:
            mod_match = re.search(r"Cannot find module ['\"]([^'\"]+)['\"]", raw_log)
            mod = mod_match.group(1) if mod_match else "unknown"
            category = RootCauseCategory.MISSING_DEPENDENCY
            evidence = f"Dependência '{mod}' ausente no ambiente de execução."
            supporting = [f"Cannot find module '{mod}'."]
            locations = []
            predicted = f"Instalar ou declarar '{mod}' resolverá a dependência."
            conf = 0.90
        elif "EADDRINUSE" in raw_log:
            category = RootCauseCategory.PORT_CONFLICT
            evidence = "A porta solicitada já está em uso por outro processo."
            supporting = ["EADDRINUSE presente no log de arranque."]
            locations = []
            predicted = "Utilizar uma porta livre resolverá a falha de bind."
            conf = 0.95
        else:
            category = RootCauseCategory.UNKNOWN
            evidence = "Não foram encontrados padrões de erro conhecidos no log bruto."
            supporting = []
            locations = []
            predicted = "Inconclusivo; requer telemetria adicional."
            conf = 0.30

        cause_id = compute_deterministic_hash(
            {"fail": failure_id, "cat": category.value, "log_snippet": raw_log[:100]},
            prefix="cause_raw_",
        )

        return RootCauseHypothesis(
            cause_id=cause_id,
            failure_id=failure_id,
            category=category,
            evidence=evidence,
            source_locations=locations,
            confidence=conf,
            supporting_observations=supporting,
            contradicting_observations=[],
            predicted_effect=predicted,
        )
