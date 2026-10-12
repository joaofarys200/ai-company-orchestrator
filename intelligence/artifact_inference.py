"""
JARVIS OS - Architecture-Aware Artifact Inference & Deterministic Repair Engine (Fase 9.2)

Implementa o Princípio Arquitetural: CAPABILITY-BASED, ARCHITECTURE-AWARE, NÃO TEMPLATE-DRIVEN.

Pipeline formal:
PROMPT + PROJECT CONTEXT + PROJECT INTAKE + DETECTED STACK + DETECTED FRAMEWORK +
EXISTING FILE TREE + EXISTING ENTRYPOINTS + BUILD SYSTEM + RUNTIME
-> ARCHITECTURE MODEL (ProjectArchitecture)
-> CAPABILITIES (CapabilityDetector)
-> ARTIFACT RESPONSIBILITIES
-> RESOLVED ARTIFACTS (InferredArtifact)
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import asdict, dataclass, field
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
class ProjectArchitecture:
    """Modelo explícito da arquitetura técnica do projeto."""
    architecture_id: str
    stack: str
    framework: str = "none"
    bundler: str = "none"
    runtime: str = "unknown"  # 'browser', 'node', 'python', 'fullstack', 'unknown'
    package_manager: str = "npm"
    frontend_entrypoints: list[str] = field(default_factory=list)
    backend_entrypoints: list[str] = field(default_factory=list)
    style_system: str = "none"
    source_root: str = "."
    app_root: str = "."
    conventions: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    evidence: list[str] = field(default_factory=list)
    is_existing: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ArchitectureDecision:
    """Decisão arquitetural formal e explícita do JARVIS."""
    detected: bool = False
    architecture: str = "vanilla_web"
    confidence: float = 1.0
    evidence: list[str] = field(default_factory=list)
    source: str = "default_architecture"  # "existing_project" ou "default_architecture"

    # Campos de compatibilidade com ProductDeliveryGate e relatórios
    selected_stack: str = ""
    rationale: str = ""
    capabilities_expected: list[str] = field(default_factory=list)
    inferred_by: str = ""
    inferred_artifacts: list[str] = field(default_factory=list)
    is_new_project: bool = False
    framework: str = ""
    bundler: str = ""
    runtime: str = "unknown"
    entrypoints: dict[str, list[str]] = field(default_factory=dict)
    conventions: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.selected_stack:
            self.selected_stack = self.architecture
        elif not self.architecture and self.selected_stack:
            self.architecture = self.selected_stack

        if not self.inferred_by:
            self.inferred_by = self.source
        elif not self.source and self.inferred_by:
            self.source = self.inferred_by

        if not self.rationale:
            self.rationale = f"Arquitetura selecionada: {self.architecture} via {self.source} (confiança: {self.confidence:.2f})"

        self.is_new_project = not self.detected

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InferredArtifact:
    """
    Especificação de artefacto orientada por responsabilidade, stack e contratos funcionais.
    """
    artifact_id: str = ""
    responsibility: str = ""
    category: str = "frontend"
    architecture: str = "generic"
    source: str = "inferred"  # "existing_project", "default_architecture", "inferred"
    required: bool = True
    existing: bool = False
    candidate_paths: list[str] = field(default_factory=list)
    functional_contracts: list[str] = field(default_factory=list)
    evidence_requirements: list[str] = field(default_factory=list)

    # Campos de compatibilidade para retrocompatibilidade
    relative_path: str = ""
    component: str = ""
    description: str = ""
    default_content: str = ""

    def __post_init__(self):
        if not self.relative_path and self.candidate_paths:
            self.relative_path = self.candidate_paths[0]
        elif self.relative_path and not self.candidate_paths:
            self.candidate_paths = [self.relative_path]

        if not self.category and self.component:
            self.category = self.component
        elif not self.component and self.category:
            self.component = self.category

        if not self.artifact_id:
            stem = Path(self.relative_path).stem if self.relative_path else "artifact"
            self.artifact_id = f"{self.category}-{stem}"

        if not self.responsibility:
            self.responsibility = self.description or f"Responsabilidade para {self.artifact_id}"

        if not self.description:
            self.description = self.responsibility


@dataclass
class CapabilityInferenceResult:
    prompt: str
    detected_capabilities: set[Capability]
    required_artifacts: list[InferredArtifact]
    entrypoints: list[str]
    contracts_by_file: dict[str, list[str]] = field(default_factory=dict)
    diagnostics: list[str] = field(default_factory=list)
    architecture: Optional[ProjectArchitecture] = None
    architecture_decision: Optional[ArchitectureDecision] = None
    mismatches: list[str] = field(default_factory=list)

    def has_capability(self, capability: Capability | str) -> bool:
        cap_val = Capability(capability) if isinstance(capability, str) else capability
        return cap_val in self.detected_capabilities

    def get_artifact(self, relative_path: str) -> Optional[InferredArtifact]:
        normalized = relative_path.replace("\\", "/").strip().lstrip("./").lower()
        for art in self.required_artifacts:
            art_norm = art.relative_path.replace("\\", "/").strip().lstrip("./").lower()
            if art_norm == normalized or any(c.replace("\\", "/").strip().lstrip("./").lower() == normalized for c in art.candidate_paths):
                return art
        return None

    def get_by_responsibility(self, responsibility_substring: str) -> list[InferredArtifact]:
        sub = responsibility_substring.lower()
        return [art for art in self.required_artifacts if sub in art.responsibility.lower() or sub in art.artifact_id.lower()]

    def required_paths(self) -> list[str]:
        return [art.relative_path for art in self.required_artifacts if art.required]


@dataclass
class RepairAction:
    action_type: str  # "CREATE_FILE", "PATCH_FILE", "REMOVE_MISMATCH", "INJECT_CONTRACT"
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
    architecture: Optional[ProjectArchitecture] = None


def normalize_text(text: str) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    without_accents = "".join(c for c in normalized if not unicodedata.combining(c))
    return without_accents.lower().strip()


def detect_architecture_mismatch(
    files: dict[str, str] | list[str],
    architecture: ProjectArchitecture,
) -> list[str]:
    """
    Deteta ficheiros que violam a arquitetura estabelecida do projeto (STACK MISMATCH).
    Exemplo: LLM introduz 'app.js' ou 'styles.css' de template num projeto React/Vite.
    """
    file_list = list(files.keys()) if isinstance(files, dict) else list(files)
    normalized = [f.replace("\\", "/").strip().lstrip("./") for f in file_list]
    mismatches: list[str] = []

    if architecture.stack == "react_vite":
        for f in normalized:
            f_lower = f.lower()
            if f_lower == "app.js":
                mismatches.append(
                    f"ARTIFACT_ARCHITECTURE_MISMATCH: 'app.js' é um template vanilla incompatível com a stack React/Vite ('src/App.tsx', 'src/main.tsx')."
                )
            elif f_lower == "styles.css" and any(rf.startswith("src/") for rf in normalized):
                mismatches.append(
                    f"ARTIFACT_ARCHITECTURE_MISMATCH: 'styles.css' na raiz conflita com a convenção de estilos React ('src/index.css' / 'src/App.css')."
                )
            elif f_lower == "search.js":
                mismatches.append(
                    f"ARTIFACT_ARCHITECTURE_MISMATCH: 'search.js' incompatível com projeto React/TypeScript. Deve ser um componente TSX."
                )

    elif architecture.stack == "nextjs":
        for f in normalized:
            f_lower = f.lower()
            if f_lower == "index.html":
                mismatches.append(
                    f"ARTIFACT_ARCHITECTURE_MISMATCH: 'index.html' é proibido no modelo App Router do Next.js (use 'app/layout.tsx' e 'app/page.tsx')."
                )
            elif f_lower in ("app.js", "main.js"):
                mismatches.append(
                    f"ARTIFACT_ARCHITECTURE_MISMATCH: '{f}' é incompatível com o modelo de rotas e componentes do Next.js."
                )

    elif architecture.stack in ("python_fastapi", "python_flask", "custom_python"):
        # Se for backend puro sem frontend solicitado
        if not architecture.frontend_entrypoints:
            for f in normalized:
                if f.lower() in ("index.html", "app.js", "styles.css"):
                    mismatches.append(
                        f"ARTIFACT_ARCHITECTURE_MISMATCH: Artefacto frontend '{f}' incompatível com backend Python puro."
                    )

    elif architecture.stack in ("node_express", "node_typescript"):
        for f in normalized:
            if f.lower() in ("server.py", "database.py"):
                mismatches.append(
                    f"ARTIFACT_ARCHITECTURE_MISMATCH: '{f}' incompatível com runtime Node/TypeScript."
                )

    return mismatches


class CapabilityDetector:
    """
    Deteta de forma determinística capacidades a partir de prompts e contexto.
    Suporta análise multilíngue (Português e Inglês), termos canónicos e exclusões.
    """

    CAPABILITY_PATTERNS: dict[Capability, list[re.Pattern]] = {
        Capability.FRONTEND: [
            re.compile(r"\b(pagina|site|website|web\s*app|frontend|interface|ui|html|css|ecra|tela|layout|view|react|vue|vanilla|browser|navegador|landing|portal|formulario)\b"),
            re.compile(r"\b(web\s*page|front\s*end|webpage|user\s*interface|landing\s*page)\b"),
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

        if Capability.CRUD in detected and Capability.FRONTEND not in detected and Capability.BACKEND not in detected and Capability.CLI not in detected:
            detected.add(Capability.FRONTEND)

        if Capability.DASHBOARD in detected and Capability.FRONTEND not in detected:
            detected.add(Capability.FRONTEND)

        if Capability.SEARCH in detected and Capability.FRONTEND not in detected and Capability.BACKEND not in detected:
            detected.add(Capability.FRONTEND)

        if (Capability.FRONTEND in detected or Capability.BACKEND in detected) and Capability.PREVIEW not in detected:
            detected.add(Capability.PREVIEW)

        if Capability.CRUD in detected and Capability.STORAGE not in detected and "sem persistencia" not in norm and "sem guardar" not in norm:
            detected.add(Capability.STORAGE)

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

        if project_context:
            files = project_context.get("files", [])
            file_names = [f.lower() for f in files] if isinstance(files, list) else [k.lower() for k in files.keys()]
            if any(f.endswith((".html", ".tsx", ".jsx", ".vue")) for f in file_names):
                detected.add(Capability.FRONTEND)
            if any("server.py" in f or "app.py" in f or "main.py" in f or "server.js" in f or "server.ts" in f for f in file_names):
                detected.add(Capability.BACKEND)

        is_single_file = bool(re.search(r"\b(cria|criar|make|write)\s+[a-z0-9_\-]+\.(txt|md|py|sh|json|csv|yaml|yml|js|ts)\b", norm))
        if is_single_file:
            if not any(w in norm for w in ["site", "website", "pagina", "web app", "frontend", "html", "react", "vue"]):
                detected.discard(Capability.FRONTEND)
                detected.discard(Capability.PREVIEW)
        elif not detected and any(re.search(rf"\b{w}\b", norm) for w in ["app", "aplicacao", "site", "web", "pagina", "ui", "painel", "dashboard", "frontend", "jogo", "game", "landing", "portal"]):
            detected.add(Capability.FRONTEND)
            detected.add(Capability.PREVIEW)

        return detected


class ProjectIntakeArchitectureDetector:
    """
    Analisa os artefactos e a estrutura real do projeto existente (Princípio: EXISTING ARCHITECTURE FIRST).
    Inspeciona:
    1. package.json, scripts de build/dev, dependências e devDependencies
    2. lockfiles (package-lock, yarn, pnpm, bun)
    3. requirements.txt / pyproject.toml
    4. tsconfig.json
    5. vite.config.*, next.config.*
    6. estrutura de pastas src/, app/, pages/, backend/, api/, server/
    7. entrypoints reais e runtime
    """

    IGNORE_DIRS = {
        "node_modules", ".git", ".gemini", "dist", "build", ".next",
        "__pycache__", ".pytest_cache", ".venv", "venv", ".idea", ".vscode"
    }

    @classmethod
    def detect_or_choose(
        cls,
        prompt: str,
        files: Optional[dict[str, str] | list[str]] = None,
        project_root: Optional[str] = None,
        project_context: Optional[dict[str, Any]] = None,
    ) -> Tuple[ProjectArchitecture, ArchitectureDecision]:
        existing_files: dict[str, str] = {}

        if project_root and os.path.exists(project_root):
            for root, dirs, f_names in os.walk(project_root):
                dirs[:] = [d for d in dirs if d not in cls.IGNORE_DIRS]
                for fn in f_names:
                    full_p = os.path.join(root, fn)
                    rel = os.path.relpath(full_p, project_root).replace("\\", "/")
                    try:
                        # Ler ficheiros de texto para inspeção arquitetural
                        if os.path.getsize(full_p) < 500_000:
                            existing_files[rel] = Path(full_p).read_text(encoding="utf-8", errors="ignore")
                        else:
                            existing_files[rel] = ""
                    except Exception:
                        existing_files[rel] = ""

        if files:
            if isinstance(files, dict):
                existing_files.update(files)
            elif isinstance(files, list):
                for f in files:
                    if f not in existing_files:
                        existing_files[f] = ""

        if project_context:
            ctx_files = project_context.get("files")
            if isinstance(ctx_files, dict):
                existing_files.update(ctx_files)
            elif isinstance(ctx_files, list):
                for f in ctx_files:
                    if f not in existing_files:
                        existing_files[f] = ""

        # Filtrar ficheiros triviais
        meaningful_files = [
            f for f in existing_files.keys()
            if not f.startswith(".") and f not in ("README.md", ".gitignore", ".gitkeep")
        ]

        if meaningful_files:
            return cls._detect_existing(existing_files)
        else:
            return cls._choose_default_architecture(prompt)

    @classmethod
    def _detect_existing(cls, files: dict[str, str]) -> Tuple[ProjectArchitecture, ArchitectureDecision]:
        file_set = set(f.replace("\\", "/").strip().lstrip("./") for f in files.keys())
        file_map = {f.lower(): f for f in file_set}
        evidence: list[str] = []

        # 1. Package.json analysis
        pkg_json_content = files.get("package.json") or files.get("./package.json")
        pkg_data: dict[str, Any] = {}
        all_deps: dict[str, str] = {}
        scripts: dict[str, str] = {}
        package_manager = "npm"

        if pkg_json_content:
            try:
                pkg_data = json.loads(pkg_json_content)
                all_deps.update(pkg_data.get("dependencies", {}))
                all_deps.update(pkg_data.get("devDependencies", {}))
                scripts = pkg_data.get("scripts", {})
                evidence.append(f"package.json detetado com {len(all_deps)} dependências")
            except Exception:
                pass

        # Lockfiles
        if "bun.lockb" in file_set:
            package_manager = "bun"
            evidence.append("bun.lockb detetado")
        elif "pnpm-lock.yaml" in file_set:
            package_manager = "pnpm"
            evidence.append("pnpm-lock.yaml detetado")
        elif "yarn.lock" in file_set:
            package_manager = "yarn"
            evidence.append("yarn.lock detetado")
        elif "package-lock.json" in file_set:
            package_manager = "npm"
            evidence.append("package-lock.json detetado")

        # Configs
        has_tsconfig = any(f.startswith("tsconfig") for f in file_set)
        has_vite_config = any("vite.config" in f for f in file_set)
        has_next_config = any("next.config" in f for f in file_set)
        has_tailwind = any("tailwind.config" in f for f in file_set) or "tailwindcss" in all_deps

        # Python manifests
        py_files = [f for f in file_set if f.endswith(".py")]
        py_deps: list[str] = []
        for req_f in ("requirements.txt", "pyproject.toml", "Pipfile"):
            if req_f in files:
                evidence.append(f"Manifesto Python detetado: {req_f}")
                content = files[req_f].lower()
                for mod in ("fastapi", "uvicorn", "flask", "django", "sqlalchemy", "requests"):
                    if mod in content:
                        py_deps.append(mod)

        # Style System
        style_system = "vanilla_css"
        if has_tailwind:
            style_system = "tailwind"
        elif any(f.endswith(".module.css") for f in file_set):
            style_system = "css_modules"

        # Check Next.js
        is_next = (
            "next" in all_deps
            or has_next_config
            or any(f.startswith("app/") or f.startswith("pages/") for f in file_set)
            and any(f.endswith((".tsx", ".jsx")) for f in file_set)
        )
        if is_next:
            fe = [f for f in file_set if f in ("app/page.tsx", "app/page.jsx", "app/layout.tsx", "pages/index.tsx", "pages/_app.tsx")]
            be = [f for f in file_set if f.startswith("app/api/") or f.startswith("pages/api/")]
            evidence.append("Estrutura Next.js identificada (App/Pages Router)")
            arch = ProjectArchitecture(
                architecture_id="nextjs",
                stack="nextjs",
                framework="Next.js",
                bundler="Next.js",
                runtime="node",
                package_manager=package_manager,
                frontend_entrypoints=fe or ["app/page.tsx"],
                backend_entrypoints=be,
                style_system=style_system,
                source_root="app" if any(f.startswith("app/") for f in file_set) else "pages",
                app_root="app" if any(f.startswith("app/") for f in file_set) else "pages",
                conventions={"typescript": has_tsconfig, "app_router": any(f.startswith("app/") for f in file_set)},
                confidence=0.98,
                evidence=evidence,
                is_existing=True,
            )
            decision = ArchitectureDecision(
                detected=True,
                architecture="nextjs",
                confidence=0.98,
                evidence=evidence,
                source="existing_project",
                framework="Next.js",
                bundler="Next.js",
                runtime="node",
            )
            return arch, decision

        # Check React / Vite
        is_react = (
            "react" in all_deps
            or has_vite_config
            or any(f.endswith((".tsx", ".jsx")) for f in file_set)
            or any(f in ("src/App.tsx", "src/App.jsx", "src/main.tsx", "src/main.jsx") for f in file_set)
        )
        if is_react:
            fe = [f for f in file_set if f in ("src/main.tsx", "src/main.jsx", "src/App.tsx", "src/App.jsx", "src/index.tsx", "index.html")]
            evidence.append("Estrutura React (Vite / SPA) identificada em src/")
            arch = ProjectArchitecture(
                architecture_id="react_vite",
                stack="react_vite",
                framework="React",
                bundler="vite" if has_vite_config or "vite" in all_deps else "bundler",
                runtime="browser",
                package_manager=package_manager,
                frontend_entrypoints=fe or ["src/App.tsx", "src/main.tsx"],
                backend_entrypoints=[],
                style_system=style_system,
                source_root="src",
                app_root="src",
                conventions={"typescript": has_tsconfig or any(f.endswith(".tsx") for f in file_set)},
                confidence=0.97,
                evidence=evidence,
                is_existing=True,
            )
            decision = ArchitectureDecision(
                detected=True,
                architecture="react_vite",
                confidence=0.97,
                evidence=evidence,
                source="existing_project",
                framework="React",
                bundler="vite",
                runtime="browser",
            )
            return arch, decision

        # Check Vue / Vite
        is_vue = (
            "vue" in all_deps
            or any(f.endswith(".vue") for f in file_set)
            or "src/App.vue" in file_set
        )
        if is_vue:
            fe = [f for f in file_set if f in ("src/App.vue", "src/main.js", "src/main.ts", "index.html")]
            evidence.append("Estrutura Vue (Vite / Single File Components) identificada")
            arch = ProjectArchitecture(
                architecture_id="vue_vite",
                stack="vue_vite",
                framework="Vue",
                bundler="vite",
                runtime="browser",
                package_manager=package_manager,
                frontend_entrypoints=fe or ["src/App.vue", "src/main.js"],
                backend_entrypoints=[],
                style_system=style_system,
                source_root="src",
                app_root="src",
                conventions={"single_file_components": True},
                confidence=0.96,
                evidence=evidence,
                is_existing=True,
            )
            decision = ArchitectureDecision(
                detected=True,
                architecture="vue_vite",
                confidence=0.96,
                evidence=evidence,
                source="existing_project",
                framework="Vue",
                bundler="vite",
                runtime="browser",
            )
            return arch, decision

        # Check Python FastAPI
        is_fastapi = "fastapi" in py_deps or any("fastapi" in files.get(f, "").lower() for f in py_files)
        if is_fastapi:
            be = [f for f in py_files if f in ("main.py", "app.py", "server.py", "backend/main.py", "api/main.py")]
            evidence.append("Servidor Python FastAPI identificado")
            arch = ProjectArchitecture(
                architecture_id="python_fastapi",
                stack="python_fastapi",
                framework="FastAPI",
                bundler="none",
                runtime="python",
                package_manager="pip",
                frontend_entrypoints=[],
                backend_entrypoints=be or ["main.py"],
                style_system="none",
                source_root="." if "main.py" in file_set else "backend",
                app_root=".",
                conventions={"framework": "FastAPI", "asgi": "uvicorn"},
                confidence=0.96,
                evidence=evidence,
                is_existing=True,
            )
            decision = ArchitectureDecision(
                detected=True,
                architecture="python_fastapi",
                confidence=0.96,
                evidence=evidence,
                source="existing_project",
                framework="FastAPI",
                runtime="python",
            )
            return arch, decision

        # Check Node / Express / TypeScript
        is_node_express = (
            "express" in all_deps
            or any("express" in files.get(f, "").lower() for f in file_set if f.endswith((".js", ".ts")))
        )
        if is_node_express:
            be = [f for f in file_set if f in ("src/server.ts", "src/index.ts", "server.ts", "server.js", "app.js")]
            evidence.append("Backend Node/Express identificado")
            arch = ProjectArchitecture(
                architecture_id="node_express",
                stack="node_express",
                framework="Express",
                bundler="tsc" if has_tsconfig else "none",
                runtime="node",
                package_manager=package_manager,
                frontend_entrypoints=[],
                backend_entrypoints=be or ["server.js"],
                style_system="none",
                source_root="src" if any(f.startswith("src/") for f in file_set) else ".",
                app_root=".",
                conventions={"typescript": has_tsconfig},
                confidence=0.95,
                evidence=evidence,
                is_existing=True,
            )
            decision = ArchitectureDecision(
                detected=True,
                architecture="node_express",
                confidence=0.95,
                evidence=evidence,
                source="existing_project",
                framework="Express",
                runtime="node",
            )
            return arch, decision

        # Check Vanilla Web
        is_vanilla = "index.html" in file_set or any(f in file_set for f in ("styles.css", "style.css", "app.js", "main.js"))
        if is_vanilla:
            fe = [f for f in ("index.html", "styles.css", "style.css", "app.js", "main.js") if f in file_set]
            evidence.append("Estrutura Vanilla Web identificada")
            arch = ProjectArchitecture(
                architecture_id="vanilla_web",
                stack="vanilla_web",
                framework="none",
                bundler="none",
                runtime="browser",
                package_manager="none",
                frontend_entrypoints=fe,
                backend_entrypoints=[],
                style_system="vanilla_css",
                source_root=".",
                app_root=".",
                conventions={"static_html": True},
                confidence=0.95,
                evidence=evidence,
                is_existing=True,
            )
            decision = ArchitectureDecision(
                detected=True,
                architecture="vanilla_web",
                confidence=0.95,
                evidence=evidence,
                source="existing_project",
                framework="none",
                runtime="browser",
            )
            return arch, decision

        # Check Generic Python
        if py_files:
            be = [f for f in py_files if f in ("main.py", "app.py", "server.py")]
            evidence.append("Ficheiros Python identificados no projeto")
            arch = ProjectArchitecture(
                architecture_id="custom_python",
                stack="custom_python",
                framework="python",
                bundler="none",
                runtime="python",
                package_manager="pip",
                frontend_entrypoints=[],
                backend_entrypoints=be or py_files[:1],
                style_system="none",
                source_root=".",
                app_root=".",
                conventions={"python_native": True},
                confidence=0.90,
                evidence=evidence,
                is_existing=True,
            )
            decision = ArchitectureDecision(
                detected=True,
                architecture="custom_python",
                confidence=0.90,
                evidence=evidence,
                source="existing_project",
                runtime="python",
            )
            return arch, decision

        # Fallback Custom Existing
        evidence.append("Projeto existente com convenções próprias")
        arch = ProjectArchitecture(
            architecture_id="custom",
            stack="custom",
            framework="custom",
            bundler="unknown",
            runtime="unknown",
            package_manager="unknown",
            frontend_entrypoints=[f for f in file_set if f.endswith((".html", ".js", ".ts"))][:2],
            backend_entrypoints=[f for f in file_set if f.endswith(".py")][:1],
            style_system="unknown",
            source_root=".",
            app_root=".",
            conventions={"custom_layout": True},
            confidence=0.85,
            evidence=evidence,
            is_existing=True,
        )
        decision = ArchitectureDecision(
            detected=True,
            architecture="custom",
            confidence=0.85,
            evidence=evidence,
            source="existing_project",
        )
        return arch, decision

    @classmethod
    def _choose_default_architecture(cls, prompt: str) -> Tuple[ProjectArchitecture, ArchitectureDecision]:
        """
        Para projeto completamente vazio:
        JARVIS escolhe arquitetura padrão com base nos requisitos do prompt, complexidade e runtime.
        NUNCA escolhe de forma silenciosa.
        """
        norm = normalize_text(prompt)
        evidence: list[str] = []

        if any(w in norm for w in ("nextjs", "next.js", "next", "app router")):
            evidence.append("Requisito explícito de Next.js detetado no prompt")
            arch = ProjectArchitecture(
                architecture_id="nextjs",
                stack="nextjs",
                framework="Next.js",
                bundler="Next.js",
                runtime="node",
                package_manager="npm",
                frontend_entrypoints=["app/page.tsx", "app/layout.tsx"],
                backend_entrypoints=["app/api/health/route.ts"],
                style_system="tailwind",
                source_root="app",
                app_root="app",
                conventions={"typescript": True, "app_router": True},
                confidence=0.92,
                evidence=evidence,
                is_existing=False,
            )
            decision = ArchitectureDecision(
                detected=False,
                architecture="nextjs",
                confidence=0.92,
                evidence=evidence,
                source="default_architecture",
                framework="Next.js",
                bundler="Next.js",
                runtime="node",
            )
            return arch, decision

        if any(w in norm for w in ("react", "vite", "tsx", "jsx", "componentes react")):
            evidence.append("Requisito de React / Vite detetado no prompt")
            arch = ProjectArchitecture(
                architecture_id="react_vite",
                stack="react_vite",
                framework="React",
                bundler="vite",
                runtime="browser",
                package_manager="npm",
                frontend_entrypoints=["src/App.tsx", "src/main.tsx", "index.html"],
                backend_entrypoints=[],
                style_system="vanilla_css",
                source_root="src",
                app_root="src",
                conventions={"typescript": True},
                confidence=0.94,
                evidence=evidence,
                is_existing=False,
            )
            decision = ArchitectureDecision(
                detected=False,
                architecture="react_vite",
                confidence=0.94,
                evidence=evidence,
                source="default_architecture",
                framework="React",
                bundler="vite",
                runtime="browser",
            )
            return arch, decision

        if any(w in norm for w in ("vue", "vuejs", "vue3", "pinia")):
            evidence.append("Requisito de Vue 3 detetado no prompt")
            arch = ProjectArchitecture(
                architecture_id="vue_vite",
                stack="vue_vite",
                framework="Vue",
                bundler="vite",
                runtime="browser",
                package_manager="npm",
                frontend_entrypoints=["src/App.vue", "src/main.js"],
                backend_entrypoints=[],
                style_system="vanilla_css",
                source_root="src",
                app_root="src",
                conventions={"single_file_components": True},
                confidence=0.92,
                evidence=evidence,
                is_existing=False,
            )
            decision = ArchitectureDecision(
                detected=False,
                architecture="vue_vite",
                confidence=0.92,
                evidence=evidence,
                source="default_architecture",
                framework="Vue",
                bundler="vite",
                runtime="browser",
            )
            return arch, decision

        if any(w in norm for w in ("fastapi", "uvicorn", "python api", "backend python")):
            evidence.append("Requisito de API backend em Python FastAPI detetado no prompt")
            arch = ProjectArchitecture(
                architecture_id="python_fastapi",
                stack="python_fastapi",
                framework="FastAPI",
                bundler="none",
                runtime="python",
                package_manager="pip",
                frontend_entrypoints=[],
                backend_entrypoints=["main.py"],
                style_system="none",
                source_root=".",
                app_root=".",
                conventions={"framework": "FastAPI"},
                confidence=0.92,
                evidence=evidence,
                is_existing=False,
            )
            decision = ArchitectureDecision(
                detected=False,
                architecture="python_fastapi",
                confidence=0.92,
                evidence=evidence,
                source="default_architecture",
                framework="FastAPI",
                runtime="python",
            )
            return arch, decision

        if any(w in norm for w in ("express", "nodejs server", "backend node")):
            evidence.append("Requisito de backend Node Express detetado no prompt")
            arch = ProjectArchitecture(
                architecture_id="node_express",
                stack="node_express",
                framework="Express",
                bundler="none",
                runtime="node",
                package_manager="npm",
                frontend_entrypoints=[],
                backend_entrypoints=["src/server.ts"],
                style_system="none",
                source_root="src",
                app_root=".",
                conventions={"typescript": True},
                confidence=0.91,
                evidence=evidence,
                is_existing=False,
            )
            decision = ArchitectureDecision(
                detected=False,
                architecture="node_express",
                confidence=0.91,
                evidence=evidence,
                source="default_architecture",
                framework="Express",
                runtime="node",
            )
            return arch, decision

        # Pure python CLI / script
        if any(w in norm for w in ("script", "cli", "terminal", "python")) and not any(w in norm for w in ("web", "site", "pagina", "html", "interface", "app")):
            evidence.append("Requisito de CLI / Script Python sem frontend detetado")
            arch = ProjectArchitecture(
                architecture_id="custom_python",
                stack="custom_python",
                framework="python",
                bundler="none",
                runtime="python",
                package_manager="pip",
                frontend_entrypoints=[],
                backend_entrypoints=["main.py"],
                style_system="none",
                source_root=".",
                app_root=".",
                conventions={"cli": True},
                confidence=0.90,
                evidence=evidence,
                is_existing=False,
            )
            decision = ArchitectureDecision(
                detected=False,
                architecture="custom_python",
                confidence=0.90,
                evidence=evidence,
                source="default_architecture",
                runtime="python",
            )
            return arch, decision

        # Default web application
        evidence.append("Projeto web novo selecionado com arquitetura Vanilla Web responsiva")
        arch = ProjectArchitecture(
            architecture_id="vanilla_web",
            stack="vanilla_web",
            framework="none",
            bundler="none",
            runtime="browser",
            package_manager="none",
            frontend_entrypoints=["index.html", "styles.css", "app.js"],
            backend_entrypoints=[],
            style_system="vanilla_css",
            source_root=".",
            app_root=".",
            conventions={"static_html": True},
            confidence=0.88,
            evidence=evidence,
            is_existing=False,
        )
        decision = ArchitectureDecision(
            detected=False,
            architecture="vanilla_web",
            confidence=0.88,
            evidence=evidence,
            source="default_architecture",
            framework="none",
            runtime="browser",
        )
        return arch, decision


class ArtifactInferenceEngine:
    """
    Motor determinístico de inferência arquitetural de artefactos e capacidades.
    Opera sobre:
    PROMPT + CONTEXTO + ARQUITETURA DETETADA + REQUISITOS -> ARTEFACTOS RESOLVIDOS
    """

    def __init__(
        self,
        detector: Optional[CapabilityDetector] = None,
        architecture_detector: Optional[ProjectIntakeArchitectureDetector] = None,
    ):
        self.detector = detector or CapabilityDetector()
        self.architecture_detector = architecture_detector or ProjectIntakeArchitectureDetector()

    def infer(
        self,
        prompt: str,
        project_name: str = "app",
        project_context: Optional[dict[str, Any]] = None,
        project_root: Optional[str] = None,
        planned_files: Optional[dict[str, str]] = None,
    ) -> CapabilityInferenceResult:
        # 1. EXISTÊNCIA E ARQUITETURA PRIMEIRO
        arch, decision = self.architecture_detector.detect_or_choose(
            prompt=prompt,
            files=planned_files,
            project_root=project_root,
            project_context=project_context,
        )

        # 2. CAPACIDADES
        capabilities = self.detector.detect(prompt, project_context)
        prompt_norm = normalize_text(prompt)
        if arch.frontend_entrypoints and "sem frontend" not in prompt_norm and "without frontend" not in prompt_norm:
            capabilities.add(Capability.FRONTEND)
        if arch.backend_entrypoints and "sem backend" not in prompt_norm and "without backend" not in prompt_norm:
            capabilities.add(Capability.BACKEND)

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

        # Obter ficheiros existentes no projeto para resolução contextual
        existing_files_dict = self._extract_existing_files(project_root, project_context, planned_files)

        # 3. MAPEAMENTO DE CAPACIDADES PARA RESPONSABILIDADES CONFORME A ARQUITETURA
        if is_frontend:
            frontend_arts = self._resolve_frontend_responsibilities(
                arch=arch,
                project_name=project_name,
                capabilities=capabilities,
                existing_files=existing_files_dict,
            )
            for art in frontend_arts:
                artifacts.append(art)
                if art.relative_path:
                    entrypoints.append(art.relative_path)
                    contracts_by_file[art.relative_path] = art.functional_contracts

        if is_backend:
            backend_arts = self._resolve_backend_responsibilities(
                arch=arch,
                project_name=project_name,
                capabilities=capabilities,
                existing_files=existing_files_dict,
            )
            for art in backend_arts:
                artifacts.append(art)
                if art.relative_path:
                    entrypoints.append(art.relative_path)
                    contracts_by_file[art.relative_path] = art.functional_contracts

        if is_storage:
            storage_arts = self._resolve_storage_responsibilities(
                arch=arch,
                capabilities=capabilities,
                existing_files=existing_files_dict,
            )
            for art in storage_arts:
                artifacts.append(art)
                if art.relative_path and art.functional_contracts:
                    contracts_by_file[art.relative_path] = art.functional_contracts

        if is_search and not any(art.artifact_id == "search-feature" for art in artifacts):
            search_arts = self._resolve_search_responsibilities(
                arch=arch,
                existing_files=existing_files_dict,
            )
            for art in search_arts:
                artifacts.append(art)

        if is_dashboard and not any(art.artifact_id == "dashboard-feature" for art in artifacts):
            dash_arts = self._resolve_dashboard_responsibilities(
                arch=arch,
                existing_files=existing_files_dict,
            )
            for art in dash_arts:
                artifacts.append(art)

        # Scaffoldings opcionais (package.json / README)
        if arch.package_manager in ("npm", "yarn", "pnpm", "bun") and "package.json" not in existing_files_dict:
            pkg_content = self._generate_package_json(project_name, capabilities, arch)
            artifacts.append(InferredArtifact(
                artifact_id="project-manifest",
                responsibility="project package manifest and scripts",
                category="scaffolding",
                architecture=arch.stack,
                required=False,
                candidate_paths=["package.json"],
                functional_contracts=["name", "version"],
                relative_path="package.json",
                default_content=pkg_content,
            ))

        # 4. DETEÇÃO DE STACK MISMATCH
        all_eval_files = list(existing_files_dict.keys())
        mismatches = detect_architecture_mismatch(all_eval_files, arch)
        for mm in mismatches:
            diagnostics.append(f"[Mismatch] {mm}")

        diagnostics.append(f"Arquitetura: {arch.stack} (fonte: {decision.source}, confiança: {arch.confidence:.2f})")
        diagnostics.append(f"Capacidades: {', '.join(sorted(c.value for c in capabilities))}")
        diagnostics.append(f"Artefactos obrigatórios: {', '.join(a.relative_path for a in artifacts if a.required)}")

        return CapabilityInferenceResult(
            prompt=prompt,
            detected_capabilities=capabilities,
            required_artifacts=artifacts,
            entrypoints=entrypoints,
            contracts_by_file=contracts_by_file,
            diagnostics=diagnostics,
            architecture=arch,
            architecture_decision=decision,
            mismatches=mismatches,
        )

    def _extract_existing_files(
        self,
        project_root: Optional[str],
        project_context: Optional[dict[str, Any]],
        planned_files: Optional[dict[str, str]],
    ) -> dict[str, str]:
        existing: dict[str, str] = {}
        if project_root and os.path.exists(project_root):
            for root, dirs, f_names in os.walk(project_root):
                dirs[:] = [d for d in dirs if d not in ProjectIntakeArchitectureDetector.IGNORE_DIRS]
                for fn in f_names:
                    rel = os.path.relpath(os.path.join(root, fn), project_root).replace("\\", "/")
                    existing[rel] = ""
        if project_context:
            ctx_files = project_context.get("files")
            if isinstance(ctx_files, dict):
                existing.update(ctx_files)
            elif isinstance(ctx_files, list):
                for f in ctx_files:
                    existing[f] = ""
        if planned_files:
            existing.update(planned_files)
        return existing

    def _match_existing(self, candidate_paths: list[str], existing_files: dict[str, str]) -> Optional[str]:
        for c in candidate_paths:
            c_norm = c.replace("\\", "/").strip().lstrip("./").lower()
            for ef in existing_files:
                ef_norm = ef.replace("\\", "/").strip().lstrip("./").lower()
                if c_norm == ef_norm:
                    return ef
        return None

    # -------------------------------------------------------------------------
    # RESOLUÇÃO ESPECÍFICA POR CAPACIDADE E ARQUITETURA
    # -------------------------------------------------------------------------

    def _resolve_frontend_responsibilities(
        self,
        arch: ProjectArchitecture,
        project_name: str,
        capabilities: set[Capability],
        existing_files: dict[str, str],
    ) -> list[InferredArtifact]:
        arts: list[InferredArtifact] = []

        if arch.stack == "react_vite":
            # 1. Entrypoint React Component
            cand_entry = ["src/App.tsx", "src/App.jsx", "src/main.tsx"]
            matched_entry = self._match_existing(cand_entry, existing_files)
            arts.append(InferredArtifact(
                artifact_id="frontend-entrypoint",
                responsibility="frontend application entrypoint",
                category="frontend",
                architecture="react_vite",
                source="existing_project" if matched_entry else "inferred",
                required=True,
                existing=bool(matched_entry),
                candidate_paths=cand_entry,
                functional_contracts=["export default", "return", "function", "const"],
                evidence_requirements=["exists", "non_empty", "contains_component"],
                relative_path=matched_entry or "src/App.tsx",
                component="frontend",
                description="Componente raiz da aplicação React",
                default_content=self._generate_react_app_skeleton(project_name, capabilities),
            ))

            # 2. Bootstrap Mount
            cand_boot = ["src/main.tsx", "src/main.jsx", "index.html"]
            matched_boot = self._match_existing(cand_boot, existing_files)
            arts.append(InferredArtifact(
                artifact_id="frontend-bootstrap",
                responsibility="frontend bootstrap mount",
                category="frontend",
                architecture="react_vite",
                source="existing_project" if matched_boot else "inferred",
                required=True,
                existing=bool(matched_boot),
                candidate_paths=cand_boot,
                functional_contracts=["createRoot", "render"],
                evidence_requirements=["exists", "non_empty"],
                relative_path=matched_boot or "src/main.tsx",
                component="frontend",
                description="Ponto de montagem React DOM",
                default_content=self._generate_react_main_skeleton(),
            ))

            # 3. Style System
            cand_css = ["src/index.css", "src/App.css", "src/styles.css"]
            matched_css = self._match_existing(cand_css, existing_files)
            arts.append(InferredArtifact(
                artifact_id="frontend-styling",
                responsibility="frontend style system",
                category="frontend",
                architecture="react_vite",
                source="existing_project" if matched_css else "inferred",
                required=True,
                existing=bool(matched_css),
                candidate_paths=cand_css,
                functional_contracts=["body", "box-sizing"],
                evidence_requirements=["exists", "non_empty"],
                relative_path=matched_css or "src/index.css",
                component="frontend",
                description="Folha de estilos principal da aplicação React",
                default_content=self._generate_css_skeleton(capabilities),
            ))

            # 4. Vite HTML container se não existir
            cand_html = ["index.html"]
            matched_html = self._match_existing(cand_html, existing_files)
            if not matched_html and not arch.is_existing:
                arts.append(InferredArtifact(
                    artifact_id="frontend-html-shell",
                    responsibility="Vite host HTML shell",
                    category="frontend",
                    architecture="react_vite",
                    required=False,
                    candidate_paths=cand_html,
                    functional_contracts=["<div id=\"root\">", "/src/main.tsx"],
                    relative_path="index.html",
                    default_content=self._generate_vite_index_html_skeleton(project_name),
                ))

        elif arch.stack == "nextjs":
            # 1. Page Entrypoint
            cand_page = ["app/page.tsx", "app/page.jsx", "pages/index.tsx"]
            matched_page = self._match_existing(cand_page, existing_files)
            arts.append(InferredArtifact(
                artifact_id="frontend-entrypoint",
                responsibility="Next.js page entrypoint",
                category="frontend",
                architecture="nextjs",
                source="existing_project" if matched_page else "inferred",
                required=True,
                existing=bool(matched_page),
                candidate_paths=cand_page,
                functional_contracts=["export default", "return"],
                relative_path=matched_page or "app/page.tsx",
                component="frontend",
                description="Página principal Next.js",
                default_content=self._generate_next_page_skeleton(project_name, capabilities),
            ))

            # 2. Layout
            cand_layout = ["app/layout.tsx", "app/layout.jsx", "pages/_app.tsx"]
            matched_layout = self._match_existing(cand_layout, existing_files)
            arts.append(InferredArtifact(
                artifact_id="frontend-layout",
                responsibility="Next.js root layout",
                category="frontend",
                architecture="nextjs",
                source="existing_project" if matched_layout else "inferred",
                required=True,
                existing=bool(matched_layout),
                candidate_paths=cand_layout,
                functional_contracts=["RootLayout", "children"],
                relative_path=matched_layout or "app/layout.tsx",
                component="frontend",
                description="Layout raiz da aplicação Next.js",
                default_content=self._generate_next_layout_skeleton(project_name),
            ))

            # 3. Global Styling
            cand_css = ["app/globals.css", "styles/globals.css", "src/app/globals.css"]
            matched_css = self._match_existing(cand_css, existing_files)
            arts.append(InferredArtifact(
                artifact_id="frontend-styling",
                responsibility="Next.js global styling",
                category="frontend",
                architecture="nextjs",
                source="existing_project" if matched_css else "inferred",
                required=True,
                existing=bool(matched_css),
                candidate_paths=cand_css,
                functional_contracts=["body"],
                relative_path=matched_css or "app/globals.css",
                component="frontend",
                description="Estilos globais Next.js",
                default_content=self._generate_css_skeleton(capabilities),
            ))

        elif arch.stack == "vue_vite":
            # 1. Vue App Root
            cand_app = ["src/App.vue"]
            matched_app = self._match_existing(cand_app, existing_files)
            arts.append(InferredArtifact(
                artifact_id="frontend-entrypoint",
                responsibility="Vue root component",
                category="frontend",
                architecture="vue_vite",
                source="existing_project" if matched_app else "inferred",
                required=True,
                existing=bool(matched_app),
                candidate_paths=cand_app,
                functional_contracts=["<template>", "<script"],
                relative_path=matched_app or "src/App.vue",
                component="frontend",
                description="Componente raiz Vue 3",
                default_content=self._generate_vue_app_skeleton(project_name, capabilities),
            ))

            # 2. Vue Bootstrap
            cand_boot = ["src/main.js", "src/main.ts"]
            matched_boot = self._match_existing(cand_boot, existing_files)
            arts.append(InferredArtifact(
                artifact_id="frontend-bootstrap",
                responsibility="Vue main bootstrap",
                category="frontend",
                architecture="vue_vite",
                source="existing_project" if matched_boot else "inferred",
                required=True,
                existing=bool(matched_boot),
                candidate_paths=cand_boot,
                functional_contracts=["createApp", "mount"],
                relative_path=matched_boot or "src/main.js",
                component="frontend",
                description="Bootstrap da aplicação Vue",
                default_content=self._generate_vue_main_skeleton(),
            ))

            # 3. Vue Styling
            cand_css = ["src/style.css", "src/App.vue"]
            matched_css = self._match_existing(cand_css, existing_files)
            arts.append(InferredArtifact(
                artifact_id="frontend-styling",
                responsibility="Vue styling",
                category="frontend",
                architecture="vue_vite",
                source="existing_project" if matched_css else "inferred",
                required=True,
                existing=bool(matched_css),
                candidate_paths=cand_css,
                functional_contracts=["body"],
                relative_path=matched_css or "src/style.css",
                component="frontend",
                description="Estilos da aplicação Vue",
                default_content=self._generate_css_skeleton(capabilities),
            ))

        else:
            html_contracts = ["<!DOCTYPE html>", "<div id=\"app\"", "<script"]
            if Capability.SEARCH in capabilities:
                html_contracts.append("id=\"search-input\"")
            if Capability.DASHBOARD in capabilities:
                html_contracts.append("id=\"dashboard\"")
            if Capability.AUTH in capabilities:
                html_contracts.append("id=\"auth-container\"")
            if Capability.CRUD in capabilities:
                html_contracts.append("id=\"item-form\"")

            cand_html = ["index.html"]
            matched_html = self._match_existing(cand_html, existing_files)
            arts.append(InferredArtifact(
                artifact_id="frontend-entrypoint",
                responsibility="HTML5 document structure",
                category="frontend",
                architecture="vanilla_web",
                source="existing_project" if matched_html else "inferred",
                required=True,
                existing=bool(matched_html),
                candidate_paths=cand_html,
                functional_contracts=html_contracts,
                relative_path=matched_html or "index.html",
                component="frontend",
                description="Ponto de entrada HTML5 responsivo",
                default_content=self._generate_html_skeleton(project_name, capabilities),
            ))

            cand_css = ["styles.css", "style.css"]
            matched_css = self._match_existing(cand_css, existing_files)
            arts.append(InferredArtifact(
                artifact_id="frontend-styling",
                responsibility="responsive CSS stylesheet",
                category="frontend",
                architecture="vanilla_web",
                source="existing_project" if matched_css else "inferred",
                required=True,
                existing=bool(matched_css),
                candidate_paths=cand_css,
                functional_contracts=["body", "box-sizing"],
                relative_path=matched_css or "styles.css",
                component="frontend",
                description="Estilos CSS modernos e responsivos",
                default_content=self._generate_css_skeleton(capabilities),
            ))

            js_contracts = ["document.addEventListener"]
            if Capability.STORAGE in capabilities:
                js_contracts.append("localStorage")
            if Capability.SEARCH in capabilities:
                js_contracts.append("filter")
            if Capability.CRUD in capabilities:
                js_contracts.append("render")
            if Capability.AUTH in capabilities:
                js_contracts.append("currentUser")

            cand_js = ["app.js", "main.js", "index.js"]
            matched_js = self._match_existing(cand_js, existing_files)
            arts.append(InferredArtifact(
                artifact_id="frontend-logic",
                responsibility="client-side DOM script",
                category="frontend",
                architecture="vanilla_web",
                source="existing_project" if matched_js else "inferred",
                required=True,
                existing=bool(matched_js),
                candidate_paths=cand_js,
                functional_contracts=js_contracts,
                relative_path=matched_js or "app.js",
                component="frontend",
                description="Lógica client-side com gestão de estado e eventos",
                default_content=self._generate_js_skeleton(project_name, capabilities),
            ))

        return arts

    def _resolve_backend_responsibilities(
        self,
        arch: ProjectArchitecture,
        project_name: str,
        capabilities: set[Capability],
        existing_files: dict[str, str],
    ) -> list[InferredArtifact]:
        arts: list[InferredArtifact] = []

        if arch.stack == "python_fastapi":
            cand_py = ["main.py", "app.py", "server.py", "backend/main.py", "api/main.py"]
            matched = self._match_existing(cand_py, existing_files)
            arts.append(InferredArtifact(
                artifact_id="backend-entrypoint",
                responsibility="backend runtime entrypoint and API routes",
                category="backend",
                architecture="python_fastapi",
                source="existing_project" if matched else "inferred",
                required=True,
                existing=bool(matched),
                candidate_paths=cand_py,
                functional_contracts=["FastAPI", "/health", "PORT"],
                relative_path=matched or "main.py",
                component="backend",
                description="Servidor HTTP / API REST FastAPI assíncrono",
                default_content=self._generate_fastapi_backend_skeleton(project_name, capabilities),
            ))

        elif arch.stack in ("node_express", "node_typescript"):
            cand_node = ["src/server.ts", "server.ts", "src/index.ts", "server.js", "app.js"]
            matched = self._match_existing(cand_node, existing_files)
            arts.append(InferredArtifact(
                artifact_id="backend-entrypoint",
                responsibility="Node backend API entrypoint",
                category="backend",
                architecture=arch.stack,
                source="existing_project" if matched else "inferred",
                required=True,
                existing=bool(matched),
                candidate_paths=cand_node,
                functional_contracts=["express", "listen", "PORT"],
                relative_path=matched or ("src/server.ts" if "src" in arch.source_root else "server.js"),
                component="backend",
                description="Servidor Express Node.js",
                default_content=self._generate_node_express_skeleton(project_name),
            ))

        elif arch.stack == "nextjs":
            cand_api = ["app/api/health/route.ts", "app/api/health/route.js", "pages/api/health.ts"]
            matched = self._match_existing(cand_api, existing_files)
            arts.append(InferredArtifact(
                artifact_id="backend-entrypoint",
                responsibility="Next.js API route handler",
                category="backend",
                architecture="nextjs",
                source="existing_project" if matched else "inferred",
                required=True,
                existing=bool(matched),
                candidate_paths=cand_api,
                functional_contracts=["GET", "Response", "NextResponse"],
                relative_path=matched or "app/api/health/route.ts",
                component="backend",
                description="Rota de API Next.js Route Handler",
                default_content="""import { NextResponse } from 'next/server';

