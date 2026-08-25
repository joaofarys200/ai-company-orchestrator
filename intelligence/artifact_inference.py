"""
JARVIS OS - Deterministic Artifact Inference & Repair Engine (Fase 9.2)

Fornece uma camada determinística de inferência de capacidades, mapeamento de
artefactos mínimos obrigatórios, esqueletos de código funcionais e reparação
automática de planos de alteração e geração de projetos, reduzindo a dependência
estocástica do LLM para decisões estruturais fundamentais.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class Capability(str, Enum):
    FRONTEND = "frontend"
    BACKEND = "backend"
    STORAGE = "storage"
    AUTH = "auth"
    CRUD = "crud"
    DASHBOARD = "dashboard"
    SEARCH = "search"
    PREVIEW = "preview"
    TESTING = "testing"
    CLI = "cli"
    API = "api"


@dataclass
class InferredArtifact:
    relative_path: str
    component: str
    required: bool = True
    description: str = ""
    default_content: str = ""
    functional_contracts: list[str] = field(default_factory=list)


@dataclass
class CapabilityInferenceResult:
    prompt: str
    detected_capabilities: set[Capability]
    required_artifacts: list[InferredArtifact]
    entrypoints: list[str]
    contracts_by_file: dict[str, list[str]] = field(default_factory=dict)
    diagnostics: list[str] = field(default_factory=list)

    def has_capability(self, capability: Capability | str) -> bool:
        cap_val = Capability(capability) if isinstance(capability, str) else capability
        return cap_val in self.detected_capabilities

    def get_artifact(self, relative_path: str) -> Optional[InferredArtifact]:
        normalized = relative_path.replace("\\", "/").strip().lstrip("./")
        for art in self.required_artifacts:
            if art.relative_path == normalized:
                return art
        return None

    def required_paths(self) -> list[str]:
        return [art.relative_path for art in self.required_artifacts if art.required]


@dataclass
class RepairAction:
    action_type: str  # "CREATE_FILE", "PATCH_FILE", "INJECT_CONTRACT"
    relative_path: str
    reason: str
    content: str
    contract_applied: Optional[str] = None


@dataclass
class RepairResult:
    repaired: bool
    actions: list[RepairAction]
    repaired_files: dict[str, str]
    diagnostics: list[str] = field(default_factory=list)
    missing_before: list[str] = field(default_factory=list)
    unresolved_contracts: list[str] = field(default_factory=list)


def normalize_text(text: str) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    without_accents = "".join(c for c in normalized if not unicodedata.combining(c))
    return without_accents.lower().strip()


class CapabilityDetector:
    """
    Deteta de forma determinística capacidades a partir de prompts e contexto.
    Suporta análise multilíngue (Português e Inglês), termos canónicos e exclusões.
    """

    CAPABILITY_PATTERNS: dict[Capability, list[re.Pattern]] = {
        Capability.FRONTEND: [
            re.compile(r"\b(pagina|site|website|web\s*app|frontend|interface|ui|html|css|ecra|tela|layout|view|react|vue|vanilla|browser|navegador)\b"),
            re.compile(r"\b(web\s*page|front\s*end|webpage|user\s*interface)\b"),
        ],
        Capability.BACKEND: [
            re.compile(r"\b(backend|back\s*end|servidor|server|api|endpoint|rotas|routes|fastapi|flask|express|nodejs|node|python\s*server)\b"),
            re.compile(r"\b(microservice|web\s*service|http\s*server)\b"),
        ],
        Capability.STORAGE: [
            re.compile(r"\b(guarda|guardar|salva|salvar|grava|gravar|armazena|armazenar|persiste|persistencia|persistir|localstorage|sessionstorage|indexeddb|sqlite|database|bd|banco|dados|storage|localmente)\b"),
            re.compile(r"\b(save\s*data|persist|local\s*storage|store|database|db)\b"),
        ],
        Capability.AUTH: [
            re.compile(r"\b(login|autenticacao|auth|sessao|registo|signup|sign\s*in|password|jwt|token|utilizador|usuario|logout)\b"),
            re.compile(r"\b(authentication|log\s*in|sign\s*up|credentials|user\s*auth)\b"),
        ],
        Capability.CRUD: [
            re.compile(r"\b(crud|gestao|gerir|tarefas|todo|tasks|items|produtos)\b"),
            re.compile(r"\b(lista\s+de|gerenciador\s+de\s+tarefas|task\s*manager|management|list\s*app)\b"),
            re.compile(r"\b(create\s*read\s*update\s*delete)\b"),
        ],
        Capability.DASHBOARD: [
            re.compile(r"\b(dashboard|painel|metricas|estatisticas|graficos|kpis|resumo|indicadores|analytics|stats|contadores)\b"),
            re.compile(r"\b(overview|metrics|charts|summary\s*panel)\b"),
        ],
        Capability.SEARCH: [
            re.compile(r"\b(pesquisa|pesquisar|procurar|busca|buscar|filtrar|filtro|filtros|ordenar|ordenacao|query)\b"),
            re.compile(r"\b(search|filter|filtering|lookup|querying|sorting)\b"),
        ],
        Capability.PREVIEW: [
            re.compile(r"\b(mostra|mostrar|browser|navegador|preview|ver|executar|abrir|healthcheck|health|live)\b"),
            re.compile(r"\b(run\s*in\s*browser|view\s*app|open\s*browser)\b"),
        ],
        Capability.TESTING: [
            re.compile(r"\b(teste|testes|testar|pytest|jest|unit\s*test|spec|specs|verificar)\b"),
            re.compile(r"\b(test|tests|testing|test\s*suite)\b"),
        ],
        Capability.CLI: [
            re.compile(r"\b(cli|linha\s*de\s*comandos|terminal|argumentos|argparse|sys\.argv|script)\b"),
            re.compile(r"\b(command\s*line|console\s*app)\b"),
        ],
        Capability.API: [
            re.compile(r"\b(api|rest|json\s*api|endpoints|swagger|post\s*get|http\s*methods)\b"),
            re.compile(r"\b(restful|rest\s*api)\b"),
        ],
    }

    NEGATION_PATTERNS: list[re.Pattern] = [
        re.compile(r"\b(sem|nao|não|without|no)\s+([a-z0-9_\-]+)\b"),
    ]

    def detect(self, prompt: str, project_context: Optional[dict[str, Any]] = None) -> set[Capability]:
        norm = normalize_text(prompt)
        detected: set[Capability] = set()

        for capability, patterns in self.CAPABILITY_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(norm):
                    detected.add(capability)
                    break

        # Contextual inferences
        if Capability.CRUD in detected and Capability.FRONTEND not in detected and Capability.BACKEND not in detected and Capability.CLI not in detected:
            # Default to frontend if CRUD is asked without specific backend/cli context
            detected.add(Capability.FRONTEND)

        if Capability.DASHBOARD in detected and Capability.FRONTEND not in detected:
            detected.add(Capability.FRONTEND)

        if Capability.SEARCH in detected and Capability.FRONTEND not in detected and Capability.BACKEND not in detected:
            detected.add(Capability.FRONTEND)

        if (Capability.FRONTEND in detected or Capability.BACKEND in detected) and Capability.PREVIEW not in detected:
            # By default, frontend/backend web requests benefit from preview capability
            detected.add(Capability.PREVIEW)

        # Storage is implied by CRUD or Dashboard persistence unless explicitly negated
        if Capability.CRUD in detected and Capability.STORAGE not in detected and "sem persistencia" not in norm and "sem guardar" not in norm:
            detected.add(Capability.STORAGE)

        # Process explicit negations
        for pattern in self.NEGATION_PATTERNS:
            for neg in pattern.finditer(norm):
                negated_term = neg.group(2)
                if negated_term in ("backend", "servidor", "server") and Capability.BACKEND in detected:
                    detected.remove(Capability.BACKEND)
                if negated_term in ("frontend", "ui", "interface") and Capability.FRONTEND in detected:
                    detected.remove(Capability.FRONTEND)
                if negated_term in ("persistencia", "guardar", "storage", "db", "database") and Capability.STORAGE in detected:
                    detected.remove(Capability.STORAGE)
                if negated_term in ("login", "auth", "autenticacao") and Capability.AUTH in detected:
                    detected.remove(Capability.AUTH)

        # Context-based augmentation if project already exists
        if project_context:
            files = project_context.get("files", [])
            if any("html" in f.lower() for f in files):
                detected.add(Capability.FRONTEND)
            if any("server.py" in f.lower() or "app.py" in f.lower() or "server.js" in f.lower() for f in files):
                detected.add(Capability.BACKEND)

        # Discard frontend for explicit standalone single-file non-web tasks (e.g. "cria hello.txt", "cria app.js")
        is_single_file = bool(re.search(r"\b(cria|criar|make|write)\s+[a-z0-9_\-]+\.(txt|md|py|sh|json|csv|yaml|yml|js|ts)\b", norm))
        if is_single_file:
            if not any(w in norm for w in ["site", "website", "pagina", "web app", "frontend", "html", "react", "vue"]):
                detected.discard(Capability.FRONTEND)
                detected.discard(Capability.PREVIEW)
        elif not detected and any(re.search(rf"\b{w}\b", norm) for w in ["app", "aplicacao", "site", "web", "pagina", "ui", "painel", "dashboard", "frontend", "jogo", "game"]):
            detected.add(Capability.FRONTEND)
            detected.add(Capability.PREVIEW)

        return detected


class ArtifactInferenceEngine:
    """
    Mapeia capacidades detectadas para ficheiros determinísticos,
    conteúdos padrão (esqueletos funcionais) e contratos estruturais.
    """

    def __init__(self, detector: Optional[CapabilityDetector] = None):
        self.detector = detector or CapabilityDetector()

    def infer(self, prompt: str, project_name: str = "app", project_context: Optional[dict[str, Any]] = None) -> CapabilityInferenceResult:
        capabilities = self.detector.detect(prompt, project_context)
        artifacts: list[InferredArtifact] = []
        entrypoints: list[str] = []
        contracts_by_file: dict[str, list[str]] = {}
        diagnostics: list[str] = []

        is_frontend = Capability.FRONTEND in capabilities
        is_backend = Capability.BACKEND in capabilities
        is_storage = Capability.STORAGE in capabilities
        is_auth = Capability.AUTH in capabilities
        is_crud = Capability.CRUD in capabilities
        is_dashboard = Capability.DASHBOARD in capabilities
        is_search = Capability.SEARCH in capabilities
        is_preview = Capability.PREVIEW in capabilities

        # 1. FRONTEND ARTIFACTS
        if is_frontend:
            entrypoints.append("index.html")
            
            # HTML
            html_contracts = ["<!DOCTYPE html>", "<div id=\"app\"", "<script"]
            if is_search:
                html_contracts.append("id=\"search-input\"")
            if is_dashboard:
                html_contracts.append("id=\"dashboard\"")
            if is_auth:
                html_contracts.append("id=\"auth-container\"")
            if is_crud:
                html_contracts.append("id=\"item-form\"")

            html_content = self._generate_html_skeleton(project_name, capabilities)
            artifacts.append(InferredArtifact(
                relative_path="index.html",
                component="frontend",
                required=True,
                description="Ponto de entrada HTML5 responsivo",
                default_content=html_content,
                functional_contracts=html_contracts,
            ))
            contracts_by_file["index.html"] = html_contracts

            # CSS
            css_content = self._generate_css_skeleton(capabilities)
            css_contracts = ["body", "box-sizing"]
            artifacts.append(InferredArtifact(
                relative_path="styles.css",
                component="frontend",
                required=True,
                description="Estilos CSS modernos e responsivos",
                default_content=css_content,
                functional_contracts=css_contracts,
            ))
            contracts_by_file["styles.css"] = css_contracts

            # JS
            js_contracts = ["document.addEventListener"]
            if is_storage:
                js_contracts.append("localStorage")
            if is_search:
                js_contracts.append("filter")
            if is_crud:
                js_contracts.append("render")
            if is_auth:
                js_contracts.append("currentUser")

            js_content = self._generate_js_skeleton(project_name, capabilities)
            artifacts.append(InferredArtifact(
                relative_path="app.js",
                component="frontend",
                required=True,
                description="Lógica client-side com gestão de estado e eventos",
                default_content=js_content,
                functional_contracts=js_contracts,
            ))
            contracts_by_file["app.js"] = js_contracts

        # 2. BACKEND ARTIFACTS
        if is_backend:
            entrypoints.append("server.py")
            backend_contracts = ["def", "PORT"]
            if is_preview:
                backend_contracts.append("/health")
            if Capability.API in capabilities:
                backend_contracts.append("json")

            py_backend_content = self._generate_python_backend_skeleton(project_name, capabilities)
            artifacts.append(InferredArtifact(
                relative_path="server.py",
                component="backend",
                required=True,
                description="Servidor HTTP / API REST em Python com rota de healthcheck",
                default_content=py_backend_content,
                functional_contracts=backend_contracts,
            ))
            contracts_by_file["server.py"] = backend_contracts

        # 3. STORAGE ARTIFACTS (para backend ou persistência dedicada)
        if is_backend and is_storage:
            artifacts.append(InferredArtifact(
                relative_path="database.py",
                component="storage",
                required=False,
                description="Camada de persistência SQLite",
                default_content=self._generate_database_skeleton(),
                functional_contracts=["sqlite3", "CREATE TABLE IF NOT EXISTS"],
            ))

        # 4. PACKAGE.JSON & README
        pkg_json = self._generate_package_json(project_name, capabilities)
        artifacts.append(InferredArtifact(
            relative_path="package.json",
            component="scaffolding",
            required=False,
            description="Metadados do projeto e scripts de execução",
            default_content=pkg_json,
            functional_contracts=["name", "version"],
        ))

        readme_content = f"# {project_name.capitalize()}\n\nAplicação gerada pelo JARVIS OS com capacidades: {', '.join(c.value for c in capabilities)}.\n"
        artifacts.append(InferredArtifact(
            relative_path="README.md",
            component="documentation",
            required=False,
            description="Documentação do projeto",
            default_content=readme_content,
            functional_contracts=["# "],
        ))

        diagnostics.append(f"Capacidades detetadas: {', '.join(sorted(c.value for c in capabilities))}")
        diagnostics.append(f"Artefactos obrigatórios inferidos: {', '.join(a.relative_path for a in artifacts if a.required)}")

        return CapabilityInferenceResult(
            prompt=prompt,
            detected_capabilities=capabilities,
            required_artifacts=artifacts,
            entrypoints=entrypoints,
            contracts_by_file=contracts_by_file,
            diagnostics=diagnostics,
        )

    # -------------------------------------------------------------------------
    # SKELETON GENERATORS
    # -------------------------------------------------------------------------

    def _generate_html_skeleton(self, project_name: str, capabilities: set[Capability]) -> str:
        title = project_name.replace("-", " ").title()
        has_auth = Capability.AUTH in capabilities
        has_search = Capability.SEARCH in capabilities
        has_dashboard = Capability.DASHBOARD in capabilities
        has_crud = Capability.CRUD in capabilities

        search_html = """
        <!-- Search & Filter Bar -->
        <div class="search-bar">
            <input type="text" id="search-input" placeholder="Pesquisar..." aria-label="Pesquisar">
            <select id="filter-select" aria-label="Filtrar">
                <option value="all">Todos</option>
                <option value="active">Ativos</option>
                <option value="completed">Concluídos</option>
            </select>
        </div>""" if has_search else ""

        dashboard_html = """
        <!-- Dashboard Summary -->
        <div id="dashboard" class="dashboard-grid">
            <div class="stat-card">
                <span class="stat-label">Total de Itens</span>
                <span id="stat-total" class="stat-value">0</span>
            </div>
            <div class="stat-card">
                <span class="stat-label">Ativos</span>
                <span id="stat-active" class="stat-value">0</span>
            </div>
            <div class="stat-card">
                <span class="stat-label">Concluídos</span>
                <span id="stat-completed" class="stat-value">0</span>
            </div>
        </div>""" if has_dashboard else ""

        auth_html = """
        <!-- Auth Container -->
        <div id="auth-container" class="auth-box">
            <div id="auth-logged-out">
                <h2>Iniciar Sessão</h2>
                <form id="login-form">
                    <input type="text" id="username-input" placeholder="Nome de utilizador" required>
                    <button type="submit" class="btn btn-primary">Entrar</button>
                </form>
            </div>
            <div id="auth-logged-in" class="hidden">
                <span>Bem-vindo, <strong id="user-display"></strong>!</span>
                <button id="logout-btn" class="btn btn-secondary">Terminar Sessão</button>
            </div>
        </div>""" if has_auth else ""

        crud_html = """
        <!-- CRUD Form -->
        <form id="item-form" class="item-form">
            <input type="text" id="item-title" placeholder="Nova tarefa ou registo..." required>
            <button type="submit" class="btn btn-primary" id="add-btn">Adicionar</button>
        </form>

        <!-- Items List -->
        <div class="list-container">
            <ul id="items-list" class="items-list"></ul>
            <div id="empty-state" class="empty-state">Nenhum item registado.</div>
        </div>""" if has_crud else ""

        return f"""<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div id="app" class="app-container">
        <header class="app-header">
            <div class="header-brand">
                <div class="logo-icon">⚡</div>
                <h1>{title}</h1>
            </div>
            <div class="status-indicator">
                <span class="dot online"></span>
                <span>Sistema Pronto</span>
            </div>
        </header>

        <main class="app-main">
            {auth_html}
            {dashboard_html}
            {search_html}
            {crud_html}
        </main>

        <footer class="app-footer">
            <p>&copy; 2026 {title} &bull; JARVIS OS Autonomous Engine</p>
        </footer>
    </div>
    <script src="app.js"></script>
