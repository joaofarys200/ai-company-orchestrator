"""
JARVIS OS — Phase 31: Pre-Execution Intelligence & Mission Understanding Engine

Provides deep, explainable pre-execution mission understanding:
1. Semantic Goal Parsing (Nouns, Verbs, Entities, Scope)
2. Strict Differentiation:
   - USER_REQUIREMENT (Source: USER, Status: VERIFIED, Confidence: 1.0)
   - SYSTEM_ASSUMPTION (Source: SYSTEM, Status: INFERRED, Confidence: 0.80 - 0.95)
   - UNKNOWN (Not provided, unverified project details)
3. Negative & Infeasible Mission Detection:
   - BLOCKED_REQUIRED_INFORMATION (Critically underspecified)
   - BLOCKED_POLICY (Violates safety invariants / policy gates)
   - BLOCKED_TECHNICAL_CONSTRAINT (Technically / logically impossible)
4. Dynamic Project Context & Pre-Execution Plan:
   - Predicted Affected Files
   - Architecture Impact & Layers
   - Task DAG with Agent Assignments
   - Validation Strategy & Potential Risks
5. Explainability & Planning Accuracy Scoring (Predicted vs Actual)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import difflib
import enum
import hashlib
import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple


class ItemSource(str, enum.Enum):
    USER = "USER"
    SYSTEM = "SYSTEM"


class EvidenceState(str, enum.Enum):
    VERIFIED = "VERIFIED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class UnderstandingStatus(str, enum.Enum):
    READY = "READY"
    REQUEST_INFORMATION = "REQUEST_INFORMATION"
    BLOCKED_REQUIRED_INFORMATION = "BLOCKED_REQUIRED_INFORMATION"
    BLOCKED_POLICY = "BLOCKED_POLICY"
    BLOCKED_TECHNICAL_CONSTRAINT = "BLOCKED_TECHNICAL_CONSTRAINT"


class NoveltyClass(str, enum.Enum):
    KNOWN_PATTERN = "KNOWN_PATTERN"
    COMPOSED_PATTERN = "COMPOSED_PATTERN"
    NOVEL_PATTERN = "NOVEL_PATTERN"


class MissionClass(str, enum.Enum):
    SOFTWARE_PROJECT = "SOFTWARE_PROJECT"
    FEATURE_IMPLEMENTATION = "FEATURE_IMPLEMENTATION"
    BUG_REPAIR = "BUG_REPAIR"
    REFACTOR_TEST_BUILD = "REFACTOR_TEST_BUILD"


@dataclass
class RequirementItem:
    req_id: str
    description: str
    source: ItemSource = ItemSource.USER
    status: EvidenceState = EvidenceState.VERIFIED
    confidence: float = 1.0
    category: str = "FUNCTIONAL"
    verifiable_via: str = "AUTOMATED_TEST"

    def to_dict(self) -> dict[str, Any]:
        return {
            "req_id": self.req_id,
            "description": self.description,
            "source": self.source.value,
            "status": self.status.value,
            "confidence": self.confidence,
            "category": self.category,
            "verifiable_via": self.verifiable_via,
        }


@dataclass
class AssumptionItem:
    assumption_id: str
    description: str
    rationale: str
    source: ItemSource = ItemSource.SYSTEM
    status: EvidenceState = EvidenceState.INFERRED
    confidence: float = 0.85
    impact_area: str = "ARCHITECTURE"

    def to_dict(self) -> dict[str, Any]:
        return {
            "assumption_id": self.assumption_id,
            "description": self.description,
            "rationale": self.rationale,
            "source": self.source.value,
            "status": self.status.value,
            "confidence": self.confidence,
            "impact_area": self.impact_area,
        }


@dataclass
class TaskPlanItem:
    task_id: str
    title: str
    agent_type: str
    dependencies: list[str] = field(default_factory=list)
    priority: int = 5
    estimated_duration_sec: float = 2.0
    target_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "agent_type": self.agent_type,
            "dependencies": self.dependencies,
            "priority": self.priority,
            "estimated_duration_sec": self.estimated_duration_sec,
            "target_paths": self.target_paths,
        }


@dataclass
class PreExecutionUnderstanding:
    mission_id: str
    prompt: str
    prompt_hash: str
    interpreted_goal: str
    mission_class: MissionClass
    novelty_class: NoveltyClass
    status: UnderstandingStatus
    requirements: list[RequirementItem] = field(default_factory=list)
    assumptions: list[AssumptionItem] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    entrypoints: list[str] = field(default_factory=list)
    affected_files: list[str] = field(default_factory=list)
    architecture_layers: list[str] = field(default_factory=list)
    task_plan: list[TaskPlanItem] = field(default_factory=list)
    validation_strategy: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    rejection_reason: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "prompt": self.prompt,
            "prompt_hash": self.prompt_hash,
            "interpreted_goal": self.interpreted_goal,
            "mission_class": self.mission_class.value,
            "novelty_class": self.novelty_class.value,
            "status": self.status.value,
            "requirements": [r.to_dict() for r in self.requirements],
            "assumptions": [a.to_dict() for a in self.assumptions],
            "unknowns": self.unknowns,
            "entrypoints": self.entrypoints,
            "affected_files": self.affected_files,
            "architecture_layers": self.architecture_layers,
            "task_plan": [t.to_dict() for t in self.task_plan],
            "validation_strategy": self.validation_strategy,
            "risks": self.risks,
            "rejection_reason": self.rejection_reason,
            "created_at": self.created_at,
        }


class PreExecutionUnderstandingEngine:
    """
    Analyzes minimalist natural language mission prompts and project context
    to produce explainable pre-execution intelligence with strict separation
    between user requirements and system assumptions.
    """

    # Invariants for Security & Policy Gates
    PROHIBITED_INTENTS = [
        ("bypass_sentinel", ["ignora o sentinel", "desativa o watchdog", "bypass sentinel", "desligar seguranca", "desativar sentinela"]),
        ("leak_secrets", ["exporta chaves privadas", "envia senhas", "dump all env secrets", "revela tokens"]),
        ("destructive_wipe", ["apaga todo o sistema", "rm -rf /", "wipe root partition", "destroi todos os ficheiros"]),
    ]

    # Invariants for Impossible / Contradictory Tasks
    CONTRADICTORY_PATTERNS = [
        ("p_vs_np", ["resolve p=np em tempo polinomial", "determine halting problem"]),
        ("impossible_constraints", ["ordena em tempo o(1) sem memoria", "sem alterar codigo mas mudando contrato"]),
        ("incompatible_runtime", ["executa binario win32 no kernel dos sem emulador"]),
    ]

    @classmethod
    def compute_prompt_hash(cls, prompt: str) -> str:
        return hashlib.sha256(prompt.strip().lower().encode("utf-8")).hexdigest()[:16]

    @classmethod
    def analyze(
        cls,
        prompt: str,
        project_context: dict[str, Any] | None = None,
        mission_id: str | None = None,
        base_dir: str = "scratch/phase31_apps",
    ) -> PreExecutionUnderstanding:
        p_clean = prompt.strip()
        p_lower = p_clean.lower()
        p_hash = cls.compute_prompt_hash(prompt)
        m_id = mission_id or f"m_{p_hash[:8]}"

        # ── 1. POLICY & SAFETY CHECK ──────────────────────────────────────────
        for rule_name, triggers in cls.PROHIBITED_INTENTS:
            if any(trig in p_lower for trig in triggers):
                return PreExecutionUnderstanding(
                    mission_id=m_id,
                    prompt=prompt,
                    prompt_hash=p_hash,
                    interpreted_goal=f"Pedido bloqueado por política de segurança: {rule_name}",
                    mission_class=MissionClass.SOFTWARE_PROJECT,
                    novelty_class=NoveltyClass.KNOWN_PATTERN,
                    status=UnderstandingStatus.BLOCKED_POLICY,
                    rejection_reason=f"Operação insegura detetada: '{rule_name}'. Rejeitado pelo Sentinel & Mission Gate.",
                    risks=["Security compromise", "Privileged credential exposure"],
                )

        # ── 2. TECHNICAL / LOGICAL INFEASIBILITY CHECK ─────────────────────────
        for rule_name, triggers in cls.CONTRADICTORY_PATTERNS:
            if any(trig in p_lower for trig in triggers):
                return PreExecutionUnderstanding(
                    mission_id=m_id,
                    prompt=prompt,
                    prompt_hash=p_hash,
                    interpreted_goal=f"Pedido impossível ou contraditório: {rule_name}",
                    mission_class=MissionClass.SOFTWARE_PROJECT,
                    novelty_class=NoveltyClass.NOVEL_PATTERN,
                    status=UnderstandingStatus.BLOCKED_TECHNICAL_CONSTRAINT,
                    rejection_reason=f"Violação de restrição técnica: o pedido '{rule_name}' não é computacionalmente realizável.",
                    risks=["Theoretical impossibility", "Unbounded execution"],
                )

        # ── 3. MISSING CRITICAL INFORMATION CHECK ─────────────────────────────
        if len(p_clean.split()) < 2:
            return PreExecutionUnderstanding(
                mission_id=m_id,
                prompt=prompt,
                prompt_hash=p_hash,
                interpreted_goal="Pedido vago ou subespecificado",
                mission_class=MissionClass.SOFTWARE_PROJECT,
                novelty_class=NoveltyClass.KNOWN_PATTERN,
                status=UnderstandingStatus.BLOCKED_REQUIRED_INFORMATION,
                unknowns=["Domínio da aplicação", "Requisitos funcionais", "Entidades a modelar"],
                rejection_reason="Prompt com informação insuficiente. Por favor especifique o objetivo da aplicação ou serviço.",
            )

        if any(term in p_lower for term in ["guarda dados confidenciais de clientes", "armazena cartoes de credito", "processa pagamentos reais"]) and not any(k in p_lower for k in ["pci", "criptografia", "vault", "tokenizacao"]):
            return PreExecutionUnderstanding(
                mission_id=m_id,
                prompt=prompt,
                prompt_hash=p_hash,
                interpreted_goal="Armazenamento de informação confidencial não especificado",
                mission_class=MissionClass.SOFTWARE_PROJECT,
                novelty_class=NoveltyClass.COMPOSED_PATTERN,
                status=UnderstandingStatus.REQUEST_INFORMATION,
                unknowns=["Política de retenção de dados", "Mecanismo de cifra/PCI", "Termos de privacidade"],
                rejection_reason="Informação de conformidade e segurança em falta para processamento de dados confidenciais.",
                risks=["Regulatory violation", "Unencrypted sensitive data"],
            )

        # ── 4. SEMANTIC ANALYSIS & CLASSIFICATION ─────────────────────────────
        import unicodedata
        p_norm = unicodedata.normalize('NFKD', p_clean.lower()).encode('ascii', 'ignore').decode('ascii')
        mission_class = cls._classify_mission(p_norm)
        novelty_class = cls._classify_novelty(p_norm, mission_class)
        interpreted_goal = cls._synthesize_interpreted_goal(p_clean, mission_class)

        # Extract requirements directly requested by the user (USER_REQUIREMENT)
        requirements = cls._extract_user_requirements(p_clean, p_norm)

        # Extract system assumptions needed to fulfill the goal (SYSTEM_ASSUMPTION)
        assumptions = cls._formulate_system_assumptions(p_norm, mission_class, requirements)

        # Extract unknown aspects not specified by user
        unknowns = cls._identify_unknowns(p_norm, requirements)

        # Generate slug and app path
        slug = cls._derive_slug(p_clean)
        app_dir = os.path.join(base_dir, slug)

        # Project Context and Affected Files
        entrypoints, affected_files, architecture_layers = cls._predict_project_impact(
            app_dir, mission_class, requirements, project_context
        )

        # Build Dynamic Task DAG
        task_plan = cls._build_dynamic_task_dag(slug, app_dir, mission_class, requirements)

        # Validation Strategy
        validation_strategy = cls._derive_validation_strategy(mission_class, requirements)

        # Risks
        risks = cls._assess_risks(mission_class, requirements, assumptions)

        return PreExecutionUnderstanding(
            mission_id=m_id,
            prompt=prompt,
            prompt_hash=p_hash,
            interpreted_goal=interpreted_goal,
            mission_class=mission_class,
            novelty_class=novelty_class,
            status=UnderstandingStatus.READY,
            requirements=requirements,
            assumptions=assumptions,
            unknowns=unknowns,
            entrypoints=entrypoints,
            affected_files=affected_files,
            architecture_layers=architecture_layers,
            task_plan=task_plan,
            validation_strategy=validation_strategy,
            risks=risks,
        )

    @classmethod
    def _classify_mission(cls, p_lower: str) -> MissionClass:
        if any(w in p_lower for w in ["corrige", "corrigir", "bug", "erro", "falha", "fix", "resolva a regressao"]):
            return MissionClass.BUG_REPAIR
        if any(w in p_lower for w in ["refatora", "refactor", "limpar", "modularizar", "escreve testes", "cobertura", "build"]):
            return MissionClass.REFACTOR_TEST_BUILD
        if any(w in p_lower for w in ["adiciona", "acrescenta", "implementa suporte a", "inclui funcionalidade"]):
            return MissionClass.FEATURE_IMPLEMENTATION
        return MissionClass.SOFTWARE_PROJECT

    @classmethod
    def _classify_novelty(cls, p_lower: str, m_class: MissionClass) -> NoveltyClass:
        dimensions = 0
        if any(w in p_lower for w in ["pesquisa", "busca", "search", "filtro", "filtrar"]):
            dimensions += 1
        if any(w in p_lower for w in ["export", "exportar", "csv", "json", "relatorio"]):
            dimensions += 1
        if any(w in p_lower for w in ["estatistica", "metricas", "totais", "dashboard", "grafico"]):
            dimensions += 1
        if any(w in p_lower for w in ["persistencia", "guardar", "salvar", "historico", "localstorage"]):
            dimensions += 1
        if any(w in p_lower for w in ["validacao", "limite", "regras de negocio", "erros"]):
            dimensions += 1

        if dimensions >= 2:
            return NoveltyClass.COMPOSED_PATTERN
        if m_class in (MissionClass.BUG_REPAIR, MissionClass.REFACTOR_TEST_BUILD):
            return NoveltyClass.NOVEL_PATTERN
        return NoveltyClass.KNOWN_PATTERN

    @classmethod
    def _synthesize_interpreted_goal(cls, prompt: str, m_class: MissionClass) -> str:
        p = prompt.strip().rstrip(".")
        if m_class == MissionClass.SOFTWARE_PROJECT:
            return f"Desenvolvimento autónomo E2E: {p}"
        if m_class == MissionClass.FEATURE_IMPLEMENTATION:
            return f"Implementação de nova funcionalidade: {p}"
        if m_class == MissionClass.BUG_REPAIR:
            return f"Diagnóstico e correção determinística de defeito: {p}"
        return f"Refatoração e validação de qualidade: {p}"

    @classmethod
    def _extract_user_requirements(cls, prompt: str, p_lower: str) -> list[RequirementItem]:
        reqs: list[RequirementItem] = []
        idx = 1

        reqs.append(RequirementItem(
            req_id=f"REQ_{idx:02d}",
            description=f"Satisfazer o objetivo principal expresso pelo utilizador: '{prompt}'",
            source=ItemSource.USER,
            status=EvidenceState.VERIFIED,
            confidence=1.0,
            category="PRIMARY_GOAL",
            verifiable_via="ACCEPTANCE_CRITERIA",
        ))
        idx += 1

        if any(w in p_lower for w in ["pesquisa", "busca", "procurar", "search"]):
            reqs.append(RequirementItem(
                req_id=f"REQ_{idx:02d}",
                description="Suporte a pesquisa em tempo real sobre os registos",
                source=ItemSource.USER,
                status=EvidenceState.VERIFIED,
                confidence=1.0,
                category="FUNCTIONAL",
                verifiable_via="BROWSER_AND_UNIT_TEST",
            ))
            idx += 1

        if any(w in p_lower for w in ["filtro", "filtros", "filtrar"]):
            reqs.append(RequirementItem(
                req_id=f"REQ_{idx:02d}",
                description="Mecanismo de filtragem dinâmica por estado ou categoria",
                source=ItemSource.USER,
                status=EvidenceState.VERIFIED,
                confidence=1.0,
                category="FUNCTIONAL",
                verifiable_via="BROWSER_AND_UNIT_TEST",
            ))
            idx += 1

        if any(w in p_lower for w in ["estatisticas", "metricas", "totais", "resumo", "contadores"]):
            reqs.append(RequirementItem(
                req_id=f"REQ_{idx:02d}",
                description="Cálculo e exibição de estatísticas agregadas e contadores de estado",
                source=ItemSource.USER,
                status=EvidenceState.VERIFIED,
                confidence=1.0,
                category="ANALYTICS",
                verifiable_via="UNIT_TEST_ASSERTION",
            ))
            idx += 1

        if any(w in p_lower for w in ["export", "exportar", "csv", "json", "download"]):
            reqs.append(RequirementItem(
                req_id=f"REQ_{idx:02d}",
                description="Capacidade de exportação de dados estruturados (JSON / CSV)",
                source=ItemSource.USER,
                status=EvidenceState.VERIFIED,
                confidence=1.0,
                category="INTEGRATION",
                verifiable_via="FUNCTIONAL_DATA_TEST",
            ))
            idx += 1

        if any(w in p_lower for w in ["persistencia", "persistente", "guardar", "armazenar", "salvar"]):
            reqs.append(RequirementItem(
                req_id=f"REQ_{idx:02d}",
                description="Persistência duradoura do estado local",
                source=ItemSource.USER,
                status=EvidenceState.VERIFIED,
                confidence=1.0,
                category="DATA_STORAGE",
                verifiable_via="STORAGE_INSPECTION",
            ))
            idx += 1

        if any(w in p_lower for w in ["validacao", "validar", "casos de erro", "impedir duplicados"]):
            reqs.append(RequirementItem(
                req_id=f"REQ_{idx:02d}",
                description="Validação rigorosa de entradas e tratamento de casos limite / erro",
                source=ItemSource.USER,
                status=EvidenceState.VERIFIED,
                confidence=1.0,
                category="DATA_INTEGRITY",
                verifiable_via="NEGATIVE_TEST_CASES",
            ))
            idx += 1

        if any(w in p_lower for w in ["testes", "teste", "regressao", "cobertura"]):
            reqs.append(RequirementItem(
                req_id=f"REQ_{idx:02d}",
                description="Suite completa de testes unitários com prevenção de regressão",
                source=ItemSource.USER,
                status=EvidenceState.VERIFIED,
                confidence=1.0,
                category="QUALITY_ASSURANCE",
                verifiable_via="UNITTEST_RUNNER",
            ))
            idx += 1

        return reqs

    @classmethod
    def _formulate_system_assumptions(
        cls,
        p_lower: str,
        m_class: MissionClass,
        reqs: list[RequirementItem],
    ) -> list[AssumptionItem]:
        assumptions: list[AssumptionItem] = []
        idx = 1

        if m_class == MissionClass.SOFTWARE_PROJECT:
            assumptions.append(AssumptionItem(
                assumption_id=f"ASM_{idx:02d}",
                description="Utilizar arquitetura decoupled: frontend reativo Vanilla JS/HTML/CSS + micro-serviço backend Python",
                rationale="Garante validação browser real independente e execução rápida sem dependências pesadas de terceiros",
                source=ItemSource.SYSTEM,
                status=EvidenceState.INFERRED,
                confidence=0.92,
                impact_area="ARCHITECTURE",
            ))
            idx += 1

            assumptions.append(AssumptionItem(
                assumption_id=f"ASM_{idx:02d}",
                description="Adotar localStorage no frontend e SQLite em memória no backend como storage engine padrão",
                rationale="Utilizador não especificou motor de base de dados externo (PostgreSQL/MySQL); SQLite em memória assegura portabilidade e isolamento determinístico",
                source=ItemSource.SYSTEM,
                status=EvidenceState.INFERRED,
                confidence=0.88,
                impact_area="STORAGE",
            ))
            idx += 1

        elif m_class == MissionClass.FEATURE_IMPLEMENTATION:
            assumptions.append(AssumptionItem(
                assumption_id=f"ASM_{idx:02d}",
                description="Preservar estritamente o contrato de API público existente e integrar a funcionalidade como extensão aditiva",
                rationale="Evita quebras de compatibilidade reversa nos entrypoints já existentes",
                source=ItemSource.SYSTEM,
                status=EvidenceState.INFERRED,
                confidence=0.95,
                impact_area="CONTRACT_PRESERVATION",
            ))
            idx += 1

        elif m_class == MissionClass.BUG_REPAIR:
            assumptions.append(AssumptionItem(
                assumption_id=f"ASM_{idx:02d}",
                description="Aplicar correção cirúrgica baseada em AST preservando semântica e adicionando asserção de teste reprodutora",
                rationale="Minimiza diff de código e impede regressão no ciclo de validação",
                source=ItemSource.SYSTEM,
                status=EvidenceState.INFERRED,
                confidence=0.96,
                impact_area="REPAIR_SAFETY",
            ))
            idx += 1

        elif m_class == MissionClass.REFACTOR_TEST_BUILD:
            assumptions.append(AssumptionItem(
                assumption_id=f"ASM_{idx:02d}",
                description="Garantir 100% de paridade comportamental verificada por testes pré e pós refatoração",
                rationale="Princípio basilar de refactoring: alteração estrutural interna sem alteração funcional externa",
                source=ItemSource.SYSTEM,
                status=EvidenceState.INFERRED,
                confidence=0.98,
                impact_area="QUALITY_GATE",
            ))
            idx += 1

        if any(r.verifiable_via == "BROWSER_AND_UNIT_TEST" for r in reqs) or m_class == MissionClass.SOFTWARE_PROJECT:
            assumptions.append(AssumptionItem(
                assumption_id=f"ASM_{idx:02d}",
                description="Construir interface com tema moderno escuro, glassmorphism e micro-animações CSS",
                rationale="Conformidade estrita com as diretrizes visuais premium do JARVIS OS",
                source=ItemSource.SYSTEM,
                status=EvidenceState.INFERRED,
                confidence=0.90,
                impact_area="USER_INTERFACE",
            ))
            idx += 1

        return assumptions

    @classmethod
    def _identify_unknowns(cls, p_lower: str, reqs: list[RequirementItem]) -> list[str]:
        unknowns = []
        if not any(k in p_lower for k in ["postgres", "sqlite", "mysql", "mongo", "redis"]):
            unknowns.append("Tecnologia de base de dados externa não especificada (assumido SQLite/localStorage)")
        if not any(k in p_lower for k in ["auth", "login", "jwt", "session", "utilizador"]):
            unknowns.append("Mecanismo de autenticação não solicitado (assumido modo monoutilizador local)")
        if not any(k in p_lower for k in ["deploy", "cloud", "docker", "aws", "port"]):
            unknowns.append("Ambiente de produção alvo não especificado (assumido runtime local)")
        return unknowns

    @classmethod
    def _derive_slug(cls, prompt: str) -> str:
        import unicodedata
        p_ascii = unicodedata.normalize('NFKD', prompt.lower()).encode('ascii', 'ignore').decode('ascii')
        p_clean = re.sub(r"[^a-zA-Z0-9\s-]", "", p_ascii).strip()
        stop_words = {"uma", "um", "de", "com", "sem", "para", "que", "os", "as", "na", "no", "cria", "adiciona", "corrige", "refatora"}
        slug_words = [w for w in p_clean.split() if w not in stop_words and len(w) > 2][:4]
        return "-".join(slug_words) or "autonomous-mission"

    @classmethod
    def _predict_project_impact(
        cls,
        app_dir: str,
        m_class: MissionClass,
        reqs: list[RequirementItem],
        project_context: dict[str, Any] | None = None,
    ) -> Tuple[list[str], list[str], list[str]]:
        entrypoints = []
        affected_files = []
        architecture_layers = []

        if m_class == MissionClass.SOFTWARE_PROJECT:
            entrypoints = [
                os.path.join(app_dir, "index.html"),
                os.path.join(app_dir, "backend_service.py"),
            ]
            affected_files = [
                os.path.join(app_dir, "index.html"),
                os.path.join(app_dir, "app.js"),
                os.path.join(app_dir, "style.css"),
                os.path.join(app_dir, "backend_service.py"),
                os.path.join(app_dir, "test_service.py"),
            ]
            architecture_layers = [
                "Presentation Layer (DOM Reactive)",
                "Service Layer (Python Business Logic)",
                "Data Layer (SQLite in-memory & LocalStorage)",
                "Quality Assurance Layer (Unittest Suite)",
            ]
        elif m_class == MissionClass.FEATURE_IMPLEMENTATION:
            entrypoints = [os.path.join(app_dir, "backend_service.py")]
            affected_files = [
                os.path.join(app_dir, "backend_service.py"),
                os.path.join(app_dir, "test_service.py"),
            ]
            architecture_layers = [
                "Service Layer (Feature Extension)",
                "Quality Assurance Layer (Feature Regression Tests)",
            ]
        elif m_class == MissionClass.BUG_REPAIR:
            entrypoints = [os.path.join(app_dir, "backend_service.py")]
            affected_files = [
                os.path.join(app_dir, "backend_service.py"),
                os.path.join(app_dir, "test_service.py"),
            ]
            architecture_layers = [
                "Fault Localization & AST Patching",
                "Regression Testing Layer",
            ]
        else: # REFACTOR_TEST_BUILD
            entrypoints = [os.path.join(app_dir, "backend_service.py")]
            affected_files = [
                os.path.join(app_dir, "backend_service.py"),
                os.path.join(app_dir, "test_service.py"),
            ]
            architecture_layers = [
                "Refactoring & Modularization Layer",
                "Contract Parity Validation",
            ]

        return entrypoints, affected_files, architecture_layers

    @classmethod
    def _build_dynamic_task_dag(
        cls,
        slug: str,
        app_dir: str,
        m_class: MissionClass,
        reqs: list[RequirementItem],
    ) -> list[TaskPlanItem]:
        tasks: list[TaskPlanItem] = []

        t_arch = TaskPlanItem(
            task_id=f"{slug}_arch_design",
            title=f"Desenho Arquitetural e Contrato de Dados ({slug})",
            agent_type="ARCHITECTURE",
            dependencies=[],
            priority=10,
            estimated_duration_sec=1.5,
            target_paths=[os.path.join(app_dir, "backend_service.py")],
        )
        tasks.append(t_arch)

        t_code_backend = TaskPlanItem(
            task_id=f"{slug}_code_backend",
            title=f"Implementação de Serviço Backend e Regras de Negócio ({slug})",
            agent_type="CODING",
            dependencies=[t_arch.task_id],
            priority=8,
            estimated_duration_sec=3.0,
            target_paths=[os.path.join(app_dir, "backend_service.py")],
        )
        tasks.append(t_code_backend)

        t_test = TaskPlanItem(
            task_id=f"{slug}_test_suite",
            title=f"Geração e Execução de Testes Automatizados ({slug})",
            agent_type="TESTING",
            dependencies=[t_code_backend.task_id],
            priority=7,
            estimated_duration_sec=2.0,
            target_paths=[os.path.join(app_dir, "test_service.py")],
        )
        tasks.append(t_test)

        if m_class == MissionClass.SOFTWARE_PROJECT:
            t_frontend = TaskPlanItem(
                task_id=f"{slug}_code_frontend",
                title=f"Implementação da Interface Web Reativa ({slug})",
                agent_type="CODING",
                dependencies=[t_arch.task_id],
                priority=8,
                estimated_duration_sec=3.0,
                target_paths=[
                    os.path.join(app_dir, "index.html"),
                    os.path.join(app_dir, "app.js"),
                    os.path.join(app_dir, "style.css"),
                ],
            )
            tasks.append(t_frontend)

            t_browser = TaskPlanItem(
                task_id=f"{slug}_browser_qa",
                title=f"Validação Browser QA Real no DOM do Chromium ({slug})",
                agent_type="BROWSER",
                dependencies=[t_frontend.task_id],
                priority=6,
                estimated_duration_sec=3.5,
                target_paths=[os.path.join(app_dir, "index.html")],
            )
            tasks.append(t_browser)

            t_review = TaskPlanItem(
                task_id=f"{slug}_review_signoff",
                title=f"Revisão Final de Critérios e Assinatura de Evidências ({slug})",
                agent_type="REVIEW",
                dependencies=[t_test.task_id, t_browser.task_id],
                priority=5,
                estimated_duration_sec=1.5,
                target_paths=[app_dir],
            )
            tasks.append(t_review)
        else:
            t_review = TaskPlanItem(
                task_id=f"{slug}_review_signoff",
                title=f"Revisão de Qualidade e Verificação de Regressão ({slug})",
                agent_type="REVIEW",
                dependencies=[t_test.task_id],
                priority=5,
                estimated_duration_sec=1.5,
                target_paths=[app_dir],
            )
            tasks.append(t_review)

        return tasks

    @classmethod
    def _derive_validation_strategy(
        cls,
        m_class: MissionClass,
        reqs: list[RequirementItem],
    ) -> list[str]:
        strategies = [
            "Verificação Sintática e AST Parsing sem diagnósticos de erro",
            "Execução de Testes Unitários com assertions rigorosas e zero tolerância a falhas",
        ]
        if m_class == MissionClass.SOFTWARE_PROJECT:
            strategies.append("Inspeção de Integridade do DOM (presença de controlos de input, botões e listas)")
            strategies.append("Validação Interativa Browser QA (ações de criação, pesquisa, filtro e persistência)")
            strategies.append("Monitorização de Exceções de Consola e Logs de Runtime")
        if any(r.category == "ANALYTICS" for r in reqs):
            strategies.append("Verificação Matemática dos Contadores e Agregações de Estatísticas")
        if any(r.category == "INTEGRATION" for r in reqs):
            strategies.append("Validação Estrutural do Payload Exportado (validação de schema JSON/CSV)")
        return strategies

    @classmethod
    def _assess_risks(
        cls,
        m_class: MissionClass,
        reqs: list[RequirementItem],
        assumptions: list[AssumptionItem],
    ) -> list[str]:
        risks = []
        if m_class == MissionClass.SOFTWARE_PROJECT:
            risks.append("Possível desfasamento de sincronização de estado entre DOM local e persistência em refresh")
        elif m_class == MissionClass.BUG_REPAIR:
            risks.append("Risco de regressão colateral em fluxos não cobertos pela asserção original")
        elif m_class == MissionClass.FEATURE_IMPLEMENTATION:
            risks.append("Possível conflito de assinaturas com callers legados do serviço")
        else:
            risks.append("Incompatibilidade de contratos durante reestruturação de imports")
        return risks

    @classmethod
    def calculate_explainability_score(
        cls,
        understanding: PreExecutionUnderstanding,
        actual_files: list[str],
        actual_tasks: list[str],
        validated_requirements: list[str],
    ) -> dict[str, Any]:
        pred_files_set = set(os.path.normpath(f).lower() for f in understanding.affected_files)
        act_files_set = set(os.path.normpath(f).lower() for f in actual_files)

        intersection_files = pred_files_set.intersection(act_files_set)
        union_files = pred_files_set.union(act_files_set)
        file_accuracy = len(intersection_files) / max(1, len(union_files))

        pred_tasks_set = set(t.task_id for t in understanding.task_plan)
        act_tasks_set = set(actual_tasks)
        task_accuracy = len(pred_tasks_set.intersection(act_tasks_set)) / max(1, len(pred_tasks_set.union(act_tasks_set)))

        req_ids = set(r.req_id for r in understanding.requirements)
        val_req_set = set(validated_requirements)
        req_accuracy = len(req_ids.intersection(val_req_set)) / max(1, len(req_ids))

        overall_planning_accuracy = (file_accuracy * 0.35) + (task_accuracy * 0.35) + (req_accuracy * 0.30)

        return {
            "overall_planning_accuracy": round(overall_planning_accuracy, 4),
            "file_prediction_accuracy": round(file_accuracy, 4),
            "task_plan_accuracy": round(task_accuracy, 4),
            "requirement_satisfaction_accuracy": round(req_accuracy, 4),
            "predicted_files_count": len(pred_files_set),
            "actual_files_count": len(act_files_set),
            "predicted_tasks_count": len(pred_tasks_set),
            "actual_tasks_count": len(act_tasks_set),
            "requirements_predicted_count": len(req_ids),
            "requirements_validated_count": len(val_req_set),
        }
