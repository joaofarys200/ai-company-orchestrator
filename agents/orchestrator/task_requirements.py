from __future__ import annotations

import re
from dataclasses import asdict, dataclass

STOPWORDS = {
    "para", "com", "uma", "um", "the", "and", "that", "this", "de", "da", "do", "das",
    "dos", "que", "por", "sem", "mais", "menos", "cria", "criar", "gera", "gerar",
    "faz", "fazer", "desenvolve", "desenvolver", "build", "create", "generate",
    "aplicacao", "aplica??o", "projeto", "project", "ficheiro", "ficheiros",
    "completa", "completo", "simples", "funcional", "funcionais",
}

@dataclass
class TaskRequirements:
    requires_artifacts: bool = False
    requires_frontend: bool = False
    requires_backend: bool = False
    requires_storage: bool = False
    requires_auth: bool = False
    requires_crud: bool = False
    requires_search: bool = False
    requires_dashboard: bool = False
    requires_preview: bool = False
    requires_validation: bool = False

def is_code_generation_task(prompt: str) -> bool:
    text = (prompt or "").lower()
    action_terms = [
        "cria", "criar", "gera", "gerar", "desenvolve", "desenvolver",
        "constrói", "construir", "faz", "fazer", "build", "create", "generate",
    ]
    target_terms = [
        "aplicação", "aplicacao", "app", "frontend", "backend", "ficheiro",
        "ficheiros", "projeto", "project", "sandbox", "website", "site",
        "dashboard", "crud", "api",
    ]
    return any(term in text for term in action_terms) and any(term in text for term in target_terms)

def normalize_text(value: str) -> str:
    return (value or "").lower().replace("ç", "c").replace("ã", "a").replace("á", "a").replace("à", "a").replace("â", "a").replace("é", "e").replace("ê", "e").replace("í", "i").replace("ó", "o").replace("ô", "o").replace("õ", "o").replace("ú", "u")

def objective_tokens(prompt: str, criteria: list[str] | None = None) -> set[str]:
    text = normalize_text(" ".join([prompt or "", *[str(item) for item in (criteria or [])]]))
    tokens = set(re.findall(r"[a-z0-9_]{4,}", text))
    return {token for token in tokens if token not in STOPWORDS}

def task_requires_creation(prompt: str, criteria: list[str] | None = None) -> bool:
    text = normalize_text(" ".join([prompt or "", *[str(item) for item in (criteria or [])]]))
    create_terms = {
        "cria", "criar", "gera", "gerar", "desenvolve", "desenvolver",
        "constroi", "construir", "faz", "fazer", "write", "create", "generate",
        "build", "implementar", "implementa", "guardar", "ficheiro",
    }
    return any(term in text for term in create_terms)

def task_requires_execution(prompt: str, criteria: list[str] | None = None) -> bool:
    text = normalize_text(" ".join([prompt or "", *[str(item) for item in (criteria or [])]]))
    tokens = set(re.findall(r"[a-z0-9_]{3,}", text))
    execution_terms = {
        "executa", "executar", "run", "arranca", "arrancar", "preview",
        "testa", "testar", "validar", "validacao", "verificar",
        "build", "compilar",
    }
    return bool(tokens & execution_terms)

def infer_task_requirements(prompt: str) -> TaskRequirements:
    text = normalize_text(prompt)
    tokens = set(re.findall(r"[a-z0-9_]{3,}", text))
    creation_required = task_requires_creation(prompt)
    explicit_frontend_terms = {
        "frontend", "html", "css", "javascript", "website", "site", "interface",
        "ui", "web", "dashboard",
    }
    requires_frontend = bool(tokens & explicit_frontend_terms) or ("app" in tokens and creation_required)
    requires_backend = bool(tokens & {"backend", "api", "servidor", "server", "rota", "endpoint"})
    requires_storage = bool(tokens & {"storage", "armazenamento", "localstorage", "persistencia", "persistente", "dados", "database", "sqlite"})
    requires_auth = bool(tokens & {"auth", "autenticacao", "login", "sessao", "utilizador", "password"})
    requires_crud = "crud" in tokens or all(term in text for term in ["create", "read", "update", "delete"])
    requires_search = bool(tokens & {"pesquisa", "search", "filtro", "filtros", "filtrar"})
    requires_dashboard = "dashboard" in tokens
    requires_preview = bool(tokens & {"preview", "sandbox"})
    requires_validation = task_requires_execution(prompt) or requires_preview
    return TaskRequirements(
        requires_artifacts=creation_required,
        requires_frontend=requires_frontend,
        requires_backend=requires_backend,
        requires_storage=requires_storage,
        requires_auth=requires_auth,
        requires_crud=requires_crud,
        requires_search=requires_search,
        requires_dashboard=requires_dashboard,
        requires_preview=requires_preview,
        requires_validation=requires_validation,
    )

def effective_requirements(prompt: str, state: TaskState) -> TaskRequirements:
    current = state.requirements
    if any(asdict(current).values()):
        return current
    return infer_task_requirements(prompt)

def evidence_contains(blob: str, terms: list[str]) -> bool:
    for term in terms:
        normalized_term = normalize_text(term)
        if not normalized_term:
            continue
        if re.search(r"[^a-z0-9_]", normalized_term):
            if normalized_term in blob:
                return True
            continue
        if re.search(rf"\b{re.escape(normalized_term)}\b", blob):
            return True
    return False