</body>
</html>"""

    def _generate_css_skeleton(self, capabilities: set[Capability]) -> str:
        return """/* JARVIS OS - Clean Modern Design System */
:root {
    --bg-base: #0a0e17;
    --bg-surface: #111827;
    --bg-elevated: #1f2937;
    --border-color: #374151;
    --border-accent: #06b6d4;
    --text-main: #f3f4f6;
    --text-muted: #9ca3af;
    --accent-primary: #06b6d4;
    --accent-hover: #0891b2;
    --accent-success: #10b981;
    --accent-danger: #ef4444;
    --radius-sm: 6px;
    --radius-md: 10px;
    --radius-lg: 16px;
    --shadow-main: 0 4px 20px rgba(0, 0, 0, 0.4);
    --font-sans: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: var(--font-sans);
    background-color: var(--bg-base);
    color: var(--text-main);
    min-height: 100vh;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    padding: 2rem 1rem;
    line-height: 1.5;
}

.app-container {
    width: 100%;
    max-width: 800px;
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-main);
    overflow: hidden;
    display: flex;
    flex-direction: column;
}

.app-header {
    padding: 1.5rem 2rem;
    background: var(--bg-elevated);
    border-bottom: 1px solid var(--border-color);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.header-brand {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.logo-icon {
    font-size: 1.5rem;
}

.app-header h1 {
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--text-main);
}

.status-indicator {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.75rem;
    color: var(--text-muted);
}

.dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
}