export async function GET() {
    return NextResponse.json({ status: 'ok', timestamp: new Date().toISOString() });
}
""",
            ))

        else:
            # Python Standard HTTP Server
            cand_py = ["server.py", "main.py", "app.py", "backend.py"]
            matched = self._match_existing(cand_py, existing_files)
            arts.append(InferredArtifact(
                artifact_id="backend-entrypoint",
                responsibility="backend HTTP server and routes",
                category="backend",
                architecture=arch.stack,
                source="existing_project" if matched else "inferred",
                required=True,
                existing=bool(matched),
                candidate_paths=cand_py,
                functional_contracts=["PORT", "HTTPServer", "do_GET"],
                relative_path=matched or "server.py",
                component="backend",
                description="Servidor HTTP em Python com rota de healthcheck",
                default_content=self._generate_python_backend_skeleton(project_name, capabilities),
            ))

        return arts

    def _resolve_storage_responsibilities(
        self,
        arch: ProjectArchitecture,
        capabilities: set[Capability],
        existing_files: dict[str, str],
    ) -> list[InferredArtifact]:
        """
        STORAGE significa persistência: NÃO criar database.py automaticamente.
        Resolve primeiro localStorage/IndexedDB se frontend puro.
        Só cria ficheiro de base de dados dedicado se for backend.
        """
        arts: list[InferredArtifact] = []

        is_backend = Capability.BACKEND in capabilities or arch.runtime in ("python", "node")
        if not is_backend:
            # Em arquitetura frontend (Vanilla, React, Vue, Next), persistência é suportada no browser
            if arch.stack == "react_vite":
                cand_storage = ["src/services/storage.ts", "src/hooks/useStorage.ts", "src/App.tsx"]
                matched = self._match_existing(cand_storage, existing_files)
                arts.append(InferredArtifact(
                    artifact_id="client-storage",
                    responsibility="client-side state persistence (localStorage / IndexedDB)",
                    category="storage",
                    architecture="react_vite",
                    source="existing_project" if matched else "inferred",
                    required=False,
                    existing=bool(matched),
                    candidate_paths=cand_storage,
                    functional_contracts=["localStorage"],
                    relative_path=matched or "src/App.tsx",
                    component="storage",
                    description="Persistência no browser via localStorage / Hook",
                ))
            elif arch.stack == "vanilla_web":
                cand_storage = ["app.js", "main.js"]
                matched = self._match_existing(cand_storage, existing_files)
                arts.append(InferredArtifact(
                    artifact_id="client-storage",
                    responsibility="client-side storage in browser",
                    category="storage",
                    architecture="vanilla_web",
                    source="existing_project" if matched else "inferred",
                    required=False,
                    existing=bool(matched),
                    candidate_paths=cand_storage,
                    functional_contracts=["localStorage"],
                    relative_path=matched or "app.js",
                    component="storage",
                    description="Mecanismo de persistência local no browser",
                ))
            return arts

        # Backend Storage
        cand_db = ["database.py", "models.py", "db.py", "db.ts", "schema.sql"]
        matched_db = self._match_existing(cand_db, existing_files)
        arts.append(InferredArtifact(
            artifact_id="backend-database",
            responsibility="backend persistent database layer",
            category="storage",
            architecture=arch.stack,
            source="existing_project" if matched_db else "inferred",
            required=False,
            existing=bool(matched_db),
            candidate_paths=cand_db,
            functional_contracts=["sqlite3", "connect"] if "python" in arch.runtime else ["db"],
            relative_path=matched_db or ("database.py" if "python" in arch.runtime else "src/db.ts"),
            component="storage",
            description="Camada de persistência em base de dados",
            default_content=self._generate_database_skeleton(),
        ))
        return arts

    def _resolve_search_responsibilities(
        self,
        arch: ProjectArchitecture,
        existing_files: dict[str, str],
    ) -> list[InferredArtifact]:
        """
        Prompt: 'adiciona pesquisa'.
        Resolve ficheiro existente primeiro (ex: SearchBar.tsx, App.tsx).
        NUNCA cria search.js num projeto React/Next.
        """
        if arch.stack == "react_vite":
            cand = ["src/components/SearchBar.tsx", "src/components/Search.tsx", "src/App.tsx"]
            matched = self._match_existing(cand, existing_files)
            return [InferredArtifact(
                artifact_id="search-feature",
                responsibility="search and filtering component",
                category="search",
                architecture="react_vite",
                source="existing_project" if matched else "inferred",
                required=True,
                existing=bool(matched),
                candidate_paths=cand,
                functional_contracts=["filter", "search"],
                relative_path=matched or "src/App.tsx",
                component="frontend",
                description="Componente ou rotina de pesquisa em React",
            )]
        elif arch.stack == "nextjs":
            cand = ["app/components/SearchBar.tsx", "app/search/page.tsx", "app/page.tsx"]
            matched = self._match_existing(cand, existing_files)
            return [InferredArtifact(
                artifact_id="search-feature",
                responsibility="search and filtering component in Next.js",
                category="search",
                architecture="nextjs",
                source="existing_project" if matched else "inferred",
                required=True,
                existing=bool(matched),
                candidate_paths=cand,
                functional_contracts=["filter"],
                relative_path=matched or "app/page.tsx",
                component="frontend",
                description="Funcionalidade de pesquisa em Next.js",
            )]
        else:
            cand = ["app.js", "index.html"]
            matched = self._match_existing(cand, existing_files)
            return [InferredArtifact(
                artifact_id="search-feature",
                responsibility="DOM search and filter routines",
                category="search",
                architecture="vanilla_web",
                source="existing_project" if matched else "inferred",
                required=True,
                existing=bool(matched),
                candidate_paths=cand,
                functional_contracts=["filter"],
                relative_path=matched or "app.js",
                component="frontend",
                description="Rotina de filtragem e pesquisa em app.js",
            )]

    def _resolve_dashboard_responsibilities(
        self,
        arch: ProjectArchitecture,
        existing_files: dict[str, str],
    ) -> list[InferredArtifact]:
        """
        Prompt: 'adiciona dashboard'.
        Resolve componente React/Next existente, nunca força templates vanilla.
        """
        if arch.stack == "react_vite":
            cand = ["src/components/Dashboard.tsx", "src/App.tsx"]
            matched = self._match_existing(cand, existing_files)
            return [InferredArtifact(
                artifact_id="dashboard-feature",
                responsibility="dashboard metric and summary view",
                category="dashboard",
                architecture="react_vite",
                source="existing_project" if matched else "inferred",
                required=True,
                existing=bool(matched),
                candidate_paths=cand,
                functional_contracts=["dashboard"],
                relative_path=matched or "src/App.tsx",
                component="frontend",
                description="Painel de métricas e KPIs em React",
            )]
        elif arch.stack == "nextjs":
            cand = ["app/dashboard/page.tsx", "app/page.tsx"]
            matched = self._match_existing(cand, existing_files)
            return [InferredArtifact(
                artifact_id="dashboard-feature",
                responsibility="Next.js dashboard page view",
                category="dashboard",
                architecture="nextjs",
                source="existing_project" if matched else "inferred",
                required=True,
                existing=bool(matched),
                candidate_paths=cand,
                functional_contracts=["dashboard"],
                relative_path=matched or "app/page.tsx",
                component="frontend",
                description="Painel de dashboard em Next.js",
            )]
        else:
            cand = ["index.html", "app.js"]
            matched = self._match_existing(cand, existing_files)
            return [InferredArtifact(
                artifact_id="dashboard-feature",
                responsibility="dashboard cards and metrics UI",
                category="dashboard",
                architecture="vanilla_web",
                source="existing_project" if matched else "inferred",
                required=True,
                existing=bool(matched),
                candidate_paths=cand,
                functional_contracts=["dashboard"],
                relative_path=matched or "index.html",
                component="frontend",
                description="Secção de métricas no index.html e app.js",
            )]

    # -------------------------------------------------------------------------
    # SKELETON GENERATORS
    # -------------------------------------------------------------------------

    def _generate_react_app_skeleton(self, project_name: str, capabilities: set[Capability]) -> str:
        title = project_name.replace("-", " ").title()
        has_auth = Capability.AUTH in capabilities
        has_search = Capability.SEARCH in capabilities
        has_dashboard = Capability.DASHBOARD in capabilities
        has_crud = Capability.CRUD in capabilities
        has_storage = Capability.STORAGE in capabilities

        return f"""import React, {{ useState, useEffect }} from 'react';
