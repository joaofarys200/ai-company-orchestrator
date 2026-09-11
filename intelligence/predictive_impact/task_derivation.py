"""
JARVIS OS — Phase 39.2: Predictive Task Reconciliation Engine

Implements deterministic derivation of PredictedTasks from:
- Intent delta operation & directives
- Impacted files & symbols
- System requirements, constraints, and current DAG tasks
- Planning contracts (Implementation, Validation, Architecture, Deprecation)

Guarantees:
- Every PredictedTask has a traceable causal explanation
- Explicit classification: FILE_DRIVEN vs SEMANTIC vs VALIDATION vs ARCHITECTURE vs CONTROL
- Deterministic FILES x TASKS correlation matrix (DIRECT, INDIRECT, DOWNSTREAM, VALIDATION, UNKNOWN)
- Zero synthetic task inflation
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Set, Tuple

from intelligence.predictive_impact.models import (
    ConfidenceClass,
    PredictedFile,
    PredictedSymbol,
    PredictedTask,
    TaskCategory,
    TaskDerivationType,
    TaskFileRelationType,
)


class TaskDerivationEngine:
    """
    Deterministic reconciliation layer that translates Impact Graph & Intent Delta
    into structured, traceable PredictedTasks and correlation matrices.
    """

    @classmethod
    def derive_tasks(
        cls,
        operation: str,
        target_name: str,
        directive_text: str,
        predicted_files: list[PredictedFile],
        predicted_symbols: list[PredictedSymbol],
        current_tasks: list[dict[str, Any]],
        requirements: list[dict[str, Any]],
        constraints: list[dict[str, Any]],
        scope: str = "LOCAL",
    ) -> list[PredictedTask]:
        """
        Derives predicted tasks anchored in standard planning contracts:
        1. ADD_REQUIREMENT / ADD_CONSTRAINT:
           - Coding / Implementation task (FILE_DRIVEN or REQUIREMENT_DRIVEN)
           - Testing / Validation task (VALIDATION_DRIVEN)
        2. MODIFY_REQUIREMENT / REVISE_APPROACH:
           - Adaptation / Coding or Architecture task (DIRECT_FILE_IMPACT or ARCHITECTURE_DRIVEN)
           - Re-validation / Testing task (VALIDATION_DRIVEN)
        3. REMOVE_REQUIREMENT:
           - Code removal / Deprecation task (DIRECT_FILE_IMPACT or REQUIREMENT_DRIVEN)
           - Cleanup / Test & Evidence verification task (VALIDATION_DRIVEN)
        """
        tasks: list[PredictedTask] = []
        op = operation.upper()
        target = target_name.strip()
        directive_lower = directive_text.lower()
        file_paths = [f.file_path for f in predicted_files]
        symbol_names = [s.name for s in predicted_symbols]

        # Determine if directive is architectural
        is_architectural = (
            scope == "ARCHITECTURAL"
            or any(kw in directive_lower for kw in ["arquitetura", "schema", "sqlite", "swarm", "eventos", "migrar"])
        )

        # Determine if directive involves browser UI validation
        needs_browser = any(kw in directive_lower for kw in ["css", "ui", "botões", "painel", "barra", "filtro", "reativo", "frontend"])

        # Prior completed task dependencies if any
        base_deps = [t["id"] for t in current_tasks if t.get("status") == "COMPLETED"][:1]

        # -------------------------------------------------------------
        # 1. ADD_REQUIREMENT / ADD_CONSTRAINT
        # -------------------------------------------------------------
        if op in ("ADD_REQUIREMENT", "ADD_CONSTRAINT"):
            # Task 1: Implementation / Architecture Task
            if is_architectural:
                impl_category = TaskCategory.ARCHITECTURE.value
                impl_derivation = TaskDerivationType.ARCHITECTURE_DRIVEN.value
                impl_owner = "architect"
                impl_title = f"Desenhar e implementar arquitetura para {target}"
                impl_desc = f"Estruturar arquitetura e componentes para: {directive_text}"
            else:
                impl_category = TaskCategory.CODING.value
                impl_derivation = (
                    TaskDerivationType.DIRECT_FILE_IMPACT.value
                    if file_paths
                    else TaskDerivationType.REQUIREMENT_DRIVEN.value
                )
                impl_owner = "coder"
                impl_title = f"Implementar {target}"
                impl_desc = f"Desenvolver componentes e lógica associada à diretiva: {directive_text}"

            impl_task_id = f"ptask_impl_{len(current_tasks) + 1}"
            impl_trace = {
                "requirement": target,
                "impact_scope": scope,
                "directive": directive_text,
                "impacted_files": file_paths,
                "impacted_symbols": symbol_names,
                "rationale": f"Implementação requerida pelo requisito {target}.",
            }

            tasks.append(
                PredictedTask(
                    predicted_task_id=impl_task_id,
                    action="ADD_TASK",
                    title=impl_title,
                    description=impl_desc,
                    source_requirement=target,
                    dependencies=base_deps,
                    predicted_owner=impl_owner,
                    confidence=0.92,
                    status="PREDICTED_ONLY",
                    category=impl_category,
                    derivation_type=impl_derivation,
                    confidence_class=ConfidenceClass.DETERMINISTIC.value if file_paths else ConfidenceClass.INFERRED.value,
                    predicted_files=list(file_paths),
                    impacted_symbols=list(symbol_names),
                    source_requirements=[target],
                    source_constraints=[c.get("id", "") for c in constraints if c.get("id")],
                    derived_from=["INTENT_DELTA", "IMPACT_GRAPH"],
                    reason=f"Implementação associada à diretiva '{directive_text}'",
                    causal_trace=impl_trace,
                )
            )

            # Task 2: Testing / Validation Task
            val_task_id = f"ptask_test_{len(current_tasks) + 2}"
            val_category = TaskCategory.TESTING.value
            val_derivation = TaskDerivationType.VALIDATION_DRIVEN.value
            val_trace = {
                "requirement": target,
                "impact_scope": scope,
                "validation_policy": "Zero False Success: toda alteração requer suite de testes e validação de invariantes.",
                "target_files": file_paths,
                "derived_from_task": impl_task_id,
            }

            tasks.append(
                PredictedTask(
                    predicted_task_id=val_task_id,
                    action="ADD_TASK",
                    title=f"Validar testes para {target}",
                    description=f"Executar suite de testes unitários e de integração para {target}",
                    source_requirement=target,
                    dependencies=[impl_task_id],
                    predicted_owner="test_engineer",
                    confidence=0.90,
                    status="PREDICTED_ONLY",
                    category=val_category,
                    derivation_type=val_derivation,
                    confidence_class=ConfidenceClass.DETERMINISTIC.value,
                    predicted_files=list(file_paths),
                    impacted_symbols=list(symbol_names),
                    source_requirements=[target],
                    derived_from=[impl_task_id, "VALIDATION_POLICY"],
                    reason=f"Validação empírica de testes exigida pelo princípio Zero False Success para {target}",
                    causal_trace=val_trace,
                )
            )

        # -------------------------------------------------------------
        # 2. MODIFY_REQUIREMENT / REVISE_APPROACH
        # -------------------------------------------------------------
        elif op in ("MODIFY_REQUIREMENT", "REVISE_APPROACH"):
            # Task 1: Implementation Adaptation
            adapt_task_id = f"ptask_replan_{len(current_tasks) + 1}"
            adapt_owner = "architect" if is_architectural else "coder"
            adapt_category = TaskCategory.ARCHITECTURE.value if is_architectural else TaskCategory.CODING.value
            adapt_derivation = (
                TaskDerivationType.ARCHITECTURE_DRIVEN.value
                if is_architectural
                else (TaskDerivationType.DIRECT_FILE_IMPACT.value if file_paths else TaskDerivationType.REQUIREMENT_DRIVEN.value)
            )

            adapt_trace = {
                "requirement": target,
                "operation": op,
                "directive": directive_text,
                "impacted_files": file_paths,
                "impacted_symbols": symbol_names,
                "rationale": f"Modificação de abordagem exige adaptação de código/arquitetura para {target}.",
            }

            tasks.append(
                PredictedTask(
                    predicted_task_id=adapt_task_id,
                    action="MODIFY_TASK",
                    title=f"Adaptar abordagem para {target}",
                    description=f"Reconfigurar implementação existente para alinhar com: {directive_text}",
                    source_requirement=target,
                    dependencies=base_deps,
                    predicted_owner=adapt_owner,
                    confidence=0.88,
                    status="PREDICTED_ONLY",
                    category=adapt_category,
                    derivation_type=adapt_derivation,
                    confidence_class=ConfidenceClass.DETERMINISTIC.value if file_paths else ConfidenceClass.INFERRED.value,
                    predicted_files=list(file_paths),
                    impacted_symbols=list(symbol_names),
                    source_requirements=[target],
                    derived_from=["INTENT_DELTA", "EXISTING_IMPLEMENTATION"],
                    reason=f"Adaptação de implementação para {target}: {directive_text}",
                    causal_trace=adapt_trace,
                )
            )

            # Task 2: Re-validation & Regression Test Task (Validation Driven)
            val_task_id = f"ptask_test_reval_{len(current_tasks) + 2}"
            val_trace = {
                "requirement": target,
                "operation": op,
                "validation_policy": "Zero False Success: modificações de requisitos exigem revalidação de testes de regressão.",
                "target_files": file_paths,
                "derived_from_task": adapt_task_id,
            }

            tasks.append(
                PredictedTask(
                    predicted_task_id=val_task_id,
                    action="ADD_TASK",
                    title=f"Revalidar testes de regressão para {target}",
                    description=f"Executar testes de regressão e verificar compatibilidade após alteração de {target}",
                    source_requirement=target,
                    dependencies=[adapt_task_id],
                    predicted_owner="test_engineer",
                    confidence=0.88,
                    status="PREDICTED_ONLY",
                    category=TaskCategory.TESTING.value,
                    derivation_type=TaskDerivationType.VALIDATION_DRIVEN.value,
                    confidence_class=ConfidenceClass.DETERMINISTIC.value,
                    predicted_files=list(file_paths),
                    impacted_symbols=list(symbol_names),
                    source_requirements=[target],
                    derived_from=[adapt_task_id, "VALIDATION_POLICY"],
                    reason=f"Revalidação de regressão necessária para modificação em {target}",
                    causal_trace=val_trace,
                )
            )

        # -------------------------------------------------------------
        # 3. REMOVE_REQUIREMENT
        # -------------------------------------------------------------
        elif op == "REMOVE_REQUIREMENT":
            # Identify any existing tasks in current_tasks that explicitly match target
            matched_existing: list[dict[str, Any]] = []
            target_norm = target.lower().replace("_", "").replace("-", "")
            for t in current_tasks:
                t_title = t.get("title", "").lower().replace("_", "").replace("-", "")
                t_id = t.get("id", "").lower().replace("_", "").replace("-", "")
                if target_norm in t_title or target_norm in t_id:
                    matched_existing.append(t)

            if matched_existing:
                for t in matched_existing:
                    tasks.append(
                        PredictedTask(
                            predicted_task_id=t["id"],
                            action="REMOVE_TASK",
                            title=t.get("title", t["id"]),
                            description=f"Cancelar tarefa associada ao requisito removido: {target}",
                            source_requirement=target,
                            predicted_owner=t.get("owner", "coder"),
                            confidence=0.95,
                            status="PREDICTED_ONLY",
                            category=TaskCategory.CODING.value,
                            derivation_type=TaskDerivationType.REQUIREMENT_DRIVEN.value,
                            confidence_class=ConfidenceClass.DETERMINISTIC.value,
                            predicted_files=list(file_paths),
                            source_requirements=[target],
                            derived_from=["EXISTING_TASK_DAG"],
                            reason=f"Remoção de requisito ativo {target} invalida a tarefa {t['id']}",
                        )
                    )
            else:
                # Requirement has no active task in current DAG, or DAG uses generic IDs (e.g. TSK_01..05).
                # Removing a requirement still deterministically entails:
                # 1. Code removal / deprecation task
                depr_task_id = f"ptask_deprecate_{len(current_tasks) + 1}"
                tasks.append(
                    PredictedTask(
                        predicted_task_id=depr_task_id,
                        action="REMOVE_TASK",
                        title=f"Depreciar e remover código de {target}",
                        description=f"Remover ou desativar endpoints, componentes e dependências do requisito removido: {target}",
                        source_requirement=target,
                        predicted_owner="coder",
                        confidence=0.92,
                        status="PREDICTED_ONLY",
                        category=TaskCategory.CODING.value,
                        derivation_type=TaskDerivationType.DIRECT_FILE_IMPACT.value if file_paths else TaskDerivationType.REQUIREMENT_DRIVEN.value,
                        confidence_class=ConfidenceClass.DETERMINISTIC.value if file_paths else ConfidenceClass.INFERRED.value,
                        predicted_files=list(file_paths),
                        impacted_symbols=list(symbol_names),
                        source_requirements=[target],
                        derived_from=["INTENT_DELTA", "IMPACT_GRAPH"],
                        reason=f"Remoção do requisito {target} requer limpeza do código associado",
                    )
                )

            # Task 2: Test & Evidence Cleanup (Validation Driven)
            cleanup_task_id = f"ptask_cleanup_{len(current_tasks) + 2}"
            tasks.append(
                PredictedTask(
                    predicted_task_id=cleanup_task_id,
                    action="ADD_TASK",
                    title=f"Limpeza de testes e evidências de {target}",
                    description=f"Atualizar suites de teste e invalidar evidências obsoletas ligadas a {target}",
                    source_requirement=target,
                    dependencies=[tasks[0].predicted_task_id] if tasks else [],
                    predicted_owner="test_engineer",
                    confidence=0.90,
                    status="PREDICTED_ONLY",
                    category=TaskCategory.TESTING.value,
                    derivation_type=TaskDerivationType.VALIDATION_DRIVEN.value,
                    confidence_class=ConfidenceClass.DETERMINISTIC.value,
                    predicted_files=list(file_paths),
                    source_requirements=[target],
                    derived_from=["VALIDATION_POLICY"],
                    reason=f"Limpeza de evidências e suites de teste obsoletas para {target}",
                )
            )

        return tasks

    @classmethod
    def build_task_file_matrix(
        cls,
        predicted_tasks: list[PredictedTask],
        predicted_files: list[PredictedFile],
    ) -> dict[str, Any]:
        """
        Builds the FILES x TASKS correlation matrix.
        Classifies each relationship into:
        - DIRECT: Task directly edits or creates the file
        - INDIRECT: File is imported by direct file or downstream dependency
        - DOWNSTREAM: File affected transitively
        - VALIDATION: Validation/Test task referencing the target file
        - UNKNOWN: Unmapped relation
        """
        matrix_rows: list[dict[str, Any]] = []
        file_path_map = {f.file_path: f for f in predicted_files}

        for task in predicted_tasks:
            task_id = task.predicted_task_id
            task_cat = task.category
            task_files = set(task.predicted_files)

            for f_path, pfile in file_path_map.items():
                is_referenced = f_path in task_files

                if not is_referenced:
                    continue

                if task_cat == TaskCategory.TESTING.value or task.derivation_type == TaskDerivationType.VALIDATION_DRIVEN.value:
                    rel_type = TaskFileRelationType.VALIDATION.value
                elif pfile.classification == "DIRECT":
                    rel_type = TaskFileRelationType.DIRECT.value
                elif pfile.classification == "INDIRECT":
                    rel_type = TaskFileRelationType.INDIRECT.value
                elif task.derivation_type == TaskDerivationType.DOWNSTREAM_FILE_IMPACT.value:
                    rel_type = TaskFileRelationType.DOWNSTREAM.value
                else:
                    rel_type = TaskFileRelationType.UNKNOWN.value

                matrix_rows.append({
                    "task_id": task_id,
                    "task_title": task.title,
                    "task_category": task_cat,
                    "file_path": f_path,
                    "file_classification": pfile.classification,
                    "relation_type": rel_type,
                    "derivation_type": task.derivation_type,
                    "confidence": task.confidence,
                })

        return {
            "tasks": [t.to_dict() for t in predicted_tasks],
            "files": [f.to_dict() for f in predicted_files],
            "relationships": matrix_rows,
            "total_relationships": len(matrix_rows),
        }