.dot.online {
    background-color: var(--accent-success);
    box-shadow: 0 0 8px var(--accent-success);
}

.app-main {
    padding: 2rem;
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
}

/* Dashboard Grid */
.dashboard-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1rem;
}

.stat-card {
    background: var(--bg-elevated);
    border: 1px solid var(--border-color);
    padding: 1rem;
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.stat-label {
    font-size: 0.75rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.stat-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--accent-primary);
}

/* Search Bar */
.search-bar {
    display: flex;
    gap: 0.75rem;
}

.search-bar input,
.search-bar select,
.item-form input {
    background: var(--bg-elevated);
    border: 1px solid var(--border-color);
    color: var(--text-main);
    padding: 0.65rem 1rem;
    border-radius: var(--radius-sm);
    font-size: 0.875rem;
    outline: none;
    transition: border-color 0.2s;
}

.search-bar input:focus,
.search-bar select:focus,
.item-form input:focus {
    border-color: var(--accent-primary);
}

.search-bar input {
    flex: 1;
}

/* Form & Buttons */
.item-form {
    display: flex;
    gap: 0.75rem;
}

.item-form input {
    flex: 1;
}

.btn {
    padding: 0.65rem 1.25rem;
    border: none;
    border-radius: var(--radius-sm);
    font-weight: 600;
    font-size: 0.875rem;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-primary {
    background: var(--accent-primary);
    color: #000;
}

.btn-primary:hover {
    background: var(--accent-hover);
}

.btn-secondary {
    background: var(--bg-elevated);
    border: 1px solid var(--border-color);
    color: var(--text-main);
}

.btn-secondary:hover {
    background: var(--border-color);
}

/* Items List */
.items-list {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.item-row {
    background: var(--bg-elevated);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    padding: 0.75rem 1rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: border-color 0.2s;
}

.item-row:hover {
    border-color: rgba(6, 182, 212, 0.4);
}

.item-row.completed span {
    text-decoration: line-through;
    color: var(--text-muted);
}

.item-actions {
    display: flex;
    gap: 0.5rem;
}

.btn-sm {
    padding: 0.25rem 0.5rem;
    font-size: 0.75rem;
}

.empty-state {
    text-align: center;
    padding: 2rem;
    color: var(--text-muted);
    font-size: 0.875rem;
}

.hidden {
    display: none !important;
}

.app-footer {
    padding: 1rem 2rem;
    background: var(--bg-elevated);
    border-top: 1px solid var(--border-color);
    text-align: center;
    font-size: 0.75rem;
    color: var(--text-muted);
}
"""

    def _generate_js_skeleton(self, project_name: str, capabilities: set[Capability]) -> str:
        has_auth = Capability.AUTH in capabilities
        has_search = Capability.SEARCH in capabilities
        has_dashboard = Capability.DASHBOARD in capabilities
        has_crud = Capability.CRUD in capabilities
        has_storage = Capability.STORAGE in capabilities

        storage_key = f"{project_name}_data_v1"

        return f"""// JARVIS OS - Deterministic Client Logic
document.addEventListener('DOMContentLoaded', () => {{
    const STORAGE_KEY = '{storage_key}';
    let items = loadState();
    let currentUser = {('localStorage.getItem("' + project_name + '_user") || ""') if has_auth else 'null'};

    // DOM Elements
    const itemForm = document.getElementById('item-form');
    const itemTitle = document.getElementById('item-title');
    const itemsList = document.getElementById('items-list');
    const emptyState = document.getElementById('empty-state');
    const searchInput = document.getElementById('search-input');
    const filterSelect = document.getElementById('filter-select');

    // Dashboard Elements
    const statTotal = document.getElementById('stat-total');
    const statActive = document.getElementById('stat-active');
    const statCompleted = document.getElementById('stat-completed');

    // Auth Elements
    const authBox = document.getElementById('auth-container');
    const loginForm = document.getElementById('login-form');
    const usernameInput = document.getElementById('username-input');
    const authLoggedOut = document.getElementById('auth-logged-out');
    const authLoggedIn = document.getElementById('auth-logged-in');
    const userDisplay = document.getElementById('user-display');
    const logoutBtn = document.getElementById('logout-btn');

    function loadState() {{
        {('try { const raw = localStorage.getItem(STORAGE_KEY); return raw ? JSON.parse(raw) : []; } catch { return []; }') if has_storage else 'return [];'}
    }}

    function saveState() {{
        {('try { localStorage.setItem(STORAGE_KEY, JSON.stringify(items)); } catch (e) { console.error("Erro ao guardar dados:", e); }') if has_storage else '// Sem persistencia local'}
        updateDashboard();
    }}

    function updateDashboard() {{
        if (!statTotal) return;
        const total = items.length;
        const completed = items.filter(i => i.completed).length;
        const active = total - completed;

        if (statTotal) statTotal.textContent = total;
        if (statActive) statActive.textContent = active;
        if (statCompleted) statCompleted.textContent = completed;
    }}

    function renderItems() {{
        if (!itemsList) return;
        itemsList.innerHTML = '';

        let filtered = [...items];
        const query = searchInput ? searchInput.value.toLowerCase().trim() : '';
        const filter = filterSelect ? filterSelect.value : 'all';

        if (query) {{
            filtered = filtered.filter(i => i.title.toLowerCase().includes(query));
        }}

        if (filter === 'active') {{
            filtered = filtered.filter(i => !i.completed);
        }} else if (filter === 'completed') {{
            filtered = filtered.filter(i => i.completed);
        }}

        if (filtered.length === 0) {{
            if (emptyState) emptyState.classList.remove('hidden');
        }} else {{
            if (emptyState) emptyState.classList.add('hidden');
            filtered.forEach(item => {{
                const li = document.createElement('li');
                li.className = `item-row ${{item.completed ? 'completed' : ''}}`;
                
                const titleSpan = document.createElement('span');
                titleSpan.textContent = item.title;

                const actions = document.createElement('div');
                actions.className = 'item-actions';

                const toggleBtn = document.createElement('button');
                toggleBtn.className = 'btn btn-secondary btn-sm';
                toggleBtn.textContent = item.completed ? '↩ Reabrir' : '✓ Concluir';
                toggleBtn.onclick = () => toggleItem(item.id);

                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'btn btn-secondary btn-sm';
                deleteBtn.textContent = '✕';
                deleteBtn.onclick = () => deleteItem(item.id);

                actions.appendChild(toggleBtn);
                actions.appendChild(deleteBtn);
                li.appendChild(titleSpan);
                li.appendChild(actions);
                itemsList.appendChild(li);
            }});
        }}

        updateDashboard();
    }}

    function addItem(title) {{
        const newItem = {{
            id: Date.now().toString(),
            title: title.trim(),
            completed: false,
            createdAt: new Date().toISOString()
        }};
        items.unshift(newItem);
        saveState();
        renderItems();
    }}

    function toggleItem(id) {{
        items = items.map(item => item.id === id ? {{ ...item, completed: !item.completed }} : item);
        saveState();
        renderItems();
    }}

    function deleteItem(id) {{
        items = items.filter(item => item.id !== id);
        saveState();
        renderItems();
    }}

    // Event Listeners
    if (itemForm) {{
        itemForm.addEventListener('submit', (e) => {{
            e.preventDefault();
            if (itemTitle && itemTitle.value.trim()) {{
                addItem(itemTitle.value);
                itemTitle.value = '';
            }}
        }});
    }}

    if (searchInput) {{
        searchInput.addEventListener('input', renderItems);
    }}

    if (filterSelect) {{
        filterSelect.addEventListener('change', renderItems);
    }}

    // Auth Handlers
    function updateAuthUI() {{
        if (!authBox) return;
        if (currentUser) {{
            if (authLoggedOut) authLoggedOut.classList.add('hidden');
            if (authLoggedIn) authLoggedIn.classList.remove('hidden');
            if (userDisplay) userDisplay.textContent = currentUser;
        }} else {{
            if (authLoggedOut) authLoggedOut.classList.remove('hidden');
            if (authLoggedIn) authLoggedIn.classList.add('hidden');
        }}
    }}

    if (loginForm) {{
        loginForm.addEventListener('submit', (e) => {{
            e.preventDefault();
            if (usernameInput && usernameInput.value.trim()) {{
                currentUser = usernameInput.value.trim();
                localStorage.setItem('{project_name}_user', currentUser);
                updateAuthUI();
            }}
        }});
    }}

    if (logoutBtn) {{
        logoutBtn.addEventListener('click', () => {{
            currentUser = '';
            localStorage.removeItem('{project_name}_user');
            updateAuthUI();
        }});
    }}

    updateAuthUI();
    renderItems();
    console.log('[JARVIS OS] Aplicação inicializada com sucesso.');
}});
"""

    def _generate_python_backend_skeleton(self, project_name: str, capabilities: set[Capability]) -> str:
        return f"""\"\"\"
JARVIS OS - Backend API Server ({project_name})
\"\"\"

from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import os
import sys

PORT = int(os.environ.get("PORT", 8080))

class ApplicationHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health" or self.path == "/api/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            response = {{"status": "ok", "app": "{project_name}", "version": "1.0.0"}}
            self.wfile.write(json.dumps(response).encode("utf-8"))
            return

        if self.path == "/api/items":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({{"items": []}}).encode("utf-8"))
            return

        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/items":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{{}}"
            try:
                data = json.loads(body)
            except Exception:
                data = {{}}
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({{"status": "created", "item": data}}).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

def run_server(port=PORT):
    server_address = ("", port)
    httpd = HTTPServer(server_address, ApplicationHandler)
    print(f"[JARVIS Backend] Servidor ativo em http://localhost:{{port}}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("[JARVIS Backend] Servidor encerrado.")

if __name__ == "__main__":
    run_server()
"""

    def _generate_database_skeleton(self) -> str:
        return """\"\"\"
JARVIS OS - SQLite Database Layer
\"\"\"

import sqlite3
import os

DB_PATH = os.environ.get("DATABASE_PATH", "app.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        conn.execute(\"\"\"
            CREATE TABLE IF NOT EXISTS items (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                completed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        \"\"\")
        conn.commit()

if __name__ == "__main__":
    init_db()
    print("[Database] Tabela 'items' inicializada.")
"""

    def _generate_package_json(self, project_name: str, capabilities: set[Capability]) -> str:
        return json.dumps({
            "name": project_name,
            "version": "1.0.0",
            "description": f"Projeto {project_name} gerado pelo JARVIS OS",
            "scripts": {
                "start": "python server.py" if Capability.BACKEND in capabilities else "npx serve ."
            },
            "dependencies": {}
        }, indent=2)


@dataclass
class DiscoveredDependencies:
    cdn_tags: list[str] = field(default_factory=list)
    npm_packages: dict[str, str] = field(default_factory=dict)
    pip_packages: list[str] = field(default_factory=list)


class DependencyScanner:
    """
    Analisa ficheiros do projeto e infere automaticamente CDNs para frontend
    e pacotes Python/Node para manifestos (requirements.txt / package.json).
    """

    KNOWN_CDN_MAP = [
        # (Pattern, CDN Tag, NPM Package, NPM Version)
        (
            r"(chart\.js|\bChart\b|\bchartjs\b)",
            '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>',
            "chart.js",
            "^4.4.1",
        ),
        (
            r"(lucide|\bdata-lucide\b)",
            '<script src="https://unpkg.com/lucide@latest"></script>',
            "lucide",
            "^0.344.0",
        ),
        (
            r"(canvas-confetti|\bconfetti\s*\()",
            '<script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.9.3/dist/confetti.browser.min.js"></script>',
            "canvas-confetti",
            "^1.9.3",
        ),
        (
            r"(axios|\baxios\s*[\.\(])",
            '<script src="https://cdn.jsdelivr.net/npm/axios/dist/axios.min.js"></script>',
            "axios",
            "^1.6.8",
        ),
        (
            r"(tailwindcss|\btailwind\b)",
            '<script src="https://cdn.tailwindcss.com"></script>',
            "tailwindcss",
            "^3.4.1",
        ),
        (
            r"(alpinejs|\bAlpine\b|\bx-data\b)",
            '<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>',
            "alpinejs",
            "^3.13.7",
        ),
        (
            r"(font-awesome|fontawesome|\bfa-[a-z0-9-]+)",
            '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">',
            "@fortawesome/fontawesome-free",
            "^6.5.1",
        ),
    ]

    KNOWN_PYTHON_PACKAGES = [
        (r"\b(import\s+fastapi|from\s+fastapi\b)", "fastapi>=0.110.0"),
        (r"\b(import\s+uvicorn|from\s+uvicorn\b)", "uvicorn>=0.28.0"),
        (r"\b(import\s+flask|from\s+flask\b)", "flask>=3.0.0"),
        (r"\b(import\s+requests|from\s+requests\b)", "requests>=2.31.0"),
        (r"\b(import\s+httpx|from\s+httpx\b)", "httpx>=0.27.0"),
        (r"\b(import\s+sqlalchemy|from\s+sqlalchemy\b)", "sqlalchemy>=2.0.0"),
        (r"\b(import\s+pydantic|from\s+pydantic\b)", "pydantic>=2.6.0"),
        (r"\b(import\s+pandas|from\s+pandas\b)", "pandas>=2.2.0"),
        (r"\b(import\s+numpy|from\s+numpy\b)", "numpy>=1.26.0"),
        (r"\b(import\s+dotenv|from\s+dotenv\b)", "python-dotenv>=1.0.0"),
    ]

    def scan(self, files: dict[str, str]) -> DiscoveredDependencies:
        cdn_tags: list[str] = []
        npm_packages: dict[str, str] = {}
        pip_packages: list[str] = []

        all_js_html_content = []
        all_py_content = []

        for path, content in files.items():
            ext = Path(path).suffix.lower()
            if ext in (".html", ".htm", ".js", ".mjs", ".ts", ".jsx", ".tsx", ".css"):
                all_js_html_content.append(content)
            elif ext == ".py":
                all_py_content.append(content)

        full_frontend_code = "\n".join(all_js_html_content)
        full_backend_code = "\n".join(all_py_content)

        # Scan Frontend Dependencies
        for pattern, cdn_tag, npm_pkg, npm_ver in self.KNOWN_CDN_MAP:
            if re.search(pattern, full_frontend_code, re.IGNORECASE):
                if cdn_tag not in cdn_tags:
                    cdn_tags.append(cdn_tag)
                npm_packages[npm_pkg] = npm_ver

        # Scan Backend Python Dependencies
        for pattern, pip_spec in self.KNOWN_PYTHON_PACKAGES:
            if re.search(pattern, full_backend_code):
                if pip_spec not in pip_packages:
                    pip_packages.append(pip_spec)

        return DiscoveredDependencies(
            cdn_tags=cdn_tags,
            npm_packages=npm_packages,
            pip_packages=pip_packages,
        )


class DeterministicRepairEngine:
    """
    Inspeciona planos de alteração ou diretórios de projetos,
    compara com a inferência determinística e repara lacunas estruturais.
    """

    def __init__(
        self,
        inference_engine: Optional[ArtifactInferenceEngine] = None,
        dependency_scanner: Optional[DependencyScanner] = None,
    ):
        self.inference_engine = inference_engine or ArtifactInferenceEngine()
        self.dependency_scanner = dependency_scanner or DependencyScanner()

    def repair_plan(
        self,
        prompt: str,
        planned_files: dict[str, str],
        project_name: str = "app",
        project_context: Optional[dict[str, Any]] = None,
    ) -> RepairResult:
        inference = self.inference_engine.infer(prompt, project_name, project_context)
        actions: list[RepairAction] = []
        repaired_files = dict(planned_files)
        diagnostics: list[str] = []
        missing_before: list[str] = []
        unresolved_contracts: list[str] = []

        # 1. Verificar artefactos em falta
        for required_art in inference.required_artifacts:
            if not required_art.required:
                continue

            rel_path = required_art.relative_path
            # Aceitar aliases comuns (ex: styles.css vs style.css, app.js vs index.js / main.js)
            existing_match = self._find_matching_path(rel_path, repaired_files)

            if not existing_match:
                missing_before.append(rel_path)
                actions.append(RepairAction(
                    action_type="CREATE_FILE",
                    relative_path=rel_path,
                    reason=f"Artefacto obrigatório inferido '{rel_path}' estava ausente no plano.",
                    content=required_art.default_content,
                ))
                repaired_files[rel_path] = required_art.default_content
                diagnostics.append(f"[Repair] Criado ficheiro obrigatório em falta: {rel_path}")
            else:
                # 2. Verificar contratos funcionais no ficheiro existente
                content = repaired_files[existing_match]
                missing_contracts = [
                    c for c in required_art.functional_contracts
                    if c not in content
                ]
                if missing_contracts:
                    repaired_content = self._patch_contracts(
                        existing_match,
                        content,
                        missing_contracts,
                        required_art.default_content,
                    )
                    if repaired_content != content:
                        repaired_files[existing_match] = repaired_content
                        for mc in missing_contracts:
                            actions.append(RepairAction(
                                action_type="PATCH_FILE",
                                relative_path=existing_match,
                                reason=f"Injeção de contrato funcional ausente: '{mc}'",
                                content=repaired_content,
                                contract_applied=mc,
                            ))
                        diagnostics.append(f"[Repair] Ficheiro '{existing_match}' corrigido com contratos: {', '.join(missing_contracts)}")
                    else:
                        unresolved_contracts.extend(missing_contracts)

        # 3. Resolução e Injeção Automática de Dependências (Fase 9.3)
        deps = self.dependency_scanner.scan(repaired_files)

        # Injeção de CDN no index.html (se for web app e tiver tags CDN necessárias)
        html_key = self._find_matching_path("index.html", repaired_files)
        if html_key and deps.cdn_tags:
            html_content = repaired_files[html_key]
            tags_to_inject = [t for t in deps.cdn_tags if t not in html_content]
            if tags_to_inject:
                patched_html = self._inject_cdn_tags(html_content, tags_to_inject)
                if patched_html != html_content:
                    repaired_files[html_key] = patched_html
                    actions.append(RepairAction(
                        action_type="PATCH_FILE",
                        relative_path=html_key,
                        reason=f"Injeção automática de bibliotecas CDN: {len(tags_to_inject)} tag(s)",
                        content=patched_html,
                    ))
                    diagnostics.append(f"[Repair] Injetadas {len(tags_to_inject)} tag(s) CDN em '{html_key}'")

        # Geração ou Atualização de requirements.txt para Python
        if deps.pip_packages:
            req_key = self._find_matching_path("requirements.txt", repaired_files)
            if not req_key:
                req_content = "\n".join(sorted(deps.pip_packages)) + "\n"
                repaired_files["requirements.txt"] = req_content
                actions.append(RepairAction(
                    action_type="CREATE_FILE",
                    relative_path="requirements.txt",
                    reason=f"Criação automática de requirements.txt com dependências detetadas: {', '.join(deps.pip_packages)}",
                    content=req_content,
                ))
                diagnostics.append(f"[Repair] Criado requirements.txt com {len(deps.pip_packages)} pacote(s)")
            else:
                current_reqs = repaired_files[req_key]
                missing_pips = [p for p in deps.pip_packages if p.split(">=")[0] not in current_reqs]
                if missing_pips:
                    patched_reqs = current_reqs.rstrip() + "\n" + "\n".join(missing_pips) + "\n"
                    repaired_files[req_key] = patched_reqs
                    actions.append(RepairAction(
                        action_type="PATCH_FILE",
                        relative_path=req_key,
                        reason=f"Atualização de requirements.txt com pacotes ausentes: {', '.join(missing_pips)}",
                        content=patched_reqs,
                    ))
                    diagnostics.append(f"[Repair] Adicionados {len(missing_pips)} pacote(s) a requirements.txt")

        # Atualização de package.json se dependências npm foram descobertas
        if deps.npm_packages:
            pkg_key = self._find_matching_path("package.json", repaired_files)
            if pkg_key:
                try:
                    pkg_data = json.loads(repaired_files[pkg_key])
                    existing_deps = pkg_data.get("dependencies", {})
                    modified = False
                    for npkg, nver in deps.npm_packages.items():
                        if npkg not in existing_deps:
                            existing_deps[npkg] = nver
                            modified = True
                    if modified:
                        pkg_data["dependencies"] = existing_deps
                        new_pkg_content = json.dumps(pkg_data, indent=2)
                        repaired_files[pkg_key] = new_pkg_content
                        actions.append(RepairAction(
                            action_type="PATCH_FILE",
                            relative_path=pkg_key,
                            reason=f"Sincronização de dependências npm em package.json",
                            content=new_pkg_content,
                        ))
                        diagnostics.append(f"[Repair] Sincronizadas dependências em package.json")
                except Exception:
                    pass

        repaired = len(actions) > 0
        return RepairResult(
            repaired=repaired,
            actions=actions,
            repaired_files=repaired_files,
            diagnostics=diagnostics,
            missing_before=missing_before,
            unresolved_contracts=unresolved_contracts,
        )

    def _find_matching_path(self, target_path: str, files: dict[str, str]) -> Optional[str]:
        target_norm = target_path.replace("\\", "/").strip().lstrip("./")
        if target_norm in files:
            return target_norm

        target_name = Path(target_norm).name.lower()
        for f in files:
            f_norm = f.replace("\\", "/").strip().lstrip("./")
            f_name = Path(f_norm).name.lower()

            if f_name == target_name:
                return f

            # Aliases
            if target_name in ("styles.css", "style.css") and f_name in ("styles.css", "style.css", "main.css", "app.css"):
                return f
            if target_name in ("app.js", "main.js", "index.js") and f_name in ("app.js", "main.js", "index.js", "script.js"):
                return f
            if target_name in ("server.py", "backend.py", "app.py") and f_name in ("server.py", "backend.py", "app.py", "main.py"):
                return f

        return None

    def _patch_contracts(self, filename: str, current_content: str, missing_contracts: list[str], fallback_content: str) -> str:
        patched = current_content
        ext = Path(filename).suffix.lower()

        # Se o ficheiro estiver quase vazio, usar o fallback completo
        if len(current_content.strip()) < 20:
            return fallback_content

        if ext in (".html", ".htm"):
            if "<!DOCTYPE html>" in missing_contracts and "<!DOCTYPE html>" not in patched:
                patched = "<!DOCTYPE html>\n" + patched
            if "<script" in missing_contracts and "<script" not in patched:
                if "</body>" in patched:
                    patched = patched.replace("</body>", "    <script src=\"app.js\"></script>\n</body>")
                else:
                    patched += "\n<script src=\"app.js\"></script>"
            if "<link rel=\"stylesheet\"" in missing_contracts or "styles.css" in missing_contracts:
                if "</head>" in patched:
                    patched = patched.replace("</head>", "    <link rel=\"stylesheet\" href=\"styles.css\">\n</head>")

        elif ext in (".js", ".mjs", ".ts"):
            if "localStorage" in missing_contracts and "localStorage" not in patched:
                storage_helpers = """
// Deterministic Storage Helper
function loadStoredState(key, fallback = []) {
    try { const raw = localStorage.getItem(key); return raw ? JSON.parse(raw) : fallback; } catch { return fallback; }
}
function saveStoredState(key, data) {
    try { localStorage.setItem(key, JSON.stringify(data)); } catch (e) { console.error(e); }
}
"""
                patched = storage_helpers + "\n" + patched

        elif ext == ".py":
            if "/health" in missing_contracts and "/health" not in patched:
                # Injetar rota health caso falte
                if "do_GET" in patched:
                    patched = patched.replace("def do_GET(self):", "def do_GET(self):\n        if self.path == '/health':\n            self.send_response(200)\n            self.send_header('Content-Type', 'application/json')\n            self.end_headers()\n            self.wfile.write(b'{\"status\": \"ok\"}')\n            return")

        return patched

    def _inject_cdn_tags(self, html: str, cdn_tags: list[str]) -> str:
        """Injeta tags de CDN no <head> do HTML de forma não-destrutiva."""
        injection = "\n    " + "\n    ".join(cdn_tags)
        if "</head>" in html:
            return html.replace("</head>", f"{injection}\n</head>")
        elif "<head>" in html:
            return html.replace("<head>", f"<head>{injection}")
        elif "<body" in html:
            idx = html.find("<body")
            return html[:idx] + f"<head>{injection}\n</head>\n" + html[idx:]
        else:
            return f"<head>{injection}\n</head>\n" + html