import './index.css';

interface Item {{
  id: string;
  title: string;
  completed: boolean;
}}

export default function App() {{
  const [items, setItems] = useState<Item[]>(() => {{
    {('try { const raw = localStorage.getItem("' + project_name + '_items"); return raw ? JSON.parse(raw) : []; } catch { return []; }') if has_storage else 'return [];'}
  }});
  const [newItemTitle, setNewItemTitle] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [currentUser, setCurrentUser] = useState<string | null>({('localStorage.getItem("' + project_name + '_user") || null') if has_auth else 'null'});

  useEffect(() => {{
    {('localStorage.setItem("' + project_name + '_items", JSON.stringify(items));') if has_storage else ''}
  }}, [items]);

  const addItem = (e: React.FormEvent) => {{
    e.preventDefault();
    if (!newItemTitle.trim()) return;
    setItems([{{ id: Date.now().toString(), title: newItemTitle.trim(), completed: false }}, ...items]);
    setNewItemTitle('');
  }};

  const toggleItem = (id: string) => {{
    setItems(items.map(i => i.id === id ? {{ ...i, completed: !i.completed }} : i));
  }};

  const deleteItem = (id: string) => {{
    setItems(items.filter(i => i.id !== id));
  }};

  const filteredItems = items.filter(i => i.title.toLowerCase().includes(searchTerm.toLowerCase()));

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>{title}</h1>
        <div className="status-indicator"><span className="dot online"></span> Pronto</div>
      </header>

      <main className="app-main">
        {('{/* Dashboard */}\\n        <div id="dashboard" className="dashboard-grid"><div className="stat-card">Total: {items.length}</div></div>') if has_dashboard else ''}

        {('{/* Search */}\\n        <div className="search-bar"><input id="search-input" type="text" placeholder="Pesquisar..." value={searchTerm} onChange={e => setSearchTerm(e.target.value)} /></div>') if has_search else ''}

        {('{/* CRUD Form */}\\n        <form id="item-form" className="item-form" onSubmit={addItem}><input id="item-title" type="text" placeholder="Novo item..." value={newItemTitle} onChange={e => setNewItemTitle(e.target.value)} /><button type="submit" className="btn btn-primary">Adicionar</button></form>') if has_crud else ''}

        <ul className="items-list">
          {{filteredItems.map(item => (
            <li key={{item.id}} className={{`item-row ${{item.completed ? 'completed' : ''}}`}}>
              <span>{{item.title}}</span>
              <div className="item-actions">
                <button className="btn btn-secondary btn-sm" onClick={{() => toggleItem(item.id)}}>✓</button>
                <button className="btn btn-secondary btn-sm" onClick={{() => deleteItem(item.id)}}>✕</button>
              </div>
            </li>
          ))}}
        </ul>
      </main>
    </div>
  );
}}
"""

    def _generate_react_main_skeleton(self) -> str:
        return """import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
