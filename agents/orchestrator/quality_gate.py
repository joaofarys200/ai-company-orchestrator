from __future__ import annotations

from agents.orchestrator.action_repair import extract_requested_file_paths
from agents.orchestrator.task_requirements import effective_requirements, evidence_contains, normalize_text
from agents.orchestrator.task_state import TaskPlan, TaskState

def artifacts_satisfy_minimum(prompt: str, state: TaskState, include_execution: bool = True) -> bool:
    requirements = effective_requirements(prompt, state)
    if not requirements.requires_artifacts:
        return True
    files = [str(item).replace("\\", "/").lower() for item in state.files_created]
    if not files:
        return False
    requested_paths = [path.lower() for path in extract_requested_file_paths(prompt)]
    if requested_paths:
        return all(path in files for path in requested_paths)
    missing = missing_requirement_evidence(prompt, state, include_quality=False)
    if not include_execution:
        missing = [
            item for item in missing
            if item not in {"preview/sandbox validado", "validacao executada"}
        ]
    return not missing

def artifact_content_blob(state: TaskState, proposed_content: str | None = None) -> str:
    parts = [*state.files_created, *state.artifact_contents.values()]
    if proposed_content:
        parts.append(proposed_content)
    return normalize_text(" ".join(str(part) for part in parts if part))

def file_contributes_to_requirements(filename: str, content: str, state: TaskState) -> bool:
    filename_text = normalize_text(filename)
    content_text = normalize_text(content)
    combined = f"{filename_text} {content_text}"
    requirements = effective_requirements("", state)
    if requirements.requires_frontend and (
        filename_text.endswith((".html", ".css", ".jsx", ".tsx", ".vue", ".svelte"))
        or "/public/" in filename_text
        or "/frontend/" in filename_text
        or evidence_contains(content_text, ["<html", "<body", "<main", "document.", "localstorage", "onclick", "queryselector", "addeventlistener"])
    ):
        return True
    if requirements.requires_backend and evidence_contains(combined, ["api", "server", "servidor", "route", "rota", "endpoint", "express", "fastapi", "flask", "http"]):
        return True
    if requirements.requires_storage and evidence_contains(combined, ["localstorage", "indexeddb", "sqlite", "json", "database", "persist", "armazenamento"]):
        return True
    if requirements.requires_auth and evidence_contains(combined, ["login", "auth", "autenticacao", "sessao", "password", "utilizador"]):
        return True
    if requirements.requires_crud and evidence_contains(combined, ["create", "read", "update", "delete", "criar", "listar", "editar", "apagar", "remover", "crud"]):
        return True
    if requirements.requires_search and evidence_contains(combined, ["search", "pesquisa", "filter", "filtro", "filtrar"]):
        return True
    if requirements.requires_dashboard and evidence_contains(combined, ["dashboard"]):
        return True
    return bool(content.strip()) and not state.requirements.requires_artifacts

def missing_requirement_evidence(prompt: str, state: TaskState, include_quality: bool = True) -> list[str]:
    requirements = effective_requirements(prompt, state)
    blob = artifact_content_blob(state)
    created_files = [str(item).replace("\\", "/").lower() for item in state.files_created]
    frontend_file_evidence = any(
        path.endswith((".html", ".css", ".jsx", ".tsx", ".vue", ".svelte")) or "/public/" in path or "/frontend/" in path
        for path in created_files
    )
    missing: list[str] = []
    if requirements.requires_artifacts and not state.files_created:
        missing.append("artefactos criados")
    if requirements.requires_frontend and not (
        frontend_file_evidence
        or evidence_contains(blob, ["<html", "<body", "<main", "document.", "localstorage", "onclick", "queryselector", "addeventlistener"])
    ):
        missing.append("frontend/UI")
    if requirements.requires_backend and not evidence_contains(blob, ["api", "server", "servidor", "route", "rota", "endpoint", "express", "fastapi", "flask", "http"]):
        missing.append("backend/API")
    if requirements.requires_storage and not evidence_contains(blob, ["localstorage", "indexeddb", "sqlite", "json", "database", "persist", "armazenamento"]):
        missing.append("storage/persistencia")
    if requirements.requires_auth and not evidence_contains(blob, ["login", "auth", "autenticacao", "sessao", "password", "utilizador"]):
        missing.append("autenticacao")
    if requirements.requires_crud:
        crud_groups = [
            ["create", "criar", "add", "post"],
            ["read", "listar", "ler", "get"],
            ["update", "editar", "put", "patch"],
            ["delete", "apagar", "remover"],
        ]
        if not all(evidence_contains(blob, group) for group in crud_groups):
            missing.append("CRUD")
    if requirements.requires_search and not evidence_contains(blob, ["search", "pesquisa", "filter", "filtro", "filtrar"]):
        missing.append("pesquisa/filtros")
    if requirements.requires_dashboard and not evidence_contains(blob, ["dashboard"]):
        missing.append("dashboard")
    if requirements.requires_preview and not (state.commands_executed or state.sandbox_validated):
        missing.append("preview/sandbox validado")
    if requirements.requires_validation and not (state.commands_executed or state.sandbox_validated):
        missing.append("validacao executada")
    if include_quality and state.success_criteria and not state.quality_checks:
        missing.append("quality check baseado nos criterios declarados")
    return missing

def quality_gate_blocker(prompt: str, state: TaskState, proposed_files: list[str] | None = None) -> str:
    combined_files = list(dict.fromkeys([*state.files_created, *[str(item) for item in (proposed_files or [])]]))
    temp_state = TaskState(
        objective=state.objective,
        objective_declared=state.objective_declared,
        requirements=state.requirements,
        implementation_plan=state.implementation_plan,
        workspace_listed=state.workspace_listed,
        files_created=combined_files,
        artifact_contents=dict(state.artifact_contents),
        files_read=list(state.files_read),
        commands_executed=list(state.commands_executed),
        quality_checks=list(state.quality_checks),
        success_criteria=list(state.success_criteria),
        sandbox_validated=state.sandbox_validated,
    )
    missing = missing_requirement_evidence(prompt, temp_state, include_quality=False)
    if missing:
        return "Quality Gate bloqueado: faltam obrigacoes verificaveis: " + ", ".join(missing) + "."
    if state.actions_without_progress >= 3:
        return "Quality Gate bloqueado: o loop acumulou varias acoes sem progresso real."
    return ""

def deterministic_quality_ready(prompt: str, state: TaskState) -> bool:
    if quality_gate_blocker(prompt, state):
        return False
    return artifacts_satisfy_minimum(prompt, state)

def should_finish_deterministically(prompt: str, task_plan: TaskPlan, state: TaskState) -> bool:
    if task_plan.current_step.id != "finalizar":
        return False
    if state.quality_checks:
        return True
    return deterministic_quality_ready(prompt, state)
