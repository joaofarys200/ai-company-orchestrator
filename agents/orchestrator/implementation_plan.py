from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

from agents.orchestrator.action_repair import (
    extract_requested_file_paths,
    is_safe_workspace_relative_path,
    normalize_workspace_path_alias,
)
from agents.orchestrator.task_requirements import TaskRequirements, evidence_contains, normalize_text

@dataclass
class PlannedArtifact:
    path: str
    purpose: str = ""
    obligations: list[str] = field(default_factory=list)

@dataclass
class ImplementationPlan:
    stack: str = ""
    files: list[PlannedArtifact] = field(default_factory=list)
    validation_commands: list[str] = field(default_factory=list)
    completion_criteria: list[str] = field(default_factory=list)
    storage_strategy: str = ""
    crud_map: dict[str, str] = field(default_factory=dict)
    preview_strategy: str = ""
    raw: dict = field(default_factory=dict)
    valid: bool = False
    issues: list[str] = field(default_factory=list)

def extract_json_object(text: str) -> dict:
    raw = (text or "").strip()
    candidates = re.findall(r"```(?:json)?\s*(.*?)```", raw, flags=re.IGNORECASE | re.DOTALL)
    if raw.startswith("{"):
        candidates.append(raw)
    if "{" in raw and "}" in raw:
        candidates.append(raw[raw.find("{"):raw.rfind("}") + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate.strip())
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}

def parse_implementation_plan(data: dict | None) -> ImplementationPlan:
    data = data or {}
    file_items = data.get("files") or data.get("artefacts") or data.get("artifacts") or []
    files: list[PlannedArtifact] = []
    if isinstance(file_items, list):
        for item in file_items:
            if isinstance(item, str):
                path = item
                purpose = ""
                obligations = []
            elif isinstance(item, dict):
                path = item.get("path") or item.get("filename") or item.get("file") or ""
                purpose = item.get("purpose") or item.get("reason") or item.get("description") or ""
                obligations_raw = item.get("obligations") or item.get("requirements") or item.get("covers") or []
                obligations = [str(value) for value in obligations_raw] if isinstance(obligations_raw, list) else [str(obligations_raw)]
            else:
                continue
            path = normalize_workspace_path_alias(path)
            if path:
                files.append(PlannedArtifact(path=path, purpose=str(purpose), obligations=[value for value in obligations if value]))

    validation_commands = data.get("validation_commands") or data.get("commands") or []
    if isinstance(validation_commands, str):
        validation_commands = [validation_commands]
    completion_criteria = data.get("completion_criteria") or data.get("criteria") or []
    if isinstance(completion_criteria, str):
        completion_criteria = [completion_criteria]
    crud_map = data.get("crud_map") or data.get("crud") or {}
    if not isinstance(crud_map, dict):
        crud_map = {"description": str(crud_map)}

    return ImplementationPlan(
        stack=str(data.get("stack") or data.get("architecture") or ""),
        files=files,
        validation_commands=[str(command) for command in validation_commands if str(command).strip()],
        completion_criteria=[str(item) for item in completion_criteria if str(item).strip()],
        storage_strategy=str(data.get("storage_strategy") or data.get("storage") or ""),
        crud_map={str(key): str(value) for key, value in crud_map.items()},
        preview_strategy=str(data.get("preview_strategy") or data.get("preview") or ""),
        raw=data,
    )

def planned_file_paths(plan: ImplementationPlan | None) -> list[str]:
    if not plan:
        return []
    return [artifact.path.replace("\\", "/") for artifact in plan.files if artifact.path]

def plan_blob(plan: ImplementationPlan | None) -> str:
    if not plan:
        return ""
    rows = [plan.stack, plan.storage_strategy, plan.preview_strategy, *plan.validation_commands, *plan.completion_criteria]
    for artifact in plan.files:
        rows.extend([artifact.path, artifact.purpose, " ".join(artifact.obligations)])
    rows.extend([f"{key}: {value}" for key, value in plan.crud_map.items()])
    return normalize_text(" ".join(str(item) for item in rows if item))