"""

    def _generate_vite_index_html_skeleton(self, project_name: str) -> str:
        title = project_name.replace("-", " ").title()
        return f"""<!DOCTYPE html>
<html lang="pt">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{title}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
"""

    def _generate_next_page_skeleton(self, project_name: str, capabilities: set[Capability]) -> str:
        title = project_name.replace("-", " ").title()
        return f"""'use client';

import React, {{ useState }} from 'react';

export default function HomePage() {{
  const [items, setItems] = useState<string[]>([]);
  const [inputVal, setInputVal] = useState('');

  const addItem = (e: React.FormEvent) => {{
    e.preventDefault();
    if (!inputVal.trim()) return;
    setItems([inputVal.trim(), ...items]);
    setInputVal('');
  }};

  return (
    <main className="container mx-auto p-8 max-w-2xl">
      <h1 className="text-3xl font-bold mb-6">{title}</h1>
      <form onSubmit={{addItem}} className="flex gap-4 mb-8">
        <input
          type="text"
          className="border p-2 flex-1 rounded text-black"
          placeholder="Adicionar tarefa..."
          value={{inputVal}}
          onChange={{e => setInputVal(e.target.value)}}
        />
        <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded">
          Adicionar
        </button>
      </form>
      <ul className="space-y-2">
        {{items.map((it, idx) => (
          <li key={{idx}} className="p-3 bg-gray-100 rounded text-black">
            {{it}}
          </li>
        ))}}
      </ul>
    </main>
  );
}}
"""

    def _generate_next_layout_skeleton(self, project_name: str) -> str:
        title = project_name.replace("-", " ").title()
        return f"""import './globals.css';
