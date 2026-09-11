"""
JARVIS OS — Phase 39: Impact Graph Engine

Traverses the multidimensional project and mission graph:
Requirement -> Task -> File -> Symbol -> Module -> Test -> Evidence

Distinguishes:
- DIRECT_IMPACT: Directly targeted by intent or explicit requirement
- INDIRECT_IMPACT: Static dependencies, imports, and caller/callee relations
- DOWNSTREAM_IMPACT: Validation tests, evidence ledger artifacts, checkpoints
- UNCERTAIN_IMPACT: Unresolved dynamic references or loose coupling
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from intelligence.predictive_impact.models import (
    FileImpactClassification,
    PredictedEvidenceImpact,
    PredictedFile,
    PredictedSymbol,
    PredictedTask,
)


class ImpactGraphEngine:
    """
    Traverses repository relationships and mission state to predict affected components.
    Does not mutate anything in the repository or database.
    """

    def __init__(self, workspace_root: Optional[str] = None) -> None:
        self.workspace_root = workspace_root or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self._ts_service = None

    @property
    def ts_service(self):
        if not hasattr(self, "_ts_service") or self._ts_service is None:
            from intelligence.typescript_dependency import TypeScriptDependencyService
            self._ts_service = TypeScriptDependencyService(self.workspace_root)
            self._ts_service.index_workspace(force_reparse=True)
        return self._ts_service

    def analyze_delta_impact(
        self,
        operation: str,
        target_name: str,
        directive_text: str,
        current_requirements: list[dict[str, Any]],
        current_tasks: list[dict[str, Any]],
        current_evidence: list[dict[str, Any]],
        assumptions: list[str],
    ) -> dict[str, Any]:
        """
        Traverses the graph starting from the user's intent delta.
        Returns:
            - predicted_files: list[PredictedFile]
            - predicted_symbols: list[PredictedSymbol]
            - predicted_tasks: list[PredictedTask]
            - predicted_evidence: list[PredictedEvidenceImpact]
            - predicted_tests: list[dict]
            - causal_chains: list[dict]
            - uncertainties: list[str]
        """
        text_lower = (directive_text + " " + target_name).lower()
        
        # 1. Domain detection using regex word boundaries for short words
        is_auth = any(re.search(rf"\b{re.escape(k)}\b", text_lower) for k in ["auth", "jwt", "login", "token", "password", "seguranca", "segurança"])
        is_search = any(k in text_lower for k in ["search", "busca", "pesquisa", "filtro"])
        is_export = any(k in text_lower for k in ["export", "csv", "pdf", "relatorio", "relatório", "download"])
        is_api = any(re.search(rf"\b{re.escape(k)}\b", text_lower) for k in ["api", "endpoint", "rest", "graphql", "backend", "servidor", "rota"])
        is_db = any(re.search(rf"\b{re.escape(k)}\b", text_lower) for k in ["db", "database", "sqlite", "postgres", "persistencia", "persistência", "sql"])
        is_ui = any(re.search(rf"\b{re.escape(k)}\b", text_lower) for k in [
            "ui", "frontend", "react", "css", "visual", "tela", "interface", "component",
            "estilo", "estilos", "tema", "theme", "layout", "tipografia", "outfit", "botão", "botões", "borda", "bordas"
        ])

        predicted_files: list[PredictedFile] = []
        predicted_symbols: list[PredictedSymbol] = []
        causal_chains: list[dict[str, Any]] = []
        uncertainties: list[str] = []

        # Graph traversal: Domain -> Files
        if is_auth:
            predicted_files.append(
                PredictedFile(
                    file_path="backend/security/auth.py",
                    classification=FileImpactClassification.DIRECT.value,
                    reason="Implementação de autenticação JWT e validação de credenciais",
                    estimated_change_type="CREATE" if not os.path.exists(os.path.join(self.workspace_root, "backend/security/auth.py")) else "MODIFY",
                    related_symbol="authenticate_user",
                    confidence=0.92,
                )
            )
            predicted_files.append(
                PredictedFile(
                    file_path="backend/api.py",
                    classification=FileImpactClassification.INDIRECT.value,
                    reason="Injeção de middleware de autenticação nas rotas protegidas",
                    estimated_change_type="MODIFY",
                    related_symbol="auth_middleware",
                    confidence=0.88,
                )
            )
            predicted_files.append(
                PredictedFile(
                    file_path="frontend/src/context/AuthContext.tsx",
                    classification=FileImpactClassification.POSSIBLE.value,
                    reason="Gestão de token de sessão e estado de autenticação no frontend",
                    estimated_change_type="CREATE",
                    confidence=0.75,
                )
            )
            causal_chains.append({
                "origin": "Directive 'auth/jwt'",
                "path": "Directive -> Security Module (auth.py) -> API Endpoints (api.py) -> Client AuthContext",
                "impact_type": "CROSS_MODULE",
            })
        elif is_export and ("remove" in text_lower or operation == "REMOVE_REQUIREMENT"):
            predicted_files.append(
                PredictedFile(
                    file_path="frontend/src/features/export/ExportPanel.tsx",
                    classification=FileImpactClassification.DIRECT.value,
                    reason="Remoção do painel de exportação CSV da interface",
                    estimated_change_type="DELETE",
                    confidence=0.95,
                )
            )
            predicted_files.append(
                PredictedFile(
                    file_path="backend/export_service.py",
                    classification=FileImpactClassification.INDIRECT.value,
                    reason="Desativação de endpoints e serializadores de exportação",
                    estimated_change_type="MODIFY",
                    confidence=0.85,
                )
            )
            causal_chains.append({
                "origin": "Directive 'remove export'",
                "path": "Directive -> UI Component Deprecation -> Backend Service Cleanup",
                "impact_type": "CROSS_MODULE",
            })
        elif is_ui:
            predicted_files.append(
                PredictedFile(
                    file_path="frontend/src/App.tsx",
                    classification=FileImpactClassification.DIRECT.value,
                    reason="Atualização de layout ou inclusão de componente React no core da aplicação",
                    estimated_change_type="MODIFY",
                    confidence=0.90,
                )
            )
            predicted_files.append(
                PredictedFile(
                    file_path="frontend/src/index.css",
                    classification=FileImpactClassification.INDIRECT.value,
                    reason="Ajuste de estilos e tokens de design",
                    estimated_change_type="MODIFY",
                    confidence=0.80,
                )
            )
            causal_chains.append({
                "origin": "Directive 'UI / React'",
                "path": "Directive -> Main App View -> Stylesheet / Design System",
                "impact_type": "LOCAL",
            })
        elif is_search:
            predicted_files.append(
                PredictedFile(
                    file_path="frontend/src/features/search/SearchBar.tsx",
                    classification=FileImpactClassification.DIRECT.value,
                    reason="Componente de entrada e filtragem de pesquisa em tempo real",
                    estimated_change_type="CREATE",
                    confidence=0.92,
                )
            )
            predicted_files.append(
                PredictedFile(
                    file_path="backend/search_service.py",
                    classification=FileImpactClassification.INDIRECT.value,
                    reason="Query builder e indexador para pesquisa de utilizadores/entidades",
                    estimated_change_type="CREATE",
                    confidence=0.85,
                )
            )
            causal_chains.append({
                "origin": "Directive 'search'",
                "path": "Directive -> Search UI Component -> Backend Query Builder",
                "impact_type": "CROSS_MODULE",
            })
        else:
            # Default fallback for arbitrary requirement
            predicted_files.append(
                PredictedFile(
                    file_path="agents/domain_logic.py",
                    classification=FileImpactClassification.DIRECT.value,
                    reason=f"Implementação das regras de negócio associadas a: {target_name}",
                    estimated_change_type="MODIFY",
                    confidence=0.75,
                )
            )
            uncertainties.append(
                f"O grafo estático não determinou ficheiro unívoco para '{target_name}'. Mapeado heuristicamente para domain_logic.py."
            )
            causal_chains.append({
                "origin": f"Directive '{target_name}'",
                "path": "Directive -> Domain Business Logic",
                "impact_type": "LOCAL",
            })

        # 1.5 TypeScript Dependency Graph Traversal & Symbol Enrichment (Phase 39.1)
        try:
            from intelligence.typescript_dependency import TypeScriptDependencyService
            if not hasattr(self, "_ts_service") or self._ts_service is None:
                self._ts_service = TypeScriptDependencyService(self.workspace_root)
                self._ts_service.index_workspace()

            ts_graph = self._ts_service.graph
            initial_ts_files = [pf.file_path for pf in predicted_files if pf.file_path.endswith((".ts", ".tsx", ".js", ".jsx"))]
            seen_file_paths = {pf.file_path for pf in predicted_files}

            for ts_file in initial_ts_files:
                norm_ts = ts_file.replace(os.sep, "/")
                # A. Extract symbols from the file
                for sym in ts_graph.file_symbols.get(norm_ts, []):
                    if sym.is_exported:
                        predicted_symbols.append(
                            PredictedSymbol(
                                name=sym.name,
                                file_path=norm_ts,
                                symbol_type=sym.symbol_type.value if hasattr(sym.symbol_type, "value") else str(sym.symbol_type),
                                change_nature="MODIFY",
                                reason=f"Símbolo exportado em {norm_ts}",
                            )
                        )

                is_root_file = norm_ts.endswith(("App.tsx", "main.tsx"))

                # B. Forward dependencies: if barrel or explicitly referenced subcomponent
                is_barrel = norm_ts.endswith(("index.ts", "index.tsx"))
                if is_barrel:
                    forward_deps = ts_graph.get_forward_dependencies(norm_ts)
                    for fwd in sorted(forward_deps):
                        if fwd not in seen_file_paths and os.path.exists(os.path.join(self.workspace_root, fwd)):
                            seen_file_paths.add(fwd)
                            predicted_files.append(
                                PredictedFile(
                                    file_path=fwd,
                                    classification=FileImpactClassification.INDIRECT.value,
                                    reason=f"Módulo exportado pelo barrel {norm_ts}",
                                    estimated_change_type="MODIFY",
                                    confidence=0.88,
                                )
                            )
                            causal_chains.append({
                                "origin": norm_ts,
                                "path": f"{norm_ts} -> {fwd}",
                                "impact_type": "INDIRECT",
                            })

                # C. Reverse dependencies (consumers)
                # If a subcomponent, utility, or context is modified/removed, its consumers need updates
                if not is_root_file:
                    rev_deps = ts_graph.get_reverse_dependencies(norm_ts)
                    for rev in sorted(rev_deps):
                        if rev not in seen_file_paths and os.path.exists(os.path.join(self.workspace_root, rev)):
                            if len(seen_file_paths) < 8:
                                seen_file_paths.add(rev)
                                predicted_files.append(
                                    PredictedFile(
                                        file_path=rev,
                                        classification=FileImpactClassification.POSSIBLE.value,
                                        reason=f"Consumidor frontend que importa {norm_ts}",
                                        estimated_change_type="MODIFY",
                                        confidence=0.82,
                                    )
                                )
                                causal_chains.append({
                                    "origin": norm_ts,
                                    "path": f"{rev} (consumer) <- {norm_ts}",
                                    "impact_type": "DOWNSTREAM",
                                })

                # D. Check for dynamic/uncertain dependencies
                for unres in ts_graph.unresolved_dependencies:
                    if unres.source == norm_ts:
                        uncertainties.append(
                            f"Dependência dinâmica não resolvida em {norm_ts}: '{unres.target}' (UNCERTAIN)"
                        )
        except Exception as e:
            uncertainties.append(f"TS graph enrichment fallback: {e}")

        # 2. Predicted Tasks generation
        predicted_tasks: list[PredictedTask] = []
        if operation in ("ADD_REQUIREMENT", "ADD_CONSTRAINT"):
            predicted_tasks.append(
                PredictedTask(
                    predicted_task_id=f"ptask_impl_{len(current_tasks) + 1}",
                    action="ADD_TASK",
                    title=f"Implementar {target_name}",
                    description=f"Desenvolver componentes e lógica associada à diretiva: {directive_text}",
                    source_requirement=target_name,
                    dependencies=[t["id"] for t in current_tasks if t.get("status") == "COMPLETED"][:1],
                    predicted_owner="coder",
                    confidence=0.90,
                )
            )
            predicted_tasks.append(
                PredictedTask(
                    predicted_task_id=f"ptask_test_{len(current_tasks) + 2}",
                    action="ADD_TASK",
                    title=f"Validar testes para {target_name}",
                    description=f"Executar suite de testes unitários e de integração para {target_name}",
                    source_requirement=target_name,
                    dependencies=[f"ptask_impl_{len(current_tasks) + 1}"],
                    predicted_owner="test_engineer",
                    confidence=0.88,
                )
            )
        elif operation == "REMOVE_REQUIREMENT":
            # Identify existing tasks that reference target
            for t in current_tasks:
                if target_name.lower() in t.get("title", "").lower() or target_name.lower() in t.get("id", "").lower():
                    predicted_tasks.append(
                        PredictedTask(
                            predicted_task_id=t["id"],
                            action="REMOVE_TASK",
                            title=t.get("title", t["id"]),
                            description=f"Cancelar tarefa associada ao requisito removido: {target_name}",
                            source_requirement=target_name,
                            predicted_owner=t.get("owner", "coder"),
                            confidence=0.95,
                        )
                    )
        elif operation in ("MODIFY_REQUIREMENT", "REVISE_APPROACH"):
            predicted_tasks.append(
                PredictedTask(
                    predicted_task_id=f"ptask_replan_{len(current_tasks) + 1}",
                    action="MODIFY_TASK",
                    title=f"Adaptar abordagem para {target_name}",
                    description=f"Reconfigurar implementação existente para alinhar com: {directive_text}",
                    source_requirement=target_name,
                    predicted_owner="architect",
                    confidence=0.85,
                )
            )

        # 3. Predicted Tests & Evidence Impact (Zero False Success)
        predicted_tests: list[dict[str, Any]] = []
        predicted_evidence: list[PredictedEvidenceImpact] = []

        # Predict tests
        for pf in predicted_files:
            test_path = f"tests/test_{os.path.splitext(os.path.basename(pf.file_path))[0]}.py"
            predicted_tests.append({
                "test_file": test_path,
                "target_module": pf.file_path,
                "test_type": "unit_and_regression",
                "reason": f"Verificação de invariantes de {pf.file_path}",
            })

        # Predict evidence impact
        for ev in current_evidence:
            req_id = ev.get("requirement_id", "")
            if target_name.lower() in req_id.lower() or operation == "REMOVE_REQUIREMENT":
                predicted_evidence.append(
                    PredictedEvidenceImpact(
                        evidence_id=ev.get("evidence_id", ev.get("id", "ev_unknown")),
                        requirement_id=req_id,
                        title=ev.get("title", ev.get("description", "Evidence Item")),
                        predicted_status="REQUIRES_REVALIDATION" if operation != "REMOVE_REQUIREMENT" else "SUPERSEDED",
                        reason=f"Requisito {req_id} afetado pela diretiva '{directive_text}'. Princípio Zero False Success exige revalidação.",
                    )
                )

        return {
            "predicted_files": [f.to_dict() for f in predicted_files],
            "predicted_symbols": [s.to_dict() for s in predicted_symbols],
            "predicted_tasks": [t.to_dict() for t in predicted_tasks],
            "predicted_evidence": [e.to_dict() for e in predicted_evidence],
            "predicted_tests": predicted_tests,
            "causal_chains": causal_chains,
            "uncertainties": uncertainties,
        }