def validate_implementation_plan(requirements: TaskRequirements, plan: ImplementationPlan) -> ImplementationPlan:
    issues: list[str] = []
    paths = planned_file_paths(plan)
    for path in paths:
        if not is_safe_workspace_relative_path(path):
            issues.append(f"ficheiro fora do workspace: {path}")
    blob = plan_blob(plan)
    if requirements.requires_artifacts and not paths:
        issues.append("plano sem artefactos")
    if requirements.requires_frontend:
        has_ui = any(
            path.endswith((".html", ".css", ".js", ".jsx", ".tsx"))
            or any(term in normalize_text(path + " " + artifact.purpose + " " + " ".join(artifact.obligations)) for term in ["frontend", "interface", "ui", "html", "css", "web"])
            for path, artifact in [(artifact.path.lower(), artifact) for artifact in plan.files]
        )
        if not has_ui:
            issues.append("frontend pedido mas plano sem artefacto de UI")
    if requirements.requires_backend:
        has_backend = any(
            any(term in normalize_text(artifact.path + " " + artifact.purpose + " " + " ".join(artifact.obligations)) for term in ["backend", "api", "server", "servidor", "endpoint", "rota"])
            for artifact in plan.files
        )
        if not has_backend:
            issues.append("backend pedido mas plano sem artefacto de API/servidor")
    if requirements.requires_storage and not any(term in blob for term in ["storage", "armazenamento", "localstorage", "persist", "sqlite", "json", "ficheiro", "database"]):
        issues.append("storage pedido mas plano nao explica persistencia")
    if requirements.requires_auth and not any(term in blob for term in ["auth", "autenticacao", "login", "sessao", "utilizador"]):
        issues.append("auth pedido mas plano nao cobre autenticacao")
    if requirements.requires_crud:
        crud_terms = ["create", "read", "update", "delete", "criar", "listar", "editar", "apagar", "remover"]
        if len(plan.crud_map) < 4 and not all(term in blob for term in ["create", "read", "update", "delete"]):
            if not all(any(term in blob for term in group) for group in [["create", "criar"], ["read", "listar", "ler"], ["update", "editar"], ["delete", "apagar", "remover"]]):
                issues.append("CRUD pedido mas plano nao mapeia create/read/update/delete")
    if requirements.requires_search and not any(term in blob for term in ["pesquisa", "search", "filtro", "filtrar"]):
        issues.append("pesquisa/filtros pedidos mas plano nao cobre essa obrigacao")
    if requirements.requires_dashboard and "dashboard" not in blob:
        issues.append("dashboard pedido mas plano nao cobre dashboard")
    if requirements.requires_preview and not (plan.preview_strategy or plan.validation_commands):
        issues.append("preview pedido mas plano nao indica validacao/preview")
    if requirements.requires_validation and not (plan.validation_commands or plan.preview_strategy):
        issues.append("validacao pedida mas plano nao indica comandos ou estrategia")
    plan.issues = issues
    plan.valid = not issues
    return plan

def fallback_plan_from_explicit_files(prompt: str, requirements: TaskRequirements) -> ImplementationPlan:
    paths = extract_requested_file_paths(prompt)
    if not paths:
        return ImplementationPlan(issues=["sem ficheiros explicitos para fallback"], valid=False)
    files = [PlannedArtifact(path=path, purpose="Ficheiro pedido explicitamente na prompt.", obligations=["artifacts"]) for path in paths]
    plan = ImplementationPlan(
        stack="Escolhida implicitamente pelo pedido de ficheiros explicitos.",
        files=files,
        completion_criteria=[f"{path} criado" for path in paths],
        raw={"fallback": "explicit_files"},
    )
    return validate_implementation_plan(requirements, plan)

def implementation_plan_context(plan: ImplementationPlan, requirements: TaskRequirements) -> str:
    req = asdict(requirements)
    files = [
        {"path": artifact.path, "purpose": artifact.purpose, "obligations": artifact.obligations}
        for artifact in plan.files
    ]
    payload = {
        "requirements": req,
        "stack": plan.stack,
        "files": files,
        "validation_commands": plan.validation_commands,
        "completion_criteria": plan.completion_criteria,
        "storage_strategy": plan.storage_strategy,
        "crud_map": plan.crud_map,
        "preview_strategy": plan.preview_strategy,
        "valid": plan.valid,
        "issues": plan.issues,
    }
    return "[IMPLEMENTATION_PLAN]\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n[/IMPLEMENTATION_PLAN]"