import type {{ Metadata }} from 'next';

export const metadata: Metadata = {{
  title: '{title}',
  description: 'Criado pelo JARVIS OS',
}};

export default function RootLayout({{
  children,
}}: {{
  children: React.ReactNode;
}}) {{
  return (
    <html lang="pt">
      <body className="bg-white text-gray-900 min-h-screen">
        {{children}}
      </body>
    </html>
  );
}}
"""

    def _generate_vue_app_skeleton(self, project_name: str, capabilities: set[Capability]) -> str:
        title = project_name.replace("-", " ").title()
        return f"""<template>
  <div class="app-container">
    <header class="app-header">
      <h1>{title}</h1>
    </header>
    <main class="app-main">
      <form @submit.prevent="addItem" class="item-form">
        <input v-model="newTitle" placeholder="Novo item..." required />
        <button type="submit" class="btn btn-primary">Adicionar</button>
      </form>
      <ul class="items-list">
        <li v-for="it in items" :key="it.id" class="item-row">
          <span>{{{{ it.title }}}}</span>
          <button @click="removeItem(it.id)" class="btn btn-secondary btn-sm">✕</button>
        </li>
      </ul>
    </main>
  </div>
</template>

<script setup>
import {{ ref }} from 'vue';

const items = ref([]);
const newTitle = ref('');

