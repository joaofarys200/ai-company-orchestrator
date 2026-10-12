"""
Motor de Inferência Determinística de Artefactos e Capacidades do JARVIS.
Implementa o Princípio Arquitetural: CAPABILITY-BASED, ARCHITECTURE-AWARE, NÃO TEMPLATE-DRIVEN.

A inferência opera sobre:
PROMPT + CONTEXTO DO PROJETO + ARQUITETURA EXISTENTE + STACK DETETADA + REQUISITOS FUNCIONAIS -> ARTEFACTOS NECESSÁRIOS
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from security.delivery_governance.architecture_detector import ArchitectureDetector, DetectedArchitecture
from security.delivery_governance.models import (
    ArchitectureDecision,
    ArtifactCategory,
    ArtifactEvidence,
    ArtifactEvidenceStatus,
    ArtifactExpectation,
    RequirementItem,
    RequirementStatus,
)


class ArtifactInferenceEngine:
    """Inferência determinística de artefactos e capacidades arquiteturais."""

    @classmethod
    def infer_architecture_and_artifacts(
        cls,
        user_prompt: str,
        project_root: str,
        project_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[DetectedArchitecture, ArchitectureDecision, List[ArtifactExpectation], List[RequirementItem]]:
        """
        1. Executa deteção de arquitetura existente primeiro (Existing Architecture First).
        2. Infere capacidades requeridas a partir do prompt e do contexto.
        3. Se projeto existente: adota a arquitetura detetada sem forçar templates genéricos.
        4. Se projeto novo: seleciona e documenta ArchitectureDecision formal.
        5. Produz lista de ArtifactExpectation com responsabilidades explícitas.
        6. Produz lista de RequirementItem com rastreabilidade atómica.
        """
        # 1. Arquitetura existente primeiro
        arch = ArchitectureDetector.detect_architecture(project_root)

        # 2. Deteta capacidades requeridas
        capabilities = cls._detect_requested_capabilities(user_prompt, arch)

        # 3. Determina ArchitectureDecision
        decision = cls._resolve_architecture_decision(user_prompt, arch, capabilities, project_context)

        # 4. Gera expectativas de artefactos baseadas em capacidades e na stack
        expectations = cls._generate_artifact_expectations(decision, arch, capabilities, project_root)

        # 5. Gera requisitos funcionais com rastreabilidade
        requirements = cls._generate_requirements(user_prompt, capabilities, expectations)

        return arch, decision, expectations, requirements

    @classmethod
    def evaluate_artifact_evidence(
        cls,
        expectations: List[ArtifactExpectation],
        project_root: str,
    ) -> List[ArtifactEvidence]:
        """
        Avalia cada expectativa de artefacto no sistema de ficheiros do projeto.
        Garante a regra estrita: PRESENT != VALIDATED.
        """
        evidence_list: List[ArtifactEvidence] = []
        if not os.path.isdir(project_root):
            for exp in expectations:
                evidence_list.append(ArtifactEvidence(
                    artifact_id=exp.artifact_id,
                    expected_path=exp.path or exp.path_pattern or "unknown",
                    responsibility=exp.responsibility,
                    category=exp.category,
                    exists=False,
                    non_empty=False,
                    validated=False,
                    evidence_ids=[],
                    status=ArtifactEvidenceStatus.MISSING.value if exp.required else ArtifactEvidenceStatus.UNKNOWN.value,
                    details={"reason": "project_root does not exist"},
                ))
            return evidence_list

        # Mapeia ficheiros do projeto
        project_files: List[str] = []
        for root, dirs, files in os.walk(project_root):
            dirs[:] = [d for d in dirs if d not in ArchitectureDetector.IGNORE_DIRS]
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), project_root).replace("\\", "/")
                project_files.append(rel)

        for exp in expectations:
            matched_file: Optional[str] = None
            if exp.path and os.path.exists(os.path.join(project_root, exp.path)):
                matched_file = exp.path
            elif exp.path_pattern:
                pat = re.compile(exp.path_pattern, re.IGNORECASE)
                for pf in project_files:
                    if pat.search(pf):
                        matched_file = pf
                        break
            elif exp.path:
                # Tenta correspondência case-insensitive ou alternativa
                for pf in project_files:
                    if pf.lower() == exp.path.lower():
                        matched_file = pf
                        break

            # Se ainda não encontrou ficheiro pelo caminho/padrão, procura se algum ficheiro do projeto satisfaz a responsabilidade
            if not matched_file:
                code_exts = (".ts", ".tsx", ".js", ".jsx", ".py", ".vue", ".html", ".htm")
                if exp.category == "style" or "style" in exp.responsibility.lower():
                    code_exts = (".css", ".scss", ".less")
                for pf in project_files:
                    if not pf.endswith(code_exts):
                        continue
                    try:
                        p_content = Path(os.path.join(project_root, pf)).read_text(encoding="utf-8", errors="ignore")
                        _, can_validate = cls._validate_file_content_responsibility(
                            category=exp.category,
                            responsibility=exp.responsibility,
                            content=p_content,
                            file_path=pf,
                        )
                        if can_validate:
                            matched_file = pf
                            break
                    except Exception:
                        pass

            if not matched_file:
                status = ArtifactEvidenceStatus.MISSING.value if exp.required else ArtifactEvidenceStatus.UNKNOWN.value
                evidence_list.append(ArtifactEvidence(
                    artifact_id=exp.artifact_id,
                    expected_path=exp.path or exp.path_pattern or "",
                    responsibility=exp.responsibility,
                    category=exp.category,
                    exists=False,
                    non_empty=False,
                    validated=False,
                    evidence_ids=[],
                    status=status,
                    details={"error": "Ficheiro ou padrão não encontrado no projeto"},
                ))
                continue

            full_p = os.path.join(project_root, matched_file)
            size = os.path.getsize(full_p)
            exists = True
            non_empty = size > 0

            if not non_empty:
                evidence_list.append(ArtifactEvidence(
                    artifact_id=exp.artifact_id,
                    expected_path=matched_file,
                    responsibility=exp.responsibility,
                    category=exp.category,
                    exists=True,
                    non_empty=False,
                    validated=False,
                    evidence_ids=[],
                    status=ArtifactEvidenceStatus.PRESENT.value,  # PRESENT != VALIDATED
                    details={"error": "Ficheiro existe mas está vazio (0 bytes)"},
                ))
                continue

            # Avalia conteúdo funcional em conformidade com a responsabilidade
            content = ""
            try:
                content = Path(full_p).read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                evidence_list.append(ArtifactEvidence(
                    artifact_id=exp.artifact_id,
                    expected_path=matched_file,
                    responsibility=exp.responsibility,
                    category=exp.category,
                    exists=True,
                    non_empty=True,
                    validated=False,
                    evidence_ids=[],
                    status=ArtifactEvidenceStatus.FAILED.value,
                    details={"read_error": str(e)},
                ))
                continue

            evidence_ids, validated = cls._validate_file_content_responsibility(
                category=exp.category,
                responsibility=exp.responsibility,
                content=content,
                file_path=matched_file,
            )

            status = ArtifactEvidenceStatus.VALIDATED.value if validated else ArtifactEvidenceStatus.PRESENT.value
            evidence_list.append(ArtifactEvidence(
                artifact_id=exp.artifact_id,
                expected_path=matched_file,
                responsibility=exp.responsibility,
                category=exp.category,
                exists=True,
                non_empty=True,
                validated=validated,
                evidence_ids=evidence_ids,
                status=status,
                details={"file_size": size, "evidence_count": len(evidence_ids)},
            ))

        return evidence_list

    @classmethod
    def _validate_file_content_responsibility(
        cls,
        category: str,
        responsibility: str,
        content: str,
        file_path: str,
    ) -> Tuple[List[str], bool]:
        """Avalia se o ficheiro possui evidência de código satisfazendo a responsabilidade requerida."""
        ev_ids: List[str] = []
        validated = False
        norm_resp = responsibility.lower()
        norm_cat = category.lower()

        clean_slug = re.sub(r'[^a-zA-Z0-9]', '_', file_path).upper()

        if "style" in norm_resp or file_path.endswith(".css"):
            if len(content.strip()) > 5:
                ev_ids.append(f"EVID-STYLE-{clean_slug}")
                validated = True

        elif "boot" in norm_resp:
            if any(t in content for t in ["render", "createRoot", "mount", "export", "import", "ReactDOM", "App"]):
                ev_ids.append(f"EVID-BOOT-{clean_slug}")
                validated = True

        elif norm_cat == ArtifactCategory.STORAGE.value or "storage" in norm_resp or "persist" in norm_resp:
            if any(term in content for term in ["localStorage", "sessionStorage", "sqlite", "sqlite3", "db.", "session.", "repository", "setItem", "getItem", "json.dump", "fs.", "useLocalStorage", "storage."]):
                ev_ids.append(f"EVID-STORAGE-{clean_slug}")
                validated = True

        elif norm_cat == ArtifactCategory.CRUD.value or "crud" in norm_resp:
            # Operações C/R/U/D
            has_create = any(t in content.lower() for t in ["create", "add", "insert", "append", "push", "post", "novo", "adicionar", "save"])
            has_read = any(t in content.lower() for t in ["read", "get", "list", "fetch", "select", "find", "obter", "listar"])
            has_delete = any(t in content.lower() for t in ["delete", "remove", "destroy", "filter(", "pop", "splice", "remover", "eliminar"])
            has_update = any(t in content.lower() for t in ["update", "put", "patch", "edit", "editar", "concluir", "toggle"])
            if (has_create or has_read or has_delete or has_update) and len(content.strip()) > 20:
                ev_ids.append(f"EVID-CRUD-{clean_slug}")
                validated = True

        elif norm_cat == ArtifactCategory.SEARCH.value or "search" in norm_resp or "pesquisa" in norm_resp:
            if any(t in content.lower() for t in ["filter(", "search", "query", "includes(", "find(", "pesquisa", "where", "like", "buscar"]):
                ev_ids.append(f"EVID-SEARCH-{clean_slug}")
                validated = True

        elif norm_cat == ArtifactCategory.DASHBOARD.value or "dashboard" in norm_resp:
            if any(t in content.lower() for t in ["dashboard", "metric", "card", "stat", "chart", "analytics", "painel", "kpi"]):
                ev_ids.append(f"EVID-DASHBOARD-{clean_slug}")
                validated = True

        elif norm_cat == ArtifactCategory.AUTH.value or "auth" in norm_resp or "autenticação" in norm_resp:
            if any(t in content.lower() for t in ["login", "logout", "password", "token", "jwt", "auth", "session", "user"]):
                ev_ids.append(f"EVID-AUTH-{clean_slug}")
                validated = True

        elif norm_cat == ArtifactCategory.BACKEND.value or "backend" in norm_resp or "server" in norm_resp or "api" in norm_resp:
            if any(term in content.lower() for term in ["fastapi", "app.get", "app.post", "router", "express", "http", "flask", "def get", "def post", "def ", "listen("]):
                ev_ids.append(f"EVID-BE-{clean_slug}")
                validated = True
            elif len(content.strip()) > 30:
                ev_ids.append(f"EVID-BE-{clean_slug}")
                validated = True

        elif norm_cat == ArtifactCategory.FRONTEND.value or "frontend" in norm_resp or "interface" in norm_resp or "script" in norm_resp or file_path.endswith(".js"):
            # HTML ou React/JSX/Vue ou script client
            if "<html" in content.lower() or "<body" in content.lower() or any(k in content for k in [
                "export default", "export const", "function ", "const ", "<template>", "return (", "class ",
                "addEventListener", "document.", "window.", "console.", "=>", "onClick", "alert("
            ]):
                ev_ids.append(f"EVID-FE-{clean_slug}")
                validated = True

        else:
            # Qualquer artefacto estrutural genérico (ex: styling, bootstrap)
            if len(content.strip()) > 5:
                ev_ids.append(f"EVID-GEN-{clean_slug}")
                validated = True

        return ev_ids, validated

        return ev_ids, validated

    @classmethod
    def _detect_requested_capabilities(cls, user_prompt: str, arch: DetectedArchitecture) -> List[str]:
        """Extrai capacidades solicitadas pelo prompt e pelo contexto."""
        prompt_lower = user_prompt.lower()
        capabilities: List[str] = []

        # Frontend
        if any(w in prompt_lower for w in ["web", "site", "ui", "interface", "ecrã", "tela", "página", "botão", "visual", "react", "html", "dashboard", "css", "dark mode", "tema"]):
            capabilities.append(ArtifactCategory.FRONTEND.value)
        elif arch.is_existing and arch.stack in {"react_vite", "nextjs", "vanilla_web", "vue_vite"}:
            capabilities.append(ArtifactCategory.FRONTEND.value)

        # Storage
        if any(w in prompt_lower for w in ["localstorage", "persist", "persistência", "database", "sqlite", "banco de dados", "salvar tarefas", "guardar tarefas"]):
            capabilities.append(ArtifactCategory.STORAGE.value)

        # CRUD: apenas quando explicitamente solicitado ou quando se trata de gestão de entidades/tarefas
        if "crud" in prompt_lower or any(phrase in prompt_lower for phrase in ["gestão de tarefas", "todo list", "lista de tarefas", "criar e listar", "criar, listar", "task management"]):
            capabilities.append(ArtifactCategory.CRUD.value)

        # Backend
        if any(w in prompt_lower for w in ["backend", "api", "servidor", "server", "endpoint", "fastapi", "flask", "express", "rota", "rotas"]):
            capabilities.append(ArtifactCategory.BACKEND.value)
        elif arch.is_existing and arch.stack in {"python_fastapi", "python_flask", "python_backend", "node_express", "node_typescript"}:
            capabilities.append(ArtifactCategory.BACKEND.value)

        # Dashboard
        if any(w in prompt_lower for w in ["dashboard", "painel", "métricas", "analytics", "estatísticas", "gráfico", "chart"]):
            capabilities.append(ArtifactCategory.DASHBOARD.value)

        # Search
        if any(w in prompt_lower for w in ["pesquisa", "pesquisar", "search", "busca", "filtro", "filtrar"]):
            capabilities.append(ArtifactCategory.SEARCH.value)

        # Auth
        if any(w in prompt_lower for w in ["auth", "autenticação", "login", "sessão", "password", "senha", "utilizador", "user"]):
            capabilities.append(ArtifactCategory.AUTH.value)

        # Se nenhuma foi detetada
        if not capabilities:
            if arch.is_existing and arch.stack in {"python_fastapi", "python_flask", "python_backend", "node_express", "node_typescript"}:
                capabilities.append(ArtifactCategory.BACKEND.value)
            else:
                capabilities.append(ArtifactCategory.FRONTEND.value)

        return capabilities

    @classmethod
    def _resolve_architecture_decision(
        cls,
        user_prompt: str,
        arch: DetectedArchitecture,
        capabilities: List[str],
        project_context: Optional[Dict[str, Any]],
    ) -> ArchitectureDecision:
        """Resolve a decisão de arquitetura sem inventar ficheiros arbitrários."""
        prompt_lower = user_prompt.lower()

        # Caso 1: Projeto Existente
        if arch.is_existing and arch.stack != "empty":
            return ArchitectureDecision(
                selected_stack=arch.stack,
                rationale=f"Arquitetura existente detetada: stack '{arch.stack}', framework '{arch.framework}'. Preservando estrutura.",
                inferred_artifacts=[f for lst in arch.entrypoints.values() for f in lst],
                expected_capabilities=capabilities,
                is_new_project=False,
                framework=arch.framework,
                bundler=arch.bundler,
                runtime=arch.runtime,
                entrypoints=arch.entrypoints,
                conventions=arch.conventions,
            )

        # Caso 2: Projeto Novo
        if "react" in prompt_lower or "vite" in prompt_lower:
            selected_stack = "react_vite"
            framework = "React"
            bundler = "Vite"
            runtime = "browser"
            rationale = "Projeto novo com especificação explícita de React/Vite."
            entrypoints = {
                "frontend": ["src/App.tsx"],
                "bootstrap": ["src/main.tsx"],
                "styling": ["src/index.css"],
            }
        elif "next" in prompt_lower or "nextjs" in prompt_lower:
            selected_stack = "nextjs"
            framework = "Next.js"
            bundler = "Next.js"
            runtime = "node"
            rationale = "Projeto novo com especificação de Next.js."
            entrypoints = {
                "frontend": ["app/page.tsx"],
                "layout": ["app/layout.tsx"],
                "styling": ["app/globals.css"],
            }
        elif "fastapi" in prompt_lower or ("python" in prompt_lower and "api" in prompt_lower):
            selected_stack = "python_fastapi"
            framework = "FastAPI"
            bundler = "None"
            runtime = "python"
            rationale = "Projeto novo com requisito de API backend em Python FastAPI."
            entrypoints = {"backend": ["main.py"]}
        elif "flask" in prompt_lower:
            selected_stack = "python_flask"
            framework = "Flask"
            bundler = "None"
            runtime = "python"
            rationale = "Projeto novo com requisito de servidor Flask."
            entrypoints = {"backend": ["app.py"]}
        elif "node" in prompt_lower or "express" in prompt_lower:
            selected_stack = "node_express"
            framework = "Express"
            bundler = "None"
            runtime = "node"
            rationale = "Projeto novo com requisito de backend Node/Express."
            entrypoints = {"backend": ["server.js"]}
        else:
            # Decisão arquitetural padrão para aplicação web simples: Vanilla Web
            selected_stack = "vanilla_web"
            framework = "Vanilla"
            bundler = "None"
            runtime = "browser"
            rationale = "Decisão arquitetural: aplicação web autónoma sem dependências externas (Vanilla HTML/CSS/JS)."
            entrypoints = {
                "frontend": ["index.html"],
                "styling": ["styles.css"],
                "scripts": ["app.js"],
            }

        return ArchitectureDecision(
            selected_stack=selected_stack,
            rationale=rationale,
            inferred_artifacts=[f for lst in entrypoints.values() for f in lst],
            expected_capabilities=capabilities,
            is_new_project=True,
            framework=framework,
            bundler=bundler,
            runtime=runtime,
            entrypoints=entrypoints,
            conventions={"is_new": True},
        )

    @classmethod
    def _generate_artifact_expectations(
        cls,
        decision: ArchitectureDecision,
        arch: DetectedArchitecture,
        capabilities: List[str],
        project_root: str,
    ) -> List[ArtifactExpectation]:
        """Gera lista de expectativas de artefactos respeitando a stack e responsabilidades."""
        expectations: List[ArtifactExpectation] = []
        source = "INFERRED_BY_PROJECT" if arch.is_existing and arch.stack != "empty" else "INFERRED_BY_DEFAULT_ARCHITECTURE"
        stack = decision.selected_stack

        # 1. FRONTEND CAPABILITY
        if ArtifactCategory.FRONTEND.value in capabilities:
            if stack == "react_vite":
                fe_entry = arch.entrypoints.get("frontend", ["src/App.tsx"])[0] if arch.entrypoints.get("frontend") else "src/App.tsx"
                boot_entry = arch.entrypoints.get("bootstrap", ["src/main.tsx"])[0] if arch.entrypoints.get("bootstrap") else "src/main.tsx"
                style_entry = arch.entrypoints.get("styling", ["src/index.css"])[0] if arch.entrypoints.get("styling") else "src/index.css"

                expectations.append(ArtifactExpectation(
                    artifact_id="ART-FE-ENTRY",
                    category=ArtifactCategory.FRONTEND.value,
                    responsibility="frontend entrypoint / main UI component",
                    path=fe_entry,
                    required=True,
                    architecture_source=source,
                    evidence_requirements=["component_render", "ui_structure"],
                ))
                expectations.append(ArtifactExpectation(
                    artifact_id="ART-FE-BOOT",
                    category=ArtifactCategory.FRONTEND.value,
                    responsibility="application bootstrap and mount point",
                    path=boot_entry,
                    required=True,
                    architecture_source=source,
                    evidence_requirements=["dom_mount"],
                ))
                expectations.append(ArtifactExpectation(
                    artifact_id="ART-FE-STYLE",
                    category=ArtifactCategory.FRONTEND.value,
                    responsibility="application design tokens and styling",
                    path=style_entry,
                    required=True,
                    architecture_source=source,
                    evidence_requirements=["css_styles"],
                ))

            elif stack == "nextjs":
                page_entry = arch.entrypoints.get("frontend", ["app/page.tsx"])[0] if arch.entrypoints.get("frontend") else "app/page.tsx"
                expectations.append(ArtifactExpectation(
                    artifact_id="ART-FE-PAGE",
                    category=ArtifactCategory.FRONTEND.value,
                    responsibility="Next.js page entrypoint",
                    path=page_entry,
                    path_pattern=r"(app/page\.(tsx|jsx|js)|pages/index\.(tsx|jsx|js))",
                    required=True,
                    architecture_source=source,
                    evidence_requirements=["page_component"],
                ))
                if arch.entrypoints.get("styling"):
                    expectations.append(ArtifactExpectation(
                        artifact_id="ART-FE-STYLE",
                        category=ArtifactCategory.FRONTEND.value,
                        responsibility="global styles",
                        path=arch.entrypoints["styling"][0],
                        required=False,
                        architecture_source=source,
                    ))

            elif stack == "vanilla_web":
                expectations.append(ArtifactExpectation(
                    artifact_id="ART-FE-HTML",
                    category=ArtifactCategory.FRONTEND.value,
                    responsibility="HTML semantic document structure and UI root",
                    path="index.html",
                    required=True,
                    architecture_source=source,
                    evidence_requirements=["html_root", "interactive_elements"],
                ))
                expectations.append(ArtifactExpectation(
                    artifact_id="ART-FE-STYLE",
                    category=ArtifactCategory.FRONTEND.value,
                    responsibility="stylesheet and visual presentation",
                    path=arch.entrypoints.get("styling", ["styles.css"])[0] if arch.entrypoints.get("styling") else "styles.css",
                    path_pattern=r".*\.css$",
                    required=True,
                    architecture_source=source,
                    evidence_requirements=["css_rules"],
                ))
                expectations.append(ArtifactExpectation(
                    artifact_id="ART-FE-SCRIPT",
                    category=ArtifactCategory.FRONTEND.value,
                    responsibility="client interactivity and logic",
                    path=arch.entrypoints.get("scripts", ["app.js"])[0] if arch.entrypoints.get("scripts") else "app.js",
                    path_pattern=r".*\.js$",
                    required=True,
                    architecture_source=source,
                    evidence_requirements=["dom_events"],
                ))

            else:
                # Custom ou Fullstack onde backend é a stack detetada mas frontend coexiste (ex: frontend/index.html)
                fe_candidates = [f for f in arch.existing_files if f.endswith((".html", ".htm", ".tsx", ".jsx"))]
                fe_file = fe_candidates[0] if fe_candidates else (arch.existing_files[0] if arch.existing_files else "index.html")
                expectations.append(ArtifactExpectation(
                    artifact_id="ART-FE-INTERFACE",
                    category=ArtifactCategory.FRONTEND.value,
                    responsibility="frontend interface entrypoint",
                    path=fe_file,
                    path_pattern=r".*(index\.html|App\.(tsx|jsx)|page\.(tsx|jsx)|\.html).*",
                    required=True,
                    architecture_source=source,
                ))

        # 2. BACKEND CAPABILITY
        if ArtifactCategory.BACKEND.value in capabilities:
            if stack in {"python_fastapi", "python_flask", "python_backend"}:
                be_entry = arch.entrypoints.get("backend", ["main.py"])[0] if arch.entrypoints.get("backend") else "main.py"
                expectations.append(ArtifactExpectation(
                    artifact_id="ART-BE-SERVER",
                    category=ArtifactCategory.BACKEND.value,
                    responsibility="backend server entrypoint and API routes",
                    path=be_entry,
                    path_pattern=r".*(main|app|server|api)\.py$",
                    required=True,
                    architecture_source=source,
                    evidence_requirements=["api_routes", "server_instance"],
                ))
            elif stack in {"node_express", "node_typescript"}:
                be_entry = arch.entrypoints.get("backend", ["src/index.ts"])[0] if arch.entrypoints.get("backend") else "src/index.ts"
                expectations.append(ArtifactExpectation(
                    artifact_id="ART-BE-SERVER",
                    category=ArtifactCategory.BACKEND.value,
                    responsibility="Node.js API server entrypoint",
                    path=be_entry,
                    path_pattern=r".*(index|server|app)\.(ts|js)$",
                    required=True,
                    architecture_source=source,
                    evidence_requirements=["route_handlers"],
                ))
            elif stack == "nextjs":
                expectations.append(ArtifactExpectation(
                    artifact_id="ART-BE-API",
                    category=ArtifactCategory.BACKEND.value,
                    responsibility="Next.js API route or server action",
                    path_pattern=r"(app/api/.*|pages/api/.*)",
                    required=True,
                    architecture_source=source,
                    evidence_requirements=["api_handler"],
                ))

        # 3. STORAGE CAPABILITY (Capability-Based: sem impor ficheiro fixo!)
        if ArtifactCategory.STORAGE.value in capabilities:
            # Qualquer ficheiro/serviço/hook/componente com evidência de persistência
            if stack == "react_vite":
                expectations.append(ArtifactExpectation(
                    artifact_id="ART-STORAGE-HOOK-OR-SERVICE",
                    category=ArtifactCategory.STORAGE.value,
                    responsibility="task and state persistence mechanism (localStorage / service / hook)",
                    path_pattern=r"(src/(hooks|services|utils)/.*(storage|localstorage).*|src/App\.(tsx|jsx))",
                    required=True,
                    architecture_source=source,
                    evidence_requirements=["storage_persistence_evidence"],
                ))
            elif stack in {"python_fastapi", "python_flask", "python_backend"}:
                expectations.append(ArtifactExpectation(
                    artifact_id="ART-STORAGE-REPO",
                    category=ArtifactCategory.STORAGE.value,
                    responsibility="persistence mechanism / repository / db layer",
                    path_pattern=r".*(db|models|repository|storage|database|main|app)\.py",
                    required=True,
                    architecture_source=source,
                    evidence_requirements=["persistence_operations"],
                ))
            else:
                expectations.append(ArtifactExpectation(
                    artifact_id="ART-STORAGE-CLIENT",
                    category=ArtifactCategory.STORAGE.value,
                    responsibility="client persistence mechanism (localStorage / IndexedDB)",
                    path_pattern=r".*(app|storage|store|client|index)\.(js|ts)",
                    required=True,
                    architecture_source=source,
                    evidence_requirements=["localstorage_usage"],
                ))

        # 4. CRUD CAPABILITY (Comportamental: C, R, U, D)
        if ArtifactCategory.CRUD.value in capabilities:
            expectations.append(ArtifactExpectation(
                artifact_id="ART-CRUD-OPERATIONS",
                category=ArtifactCategory.CRUD.value,
                responsibility="CRUD operations handlers (Create, Read, Update, Delete)",
                path_pattern=r".*(task|todo|item|app|main|service|route|list|form|server|api).*",
                required=False,
                architecture_source=source,
                evidence_requirements=["create_read_update_delete_logic"],
            ))

        # 5. DASHBOARD CAPABILITY
        if ArtifactCategory.DASHBOARD.value in capabilities:
            expectations.append(ArtifactExpectation(
                artifact_id="ART-DASHBOARD-VIEW",
                category=ArtifactCategory.DASHBOARD.value,
                responsibility="dashboard view / metrics aggregation and presentation",
                path_pattern=r".*(dashboard|metrics|stats|overview|analytics|panel).*",
                required=True,
                architecture_source=source,
                evidence_requirements=["metric_presentation"],
            ))

        # 6. SEARCH CAPABILITY
        if ArtifactCategory.SEARCH.value in capabilities:
            expectations.append(ArtifactExpectation(
                artifact_id="ART-SEARCH-LOGIC",
                category=ArtifactCategory.SEARCH.value,
                responsibility="search and filtering logic",
                path_pattern=r".*(search|filter|list|app|main).*",
                required=True,
                architecture_source=source,
                evidence_requirements=["filter_and_search_query"],
            ))

        # 7. AUTH CAPABILITY
        if ArtifactCategory.AUTH.value in capabilities:
            expectations.append(ArtifactExpectation(
                artifact_id="ART-AUTH-MODULE",
                category=ArtifactCategory.AUTH.value,
                responsibility="authentication and authorization mechanisms",
                path_pattern=r".*(auth|login|session|user|page|app).*",
                required=True,
                architecture_source=source,
                evidence_requirements=["auth_verification"],
            ))

        return expectations

    @classmethod
    def _generate_requirements(
        cls,
        user_prompt: str,
        capabilities: List[str],
        expectations: List[ArtifactExpectation],
    ) -> List[RequirementItem]:
        """Gera requisitos atómicos com aceitação vinculada a evidências concretas."""
        items: List[RequirementItem] = []
        req_id = 1

        for cap in capabilities:
            matching_arts = [e.artifact_id for e in expectations if e.category == cap]
            desc = f"Implementação verificável da capacidade de {cap.upper()} ({', '.join(matching_arts)})"
            items.append(RequirementItem(
                requirement_id=f"REQ-{req_id:02d}",
                description=desc,
                category=cap,
                source="inferred_capability",
                acceptance_test=f"Verificação de evidência de código e responsabilidade arquitetural para {cap}",
                acceptance_tests=[f"test_capability_{cap}_evidence"],
                required_artifacts=matching_arts,
                status=RequirementStatus.UNKNOWN.value,
                blocking=True,
            ))
            req_id += 1

        # Adiciona também linhas explícitas do prompt se houver
        lines = [l.strip() for l in user_prompt.splitlines() if l.strip()]
        for l in lines:
            if len(l) > 15 and not l.startswith("=") and not l.startswith("#"):
                items.append(RequirementItem(
                    requirement_id=f"REQ-{req_id:02d}",
                    description=l[:120],
                    category="functional_prompt",
                    source="user_prompt",
                    acceptance_test="Validação funcional e de produto sem regressões",
                    acceptance_tests=["test_functional_integrity"],
                    required_artifacts=[e.artifact_id for e in expectations[:2]],
                    status=RequirementStatus.UNKNOWN.value,
                    blocking=True,
                ))
                req_id += 1

        return items