function addItem() {{
  if (!newTitle.value.trim()) return;
  items.value.unshift({{ id: Date.now().toString(), title: newTitle.value.trim() }});
  newTitle.value = '';
}}

function removeItem(id) {{
  items.value = items.value.filter(i => i.id !== id);
}}
</script>
"""

    def _generate_vue_main_skeleton(self) -> str:
        return """import { createApp } from 'vue';
import App from './App.vue';
import './style.css';

createApp(App).mount('#app');
"""

    def _generate_fastapi_backend_skeleton(self, project_name: str, capabilities: set[Capability]) -> str:
        return f"""\"\"\"
JARVIS OS - FastAPI Backend ({project_name})
\"\"\"

import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="{project_name.capitalize()} API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PORT = int(os.environ.get("PORT", 8080))

class Item(BaseModel):
    id: Optional[str] = None
    title: str
    completed: bool = False

db_items: List[Item] = []

@app.get("/health")
def healthcheck():
    return {{"status": "ok", "app": "{project_name}", "version": "1.0.0"}}

@app.get("/api/items", response_model=List[Item])
def get_items():
    return db_items

@app.post("/api/items", response_model=Item, status_code=201)
def create_item(item: Item):
    item.id = str(len(db_items) + 1)
    db_items.append(item)
    return item

@app.delete("/api/items/{{item_id}}")
def delete_item(item_id: str):
    global db_items
    db_items = [i for i in db_items if i.id != item_id]
    return {{"status": "deleted", "id": item_id}}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
"""

    def _generate_node_express_skeleton(self, project_name: str) -> str:
        return f"""// JARVIS OS - Express Backend ({project_name})
import express, {{ Request, Response }} from 'express';
import cors from 'cors';

const app = express();
const PORT = process.env.PORT || 8080;

app.use(cors());
app.use(express.json());

interface Item {{
  id: string;
  title: string;
  completed: boolean;
}}

let items: Item[] = [];

app.get('/health', (req: Request, res: Response) => {{
  res.json({{ status: 'ok', app: '{project_name}', timestamp: new Date().toISOString() }});
}});

app.get('/api/items', (req: Request, res: Response) => {{
  res.json(items);
}});

app.post('/api/items', (req: Request, res: Response) => {{
  const newItem: Item = {{ id: Date.now().toString(), title: req.body.title || '', completed: false }};
  items.unshift(newItem);
  res.status(201).json(newItem);
}});

app.listen(PORT, () => {{
  console.log(`[JARVIS Backend] Servidor Express ativo na porta ${{PORT}}`);
}});
"""

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

    const itemForm = document.getElementById('item-form');
    const itemTitle = document.getElementById('item-title');
    const itemsList = document.getElementById('items-list');
    const emptyState = document.getElementById('empty-state');
    const searchInput = document.getElementById('search-input');
    const filterSelect = document.getElementById('filter-select');

    const statTotal = document.getElementById('stat-total');
    const statActive = document.getElementById('stat-active');
    const statCompleted = document.getElementById('stat-completed');

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

    def _generate_package_json(
        self,
        project_name: str,
        capabilities: set[Capability],
        arch: Optional[ProjectArchitecture] = None,
    ) -> str:
        stack = arch.stack if arch else "vanilla_web"
        scripts = {}
        if stack == "react_vite":
            scripts = {
                "dev": "vite",
                "build": "vite build",
                "preview": "vite preview",
            }
        elif stack == "nextjs":
            scripts = {
                "dev": "next dev",
                "build": "next build",
                "start": "next start",
            }
        elif stack == "vue_vite":
            scripts = {
                "dev": "vite",
                "build": "vite build",
                "preview": "vite preview",
            }
        else:
            scripts = {
                "start": "python server.py" if Capability.BACKEND in capabilities else "npx serve ."
            }

        return json.dumps({
            "name": project_name,
            "version": "1.0.0",
            "description": f"Projeto {project_name} gerado pelo JARVIS OS",
            "scripts": scripts,
            "dependencies": {},
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

        for pattern, cdn_tag, npm_pkg, npm_ver in self.KNOWN_CDN_MAP:
            if re.search(pattern, full_frontend_code, re.IGNORECASE):
                if cdn_tag not in cdn_tags:
                    cdn_tags.append(cdn_tag)
                npm_packages[npm_pkg] = npm_ver

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
    compara com a inferência arquitetural e repara lacunas estruturais.
    REGRAS ARQUITETURAIS:
    1. Resolve a arquitetura primeiro.
    2. Procura artefactos equivalentes que já cumpram as responsabilidades.
    3. Só cria responsabilidades inexistentes usando a convenção da stack.
    4. Corrige STACK MISMATCHES (ex: app.js num projeto React).
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
        project_root: Optional[str] = None,
    ) -> RepairResult:
        inference = self.inference_engine.infer(
            prompt=prompt,
            project_name=project_name,
            project_context=project_context,
            project_root=project_root,
            planned_files=planned_files,
        )
        arch = inference.architecture
        actions: list[RepairAction] = []
        repaired_files = dict(planned_files)
        diagnostics: list[str] = list(inference.diagnostics)
        missing_before: list[str] = []
        unresolved_contracts: list[str] = []

        # 1. Tratar STACK MISMATCH (ex: LLM tentou injetar app.js ou styles.css vanilla num React/Next)
        if arch and arch.stack in ("react_vite", "nextjs", "vue_vite"):
            for bad_file in list(repaired_files.keys()):
                bad_norm = bad_file.replace("\\", "/").strip().lstrip("./").lower()
                if bad_norm in ("app.js", "search.js") and arch.stack in ("react_vite", "nextjs"):
                    del repaired_files[bad_file]
                    actions.append(RepairAction(
                        action_type="REMOVE_MISMATCH",
                        relative_path=bad_file,
                        reason=f"Remoção de artefacto incompatível '{bad_file}' para arquitetura {arch.stack}",
                        content="",
                    ))
                    diagnostics.append(f"[Repair] Removido ficheiro incompatível '{bad_file}' para arquitetura {arch.stack}")
                elif bad_norm in ("styles.css", "style.css") and arch.stack in ("react_vite", "nextjs") and any(rf.startswith("src/") or rf.startswith("app/") for rf in repaired_files):
                    del repaired_files[bad_file]
                    actions.append(RepairAction(
                        action_type="REMOVE_MISMATCH",
                        relative_path=bad_file,
                        reason=f"Remoção de folha de estilos na raiz '{bad_file}' incompatível com arquitetura {arch.stack}",
                        content="",
                    ))
                    diagnostics.append(f"[Repair] Removido ficheiro incompatível '{bad_file}' para arquitetura {arch.stack}")

        # 2. Verificar responsabilidades em falta
        for required_art in inference.required_artifacts:
            if not required_art.required:
                continue

            # Procurar se algum ficheiro no plano cumpre a responsabilidade
            existing_match = self._find_matching_path(required_art, repaired_files)

            if not existing_match and not required_art.existing:
                # Responsabilidade ausente: criar com o caminho e convenções da arquitetura detetada
                target_path = required_art.relative_path
                missing_before.append(target_path)
                actions.append(RepairAction(
                    action_type="CREATE_FILE",
                    relative_path=target_path,
                    reason=f"Responsabilidade obrigatória '{required_art.responsibility}' em falta para arquitetura {arch.stack if arch else 'generic'}.",
                    content=required_art.default_content,
                ))
                repaired_files[target_path] = required_art.default_content
                diagnostics.append(f"[Repair] Criado artefacto em falta '{target_path}' ({required_art.responsibility})")
            else:
                # Verificar contratos funcionais no ficheiro existente
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

        # Injeção de CDN no index.html (se for web app vanilla e tiver tags CDN necessárias)
        if arch and arch.stack == "vanilla_web":
            html_key = self._find_key_in_dict("index.html", repaired_files)
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
            req_key = self._find_key_in_dict("requirements.txt", repaired_files)
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
            pkg_key = self._find_key_in_dict("package.json", repaired_files)
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
            architecture=arch,
        )

    def _find_matching_path(self, art: InferredArtifact, files: dict[str, str]) -> Optional[str]:
        # 1. Correspondência exata em candidate_paths
        for c in art.candidate_paths:
            c_norm = c.replace("\\", "/").strip().lstrip("./").lower()
            for f in files:
                f_norm = f.replace("\\", "/").strip().lstrip("./").lower()
                if f_norm == c_norm:
                    return f

        # 2. Correspondência por nome de ficheiro
        for c in art.candidate_paths:
            c_name = Path(c).name.lower()
            for f in files:
                f_name = Path(f).name.lower()
                if f_name == c_name:
                    return f

        # 3. Correspondência por responsabilidade / aliases
        if art.category == "frontend" and "styling" in art.responsibility.lower():
            for f in files:
                if f.lower().endswith((".css", ".scss")) and not f.startswith("."):
                    return f

        if art.category == "backend" and "entrypoint" in art.responsibility.lower():
            for f in files:
                f_name = Path(f).name.lower()
                if f_name in ("server.py", "main.py", "app.py", "server.ts", "server.js", "index.py", "index.ts"):
                    return f

        return None

    def _find_key_in_dict(self, target_name: str, files: dict[str, str]) -> Optional[str]:
        t_low = target_name.lower()
        for k in files:
            if k.lower() == t_low or Path(k).name.lower() == t_low:
                return k
        return None

    def _patch_contracts(
        self,
        filename: str,
        current_content: str,
        missing_contracts: list[str],
        fallback_content: str,
    ) -> str:
        patched = current_content
        ext = Path(filename).suffix.lower()

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
                if "do_GET" in patched:
                    patched = patched.replace(
                        "def do_GET(self):",
                        "def do_GET(self):\n        if self.path == '/health':\n            self.send_response(200)\n            self.send_header('Content-Type', 'application/json')\n            self.end_headers()\n            self.wfile.write(b'{\"status\": \"ok\"}')\n            return",
                    )

        return patched

    def _inject_cdn_tags(self, html: str, cdn_tags: list[str]) -> str:
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
