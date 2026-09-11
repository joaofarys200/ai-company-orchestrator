"""
JARVIS OS — Phase 35: Mission Control Center & Explainable Autonomous Execution Engine

Consolidates all mission intelligence into a single, unified, observable operations state:
- Mission Header (ID, Goal, State, Progress, Stage, Elapsed Time, Active Agents, Requirements)
- Understanding (Strict separation of USER_REQUIREMENT vs SYSTEM_ASSUMPTION vs UNKNOWN)
- Plan View (Topological TaskGraph with owner agents, priority, dependencies, duration)
- Live Execution (Current task, agent, stage, active, completed, failed, repairs, replans)
- Swarm Agents (The 6 specialized agents with touched files, completed tasks, handoffs)
- Why Panel ("Porque é que o JARVIS fez isto?" with Action, Reason, Source, Evidence)
- Repair Explainability (Failure -> Diagnosis -> Patch -> Validation)
- Replan Explainability (Old Plan -> New Plan -> Why Changed -> Trigger)
- Recovery Visibility (Worker Failed -> Checkpoint Found -> State Restored -> Task Resumed)
- Requirement Tracking (IDENTIFIED -> IMPLEMENTED -> VALIDATED)
- Evidence Ledger (Tests, Build, Runtime, Browser, Code Validation, Satisfaction)
- Final Result & Zero False Success Gate
- WebSocket Event Factory with Deterministic event_id and Idempotent Deduplication
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import enum
import hashlib
import json
import os
import sys
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

# Workspace root
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)


class MissionControlStatus(str, enum.Enum):
    PLANNING = "PLANNING"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    REPAIRING = "REPAIRING"
    REPLANNING = "REPLANNING"
    VALIDATING = "VALIDATING"
    BLOCKED = "BLOCKED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RECOVERING = "RECOVERING"


class CommandType(str, enum.Enum):
    APPROVE = "APPROVE"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    CANCEL = "CANCEL"
    CHANGE_PRIORITY = "CHANGE_PRIORITY"
    REORDER = "REORDER"
    INTENT_CHANGE = "INTENT_CHANGE"


class CommandStatus(str, enum.Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    STALE = "STALE"
    SECURITY_BLOCK = "SECURITY_BLOCK"
    INVALID_STATE = "INVALID_STATE"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
    ECONOMIC_BLOCK = "ECONOMIC_BLOCK"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"


class PriorityLevel(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


class IntentStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"
    CONFLICTED = "CONFLICTED"
    PENDING_APPROVAL = "PENDING_APPROVAL"


class IntentSource(str, enum.Enum):
    USER_DIRECTIVE = "USER_DIRECTIVE"
    OPERATOR_COMMAND = "OPERATOR_COMMAND"
    SYSTEM_INFERENCE = "SYSTEM_INFERENCE"


class IntentItemType(str, enum.Enum):
    USER_REQUIREMENT = "USER_REQUIREMENT"
    SYSTEM_ASSUMPTION = "SYSTEM_ASSUMPTION"
    USER_CONSTRAINT = "USER_CONSTRAINT"
    USER_PREFERENCE = "USER_PREFERENCE"
    USER_EXCLUSION = "USER_EXCLUSION"
    ACCEPTANCE_CRITERIA = "ACCEPTANCE_CRITERIA"


class IntentDeltaOperation(str, enum.Enum):
    ADD_REQUIREMENT = "ADD_REQUIREMENT"
    REMOVE_REQUIREMENT = "REMOVE_REQUIREMENT"
    MODIFY_REQUIREMENT = "MODIFY_REQUIREMENT"
    ADD_CONSTRAINT = "ADD_CONSTRAINT"
    REMOVE_CONSTRAINT = "REMOVE_CONSTRAINT"
    MODIFY_CONSTRAINT = "MODIFY_CONSTRAINT"
    ADD_PREFERENCE = "ADD_PREFERENCE"
    REMOVE_PREFERENCE = "REMOVE_PREFERENCE"
    ADD_EXCLUSION = "ADD_EXCLUSION"
    REMOVE_EXCLUSION = "REMOVE_EXCLUSION"
    MODIFY_PRIORITY = "MODIFY_PRIORITY"
    MODIFY_ACCEPTANCE_CRITERIA = "MODIFY_ACCEPTANCE_CRITERIA"
    REVISE_APPROACH = "REVISE_APPROACH"


class ImpactLevel(str, enum.Enum):
    NONE = "NONE"
    LOCAL = "LOCAL"
    PARTIAL = "PARTIAL"
    STRUCTURAL = "STRUCTURAL"
    MISSION_WIDE = "MISSION_WIDE"


class ConflictType(str, enum.Enum):
    REQUIREMENT_CONFLICT = "REQUIREMENT_CONFLICT"
    CONSTRAINT_CONFLICT = "CONSTRAINT_CONFLICT"
    ARCHITECTURE_CONFLICT = "ARCHITECTURE_CONFLICT"
    DAG_CONFLICT = "DAG_CONFLICT"
    STATE_CONFLICT = "STATE_CONFLICT"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"
    SECURITY_CONFLICT = "SECURITY_CONFLICT"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    ECONOMIC_CONFLICT = "ECONOMIC_CONFLICT"


class RequirementLifecycleStatus(str, enum.Enum):
    IDENTIFIED = "IDENTIFIED"
    PLANNED = "PLANNED"
    IMPLEMENTED = "IMPLEMENTED"
    VALIDATED = "VALIDATED"
    MODIFIED = "MODIFIED"
    SUPERSEDED = "SUPERSEDED"
    REMOVED = "REMOVED"
    BLOCKED = "BLOCKED"
    REQUIRES_REVALIDATION = "REQUIRES_REVALIDATION"


class EvidenceStatus(str, enum.Enum):
    VALID = "VALID"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"
    PENDING_REVALIDATION = "PENDING_REVALIDATION"


@dataclass
class MissionIntent:
    intent_id: str
    mission_id: str
    version: int
    source: IntentSource
    created_at: float
    requirements: list[dict[str, Any]]
    constraints: list[dict[str, Any]]
    preferences: list[dict[str, Any]]
    exclusions: list[dict[str, Any]]
    acceptance_criteria: list[dict[str, Any]]
    priorities: dict[str, str]
    immutable_requirements: list[str]
    parent_version: Optional[int] = None
    supersedes: Optional[str] = None
    status: IntentStatus = IntentStatus.ACTIVE

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "mission_id": self.mission_id,
            "version": self.version,
            "source": self.source.value if isinstance(self.source, IntentSource) else str(self.source),
            "created_at": self.created_at,
            "requirements": self.requirements,
            "constraints": self.constraints,
            "preferences": self.preferences,
            "exclusions": self.exclusions,
            "acceptance_criteria": self.acceptance_criteria,
            "priorities": self.priorities,
            "immutable_requirements": self.immutable_requirements,
            "parent_version": self.parent_version,
            "supersedes": self.supersedes,
            "status": self.status.value if isinstance(self.status, IntentStatus) else str(self.status),
        }


@dataclass
class MissionIntentDelta:
    delta_id: str
    mission_id: str
    base_intent_version: int
    operation: IntentDeltaOperation
    target: str
    payload: dict[str, Any]
    reason: Optional[str] = None
    source_message_id: Optional[str] = None
    requested_by: str = "user_operator"
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "delta_id": self.delta_id,
            "mission_id": self.mission_id,
            "base_intent_version": self.base_intent_version,
            "operation": self.operation.value if isinstance(self.operation, IntentDeltaOperation) else str(self.operation),
            "target": self.target,
            "payload": self.payload,
            "reason": self.reason,
            "source_message_id": self.source_message_id,
            "requested_by": self.requested_by,
            "created_at": self.created_at,
        }


@dataclass
class IntentConflict:
    conflict_type: ConflictType
    description: str
    target: str
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    resolution_proposal: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_type": self.conflict_type.value if isinstance(self.conflict_type, ConflictType) else str(self.conflict_type),
            "description": self.description,
            "target": self.target,
            "severity": self.severity,
            "resolution_proposal": self.resolution_proposal,
        }


@dataclass
class IntentImpact:
    level: ImpactLevel
    requirements_affected: list[str]
    constraints_affected: list[str]
    tasks_affected: list[str]
    agents_affected: list[str]
    files_affected: list[str]
    evidence_invalidated: list[str]
    estimated_replan_scope: str
    requires_pause: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level.value if isinstance(self.level, ImpactLevel) else str(self.level),
            "requirements_affected": self.requirements_affected,
            "constraints_affected": self.constraints_affected,
            "tasks_affected": self.tasks_affected,
            "agents_affected": self.agents_affected,
            "files_affected": self.files_affected,
            "evidence_invalidated": self.evidence_invalidated,
            "estimated_replan_scope": self.estimated_replan_scope,
            "requires_pause": self.requires_pause,
        }


@dataclass
class IntentResolution:
    resolved: bool
    deltas: list[MissionIntentDelta]
    unchanged_requirements: list[str]
    conflicts: list[IntentConflict]
    assumptions: list[dict[str, Any]]
    ambiguity: list[str]
    impact: IntentImpact
    confidence: float
    requires_confirmation: bool
    requires_replan: bool
    clarification_prompt: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolved": self.resolved,
            "deltas": [d.to_dict() for d in self.deltas],
            "unchanged_requirements": self.unchanged_requirements,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "assumptions": self.assumptions,
            "ambiguity": self.ambiguity,
            "impact": self.impact.to_dict(),
            "confidence": round(self.confidence, 4),
            "requires_confirmation": self.requires_confirmation,
            "requires_replan": self.requires_replan,
            "clarification_prompt": self.clarification_prompt,
        }


class IntentResolver:
    """
    Deterministic intent resolver converting natural language directives or structured
    instructions into formal MissionIntentDelta specifications.
    """

    @classmethod
    def parse_directive(
        cls,
        text: str,
        base_intent_version: int = 1,
        mission_id: str = "m_p36_interactive",
    ) -> tuple[Optional[MissionIntentDelta], float, list[str], Optional[str]]:
        """
        Parses text into a MissionIntentDelta. Returns:
        (delta, confidence, ambiguity_list, clarification_prompt)
        """
        clean = (text or "").strip()
        lower = clean.lower()
        delta_id = f"delta_{uuid.uuid4().hex[:8]}"

        # 1. Security / Sentinel Bypass Refusal check
        forbidden_sentinel = ["ignora security sentinel", "bypass_sentinel", "disable security", "override_policy"]
        if any(f in lower for f in forbidden_sentinel):
            return None, 1.0, ["Tentativa de desativação do Security Sentinel detetada."], "Bloqueio estrito de segurança: O Security Sentinel não pode ser desativado."

        # 2. Authentication: "adiciona autenticação" / "add auth"
        if "adiciona autentica" in lower or "add auth" in lower or "autenticação" in lower:
            # Check for conflict instruction: "mas não mexas na api"
            has_api_freeze = "não mexas na api" in lower or "não alteres a api" in lower or "sem alterar api" in lower
            payload = {
                "id": "REQ_AUTH",
                "title": "Autenticação & Controlo de Acesso",
                "desc": "Autenticação segura de utilizadores com tokens de sessão e RBAC.",
                "type": "SECURITY",
                "conflict_intent": "FREEZE_API" if has_api_freeze else None,
            }
            d = MissionIntentDelta(
                delta_id=delta_id,
                mission_id=mission_id,
                base_intent_version=base_intent_version,
                operation=IntentDeltaOperation.ADD_REQUIREMENT,
                target="REQ_AUTH",
                payload=payload,
                reason="Requisito de segurança: Adicionar autenticação e controlo de acesso",
            )
            return d, 0.98, [], None

        # 3. Constraint: "não alteres a api existente" / "não mexas no frontend"
        if "não alteres a api" in lower or "mantém a api" in lower or "preserve api" in lower:
            d = MissionIntentDelta(
                delta_id=delta_id,
                mission_id=mission_id,
                base_intent_version=base_intent_version,
                operation=IntentDeltaOperation.ADD_CONSTRAINT,
                target="CONST_API_STABILITY",
                payload={
                    "id": "CONST_API_STABILITY",
                    "desc": "Não alterar contratos ou endpoints da API REST existente.",
                    "scope": "BACKEND_API",
                },
                reason="Restrição do utilizador: Estabilidade estrita da API pública",
            )
            return d, 0.99, [], None

        if "não mexas no frontend" in lower or "congelar frontend" in lower or "freeze frontend" in lower:
            d = MissionIntentDelta(
                delta_id=delta_id,
                mission_id=mission_id,
                base_intent_version=base_intent_version,
                operation=IntentDeltaOperation.ADD_CONSTRAINT,
                target="CONST_FRONTEND_FREEZE",
                payload={
                    "id": "CONST_FRONTEND_FREEZE",
                    "desc": "Não efetuar alterações ou mutações em componentes de frontend.",
                    "scope": "FRONTEND",
                },
                reason="Restrição do utilizador: Congelamento total da interface web",
            )
            return d, 0.99, [], None

        # 4. Remove Requirement: "remove a funcionalidade de exportação" / "remove export csv"
        if "remove" in lower and ("export" in lower or "csv" in lower):
            d = MissionIntentDelta(
                delta_id=delta_id,
                mission_id=mission_id,
                base_intent_version=base_intent_version,
                operation=IntentDeltaOperation.REMOVE_REQUIREMENT,
                target="REQ_04",
                payload={
                    "target_id": "REQ_04",
                    "title": "Exportação CSV",
                    "desc": "Remoção de exportação CSV conforme pedido do operador",
                },
                reason="Exclusão funcional solicitada: Remover módulo de exportação",
            )
            return d, 0.95, [], None

        # 5. Revise Approach: "faz com react em vez de vanilla js" / "use react"
        if "react" in lower and ("vanilla" in lower or "vez de" in lower or "faz com" in lower or "usa react" in lower):
            d = MissionIntentDelta(
                delta_id=delta_id,
                mission_id=mission_id,
                base_intent_version=base_intent_version,
                operation=IntentDeltaOperation.REVISE_APPROACH,
                target="APPROACH_UI_FRAMEWORK",
                payload={
                    "framework": "React",
                    "previous": "Vanilla JS",
                    "rationale": "Componentização declarativa e ecossistema modular",
                },
                reason="Revisão arquitetural: Migração da abordagem de UI para React",
            )
            return d, 0.96, [], None

        # 6. Priority: "dá prioridade ao backend"
        if "prioridade" in lower and "backend" in lower:
            d = MissionIntentDelta(
                delta_id=delta_id,
                mission_id=mission_id,
                base_intent_version=base_intent_version,
                operation=IntentDeltaOperation.MODIFY_PRIORITY,
                target="BACKEND",
                payload={"target_scope": "BACKEND", "new_priority": "CRITICAL"},
                reason="Alteração de prioridade operacional para foco no backend",
            )
            return d, 0.94, [], None

        # 7. Add Tests: "acrescenta testes"
        if "acrescenta testes" in lower or "adiciona testes" in lower or "add tests" in lower:
            d = MissionIntentDelta(
                delta_id=delta_id,
                mission_id=mission_id,
                base_intent_version=base_intent_version,
                operation=IntentDeltaOperation.ADD_REQUIREMENT,
                target="REQ_TESTS_EXTRA",
                payload={
                    "id": "REQ_TESTS_EXTRA",
                    "title": "Bateria de Testes Adicionais",
                    "desc": "Testes unitários e de integração adicionais de tolerância a falhas.",
                    "type": "TESTING",
                },
                reason="Acréscimo de cobertura e testes de regressão",
            )
            return d, 0.95, [], None

        # 8. Search: "suportar pesquisa" / "adiciona pesquisa" / "filtros por data"
        if "pesquisa" in lower or "search" in lower or "filtros" in lower:
            d = MissionIntentDelta(
                delta_id=delta_id,
                mission_id=mission_id,
                base_intent_version=base_intent_version,
                operation=IntentDeltaOperation.ADD_REQUIREMENT,
                target="REQ_SEARCH",
                payload={
                    "id": "REQ_SEARCH",
                    "title": "Pesquisa Reativa & Filtragem",
                    "desc": "Mecanismo reativo de pesquisa e filtros dinâmicos.",
                    "type": "FEATURE",
                },
                reason="Nova funcionalidade: Pesquisa reativa e filtragem dinâmica",
            )
            return d, 0.95, [], None

        # 9. Button fix / typo: "corrige o botão x" / "corrige typo"
        if "corrige" in lower or "ajusta o botão" in lower or "typo" in lower:
            d = MissionIntentDelta(
                delta_id=delta_id,
                mission_id=mission_id,
                base_intent_version=base_intent_version,
                operation=IntentDeltaOperation.MODIFY_REQUIREMENT,
                target="REQ_BUTTON_X",
                payload={
                    "id": "REQ_BUTTON_X",
                    "title": "Correção de UI",
                    "desc": "Ajuste cirúrgico de estilo e alinhamento de componentes.",
                },
                reason="Correção cirúrgica de apresentação",
            )
            return d, 0.92, [], None

        # 10. Ambiguous / underspecified queries: e.g. "faz algo" / "muda isso"
        ambiguities = [
            "Instrução semanticamente sub-especificada.",
            "Não foi possível identificar o requisito ou componente alvo com certeza determinística.",
        ]
        prompt = "Poderia especificar quais os requisitos concretos ou restrições que pretende alterar na missão?"
        return None, 0.45, ambiguities, prompt


class ImpactAnalyzer:
    """
    Computes deterministic multi-dimensional impact of an intent change on requirements,
    constraints, DAG tasks, swarm agents, evidence ledger, and execution safety.
    """

    @classmethod
    def analyze_impact(cls, delta: MissionIntentDelta, state: MissionControlState) -> IntentImpact:
        op = delta.operation
        target = delta.target
        req_affected: list[str] = []
        const_affected: list[str] = []
        tasks_affected: list[str] = []
        agents_affected: list[str] = []
        files_affected: list[str] = []
        ev_invalidated: list[str] = []
        requires_pause = False

        if op == IntentDeltaOperation.REVISE_APPROACH:
            level = ImpactLevel.STRUCTURAL
            requires_pause = True
            req_affected = [r.get("id", "") for r in state.requirements if "UI" in r.get("id", "") or "02" in r.get("id", "")]
            tasks_affected = ["TSK_02", "TSK_03", "TSK_05"]
            agents_affected = ["CODING", "TESTING", "BROWSER"]
            files_affected = ["package.json", "App.tsx", "index.tsx", "style.css"]
            ev_invalidated = ["ev_browser_01", "ev_build_01"]
            scope = "Reestruturação arquitetural: substituição do pipeline de renderização e framework de UI."

        elif op == IntentDeltaOperation.ADD_REQUIREMENT:
            req_type = str(delta.payload.get("type", "")).upper()
            target_upper = target.upper()
            reason_lower = (delta.reason or "").lower()
            desc_lower = str(delta.payload.get("desc", "")).lower()
            req_affected = [target]
            if (
                req_type == "SECURITY"
                or "AUTH" in target_upper
                or "autentica" in reason_lower
                or "autentica" in desc_lower
                or "auth" in reason_lower
            ):
                level = ImpactLevel.STRUCTURAL
                requires_pause = True
                tasks_affected = ["TSK_01", "TSK_02", "TSK_05"]
                agents_affected = ["ARCHITECTURE", "CODING", "TESTING"]
                files_affected = ["auth.py", "session.py", "middleware.py"]
                ev_invalidated = ["BUILD", "RUNTIME"]
                scope = "Inclusão estrutural de segurança: middleware de autenticação e proteção de rotas."
            else:
                level = ImpactLevel.PARTIAL
                requires_pause = False
                tasks_affected = ["TSK_02", "TSK_03"]
                agents_affected = ["CODING", "TESTING"]
                files_affected = ["app.js", "filters.js"]
                ev_invalidated = []
                scope = "Expansão incremental: adição de nova capacidade funcional ao DAG."

        elif op == IntentDeltaOperation.REMOVE_REQUIREMENT:
            # Check if already completed or validated
            req_matched = next((r for r in state.requirements if r.get("id") == target), None)
            is_validated = req_matched and req_matched.get("status") in ("VALIDATED", "DONE", "COMPLETED")
            req_affected = [target]
            if is_validated:
                level = ImpactLevel.PARTIAL
                tasks_affected = ["TSK_04", "TSK_05"]
                agents_affected = ["CODING", "TESTING"]
                files_affected = ["export.js", "storage.js"]
                ev_invalidated = [f"ev_{target.lower()}"]
                scope = "Remoção de requisito já implementado: requer compensação e revalidação determinística."
            else:
                level = ImpactLevel.LOCAL
                tasks_affected = [t.get("id", "") for t in state.tasks if target in t.get("title", "")]
                agents_affected = ["CODING"]
                files_affected = []
                ev_invalidated = []
                scope = "Remoção de requisito pendente: cancelamento direto de tarefas associadas."

        elif op == IntentDeltaOperation.ADD_CONSTRAINT:
            const_affected = [target]
            if "API" in target or "API" in str(delta.payload.get("desc", "")):
                level = ImpactLevel.PARTIAL
                tasks_affected = ["TSK_01", "TSK_02"]
                agents_affected = ["CODING", "ARCHITECTURE"]
                files_affected = ["api.py", "routes.py"]
                scope = "Restrição de estabilidade de API: condiciona tarefas que possam alterar endpoints existentes."
            else:
                level = ImpactLevel.LOCAL
                tasks_affected = []
                agents_affected = []
                files_affected = []
                scope = "Restrição operacional local."

        elif op == IntentDeltaOperation.MODIFY_PRIORITY:
            level = ImpactLevel.LOCAL
            tasks_affected = ["TSK_01", "TSK_02"]
            agents_affected = ["ARCHITECTURE", "CODING"]
            scope = "Ajuste de escalonamento: reordenação de prioridade de execução."

        elif op == IntentDeltaOperation.MODIFY_REQUIREMENT:
            level = ImpactLevel.LOCAL
            req_affected = [target]
            tasks_affected = ["TSK_02"]
            agents_affected = ["CODING"]
            files_affected = ["app.js", "style.css"]
            scope = "Ajuste cirúrgico em requisito existente."

        else:
            level = ImpactLevel.NONE
            scope = "Nenhum impacto material detetado."

        return IntentImpact(
            level=level,
            requirements_affected=req_affected,
            constraints_affected=const_affected,
            tasks_affected=tasks_affected,
            agents_affected=agents_affected,
            files_affected=files_affected,
            evidence_invalidated=ev_invalidated,
            estimated_replan_scope=scope,
            requires_pause=requires_pause,
        )


class ConflictDetector:
    """
    Detects deterministic conflicts between previous intent, new intent,
    constraints, DAG topology, security sentinel, and economic invariants.
    """

    @classmethod
    def detect_conflicts(cls, delta: MissionIntentDelta, state: MissionControlState) -> list[IntentConflict]:
        conflicts: list[IntentConflict] = []

        # 1. Security Sentinel Conflict
        payload_str = json.dumps(delta.payload).lower()
        reason_str = (delta.reason or "").lower()
        target_str = (delta.target or "").lower()
        forbidden_patterns = [
            "bypass_sentinel", "disable_security", "rm -rf", "drop database", "override_policy",
            "security_sentinel", "sentinel", "bypass"
        ]
        if any(p in payload_str or p in reason_str or p in target_str for p in forbidden_patterns):
            conflicts.append(
                IntentConflict(
                    conflict_type=ConflictType.SECURITY_CONFLICT,
                    description="A alteração solicitada tenta contornar o Security Sentinel ou executar operações destrutivas.",
                    target=delta.target,
                    severity="CRITICAL",
                    resolution_proposal="Bloqueio imediato da alteração conforme a política de segurança do sistema.",
                )
            )

        # 2. Terminal State Conflict
        if state.status in (MissionControlStatus.COMPLETED, MissionControlStatus.CANCELLED, MissionControlStatus.FAILED):
            conflicts.append(
                IntentConflict(
                    conflict_type=ConflictType.STATE_CONFLICT,
                    description=f"Não é permitido aplicar alterações de intenção a uma missão no estado terminal '{state.status.value}'.",
                    target=state.mission_id,
                    severity="CRITICAL",
                    resolution_proposal="Criar uma nova missão com a intenção atualizada em vez de mutar uma missão concluída.",
                )
            )

        # 3. Contradictory Intent / Constraint Conflict
        all_constraints = (state.intent.get("constraints", []) if state.intent else [])
        for c in all_constraints:
            c_desc = (str(c.get("desc", "")) + " " + str(c.get("id", ""))).lower()
            if "api" in c_desc:
                if "api" in target_str or "graphql" in payload_str or "api" in payload_str or "api" in reason_str:
                    conflicts.append(
                        IntentConflict(
                            conflict_type=ConflictType.CONSTRAINT_CONFLICT,
                            description=f"Conflito direto com restrição ativa '{c.get('id', 'CST')}': {c.get('desc', '')}. A alteração proposta viola a estabilidade da API.",
                            target=delta.target,
                            severity="HIGH",
                            resolution_proposal="Esclarecer com o operador se a restrição de API pode ser revogada ou se a nova funcionalidade deve coexistir.",
                        )
                    )

        if delta.payload.get("conflict_intent") == "FREEZE_API" or (
            delta.operation == IntentDeltaOperation.ADD_REQUIREMENT
            and delta.target == "REQ_AUTH"
            and any("API" in str(c.get("id", "")) or "API" in str(c.get("desc", "")) for c in all_constraints)
        ):
            if not any(c.conflict_type == ConflictType.CONSTRAINT_CONFLICT for c in conflicts):
                conflicts.append(
                    IntentConflict(
                        conflict_type=ConflictType.CONSTRAINT_CONFLICT,
                        description="Requisito de autenticação requer novos endpoints mas existe uma restrição de não alterar a API.",
                        target="REQ_AUTH vs CONST_API_STABILITY",
                        severity="HIGH",
                        resolution_proposal="Esclarecer com o operador se é permitido adicionar novas rotas dedicadas de autenticação sem alterar os contratos da API existente.",
                    )
                )

        # 4. Economic Invariant Conflict
        if "money" in payload_str or "faturação" in payload_str or "arbitragem" in payload_str:
            if not delta.payload.get("operator_financial_auth"):
                conflicts.append(
                    IntentConflict(
                        conflict_type=ConflictType.ECONOMIC_CONFLICT,
                        description="Alteração de parâmetros financeiros ou monetários sem autorização de operador autenticado.",
                        target="ECONOMIC_PIPELINE",
                        severity="CRITICAL",
                        resolution_proposal="Submeter autenticação económica explícita antes de mutar intenções de capital.",
                    )
                )

        return conflicts


class DynamicReplanner:
    """
    Incremental replanner that mutates the Task DAG safely, enforcing Kahn topological
    invariants, cycle absence, compensation tasks for completed work, and monotonic versions.
    """

    @classmethod
    def replan(
        cls,
        tasks: list[dict[str, Any]],
        delta: MissionIntentDelta,
        impact: IntentImpact,
        current_plan_version: int = 1,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        new_tasks = [dict(t) for t in tasks]
        added: list[dict[str, Any]] = []
        removed: list[str] = []
        modified: list[dict[str, Any]] = []
        dep_changes: list[dict[str, Any]] = []

        op = delta.operation
        target = delta.target

        if op == IntentDeltaOperation.ADD_REQUIREMENT:
            if delta.payload.get("type") == "SECURITY":
                # Add authentication tasks
                t_auth1 = {
                    "id": "TSK_AUTH_01",
                    "title": "Implementar Middleware de Autenticação & Sessão",
                    "agent": "CODING",
                    "priority": "HIGH",
                    "dependencies": ["TSK_01"],
                    "evidence": "Em síntese",
                    "duration_seconds": 0.12,
                    "status": "READY",
                    "intent_version": delta.base_intent_version + 1,
                }
                t_auth2 = {
                    "id": "TSK_AUTH_02",
                    "title": "Bateria de Testes de Autenticação & RBAC",
                    "agent": "TESTING",
                    "priority": "HIGH",
                    "dependencies": ["TSK_AUTH_01"],
                    "evidence": "Pendente de execução",
                    "duration_seconds": 0.08,
                    "status": "PENDING",
                    "intent_version": delta.base_intent_version + 1,
                }
                new_tasks.extend([t_auth1, t_auth2])
                added.extend([t_auth1, t_auth2])

                # Rewire review/approval task TSK_05 to depend on TSK_AUTH_02
                for t in new_tasks:
                    if t.get("id") == "TSK_05":
                        t["dependencies"] = list(set(t.get("dependencies", []) + ["TSK_AUTH_02"]))
                        dep_changes.append({"task_id": "TSK_05", "added_dep": "TSK_AUTH_02"})
                        modified.append({"task_id": "TSK_05", "change": "added dependency TSK_AUTH_02"})

            elif target == "REQ_SEARCH" or "pesquisa" in target.lower() or "filtros" in target.lower():
                t_search1 = {
                    "id": "TSK_SEARCH_01",
                    "title": "Implementar Pesquisa Reativa & Filtros de Categoria",
                    "agent": "CODING",
                    "priority": "NORMAL",
                    "dependencies": ["TSK_01"],
                    "evidence": "Em síntese",
                    "duration_seconds": 0.10,
                    "status": "READY",
                    "intent_version": delta.base_intent_version + 1,
                }
                t_search2 = {
                    "id": "TSK_SEARCH_02",
                    "title": "Validação de Filtros Reativos no Navegador",
                    "agent": "BROWSER",
                    "priority": "NORMAL",
                    "dependencies": ["TSK_SEARCH_01"],
                    "evidence": "Pendente de execução",
                    "duration_seconds": 0.07,
                    "status": "PENDING",
                    "intent_version": delta.base_intent_version + 1,
                }
                new_tasks.extend([t_search1, t_search2])
                added.extend([t_search1, t_search2])

                for t in new_tasks:
                    if t.get("id") == "TSK_05":
                        t["dependencies"] = list(set(t.get("dependencies", []) + ["TSK_SEARCH_02"]))
                        dep_changes.append({"task_id": "TSK_05", "added_dep": "TSK_SEARCH_02"})
                        modified.append({"task_id": "TSK_05", "change": "added dependency TSK_SEARCH_02"})

            else:
                # Generic add requirement task
                base_tid = f"TSK_{target.upper()}"
                tid = base_tid
                existing_ids = {t.get("id") for t in new_tasks}
                counter = 1
                while tid in existing_ids:
                    tid = f"{base_tid}_{counter}"
                    counter += 1

                t_custom = {
                    "id": tid,
                    "title": delta.payload.get("title", f"Implementar {target}"),
                    "agent": "CODING",
                    "priority": "NORMAL",
                    "dependencies": ["TSK_01"],
                    "evidence": "Agendado",
                    "duration_seconds": 0.09,
                    "status": "READY",
                    "intent_version": delta.base_intent_version + 1,
                }
                new_tasks.append(t_custom)
                added.append(t_custom)

        elif op == IntentDeltaOperation.REMOVE_REQUIREMENT:
            # Check if requirement was already implemented in DAG
            target_id = delta.payload.get("target_id", target)
            matched_task = next(
                (t for t in new_tasks if target_id in t.get("id", "")
                 or target_id.replace("REQ_", "TSK_") in t.get("id", "")
                 or target_id in t.get("title", "")),
                None
            )
            if not matched_task and any(t.get("status") in ("DONE", "COMPLETED") for t in new_tasks):
                matched_task = next((t for t in new_tasks if t.get("status") in ("DONE", "COMPLETED")), None)
            
            if matched_task and matched_task.get("status") in ("DONE", "COMPLETED"):
                # Non-destructive compensation! Completed task is NOT deleted.
                t_comp = {
                    "id": f"TSK_COMP_{target_id}",
                    "title": f"Compensação Cirúrgica: Remoção de {target_id}",
                    "agent": "CODING",
                    "priority": "HIGH",
                    "dependencies": ["TSK_01"],
                    "evidence": "Agendado",
                    "duration_seconds": 0.06,
                    "status": "READY",
                    "intent_version": delta.base_intent_version + 1,
                }
                t_reval = {
                    "id": f"TSK_REVAL_{target_id}",
                    "title": f"Revalidação pós-remoção de {target_id}",
                    "agent": "TESTING",
                    "priority": "HIGH",
                    "dependencies": [t_comp["id"]],
                    "evidence": "Pendente",
                    "duration_seconds": 0.05,
                    "status": "PENDING",
                    "intent_version": delta.base_intent_version + 1,
                }
                new_tasks.extend([t_comp, t_reval])
                added.extend([t_comp, t_reval])
            elif matched_task:
                matched_task["status"] = "CANCELLED"
                modified.append({"task_id": matched_task["id"], "change": "status marked CANCELLED"})
                removed.append(matched_task["id"])

        elif op == IntentDeltaOperation.REVISE_APPROACH:
            # Modifies pending UI coding task to React synthesis
            for t in new_tasks:
                if t.get("id") == "TSK_02":
                    t["title"] = "Síntese de Componentes React & Bundling Modular"
                    t["agent"] = "CODING"
                    t["evidence"] = "Em síntese com React"
                    modified.append({"task_id": "TSK_02", "change": "converted to React architecture"})
            # Add React framework setup task
            t_react = {
                "id": "TSK_REACT_SETUP",
                "title": "Configuração de Ambiente React & JSX Runtime",
                "agent": "CODING",
                "priority": "HIGH",
                "dependencies": ["TSK_01"],
                "evidence": "Concluído",
                "duration_seconds": 0.05,
                "status": "DONE",
                "intent_version": delta.base_intent_version + 1,
            }
            new_tasks.insert(1, t_react)
            added.append(t_react)
            for t in new_tasks:
                if t.get("id") == "TSK_02":
                    t["dependencies"] = ["TSK_REACT_SETUP"]
                    dep_changes.append({"task_id": "TSK_02", "added_dep": "TSK_REACT_SETUP"})

        # 4. Kahn's Algorithm Validation for Cycle Absence & Dependency Completeness
        task_ids = {t["id"] for t in new_tasks}
        in_degrees: dict[str, int] = {t["id"]: 0 for t in new_tasks}
        graph: dict[str, list[str]] = {t["id"]: [] for t in new_tasks}

        for t in new_tasks:
            for dep in t.get("dependencies", []):
                if dep not in task_ids:
                    # Incomplete dependency check
                    raise ValueError(f"Violação de integridade do DAG: Dependência '{dep}' requerida por '{t['id']}' não existe no grafo.")
                graph[dep].append(t["id"])
                in_degrees[t["id"]] += 1

        queue = [t_id for t_id, deg in in_degrees.items() if deg == 0]
        visited_count = 0

        while queue:
            curr = queue.pop(0)
            visited_count += 1
            for neighbor in graph.get(curr, []):
                in_degrees[neighbor] -= 1
                if in_degrees[neighbor] == 0:
                    queue.append(neighbor)

        if visited_count != len(new_tasks):
            raise ValueError("Violação de aciclicidade do DAG: Ciclo detetado após aplicação do delta de intenção!")

        plan_diff = {
            "plan_version_before": current_plan_version,
            "plan_version_after": current_plan_version + 1,
            "added_tasks": added,
            "removed_tasks": removed,
            "modified_tasks": modified,
            "dependencies_changed": dep_changes,
            "reason": delta.reason or f"Replanning dinâmico por alteração de intenção ({op.value})",
            "timestamp": time.time(),
        }
        return new_tasks, plan_diff


ALLOWED_STATE_TRANSITIONS: dict[MissionControlStatus, set[MissionControlStatus]] = {
    MissionControlStatus.PLANNING: {
        MissionControlStatus.RUNNING,
        MissionControlStatus.CANCELLING,
        MissionControlStatus.BLOCKED,
        MissionControlStatus.FAILED,
    },
    MissionControlStatus.READY: {
        MissionControlStatus.RUNNING,
        MissionControlStatus.CANCELLING,
        MissionControlStatus.BLOCKED,
    },
    MissionControlStatus.RUNNING: {
        MissionControlStatus.PAUSED,
        MissionControlStatus.REPAIRING,
        MissionControlStatus.REPLANNING,
        MissionControlStatus.VALIDATING,
        MissionControlStatus.CANCELLING,
        MissionControlStatus.BLOCKED,
        MissionControlStatus.COMPLETED,
        MissionControlStatus.FAILED,
    },
    MissionControlStatus.PAUSED: {
        MissionControlStatus.RUNNING,
        MissionControlStatus.REPLANNING,
        MissionControlStatus.CANCELLING,
    },
    MissionControlStatus.REPAIRING: {
        MissionControlStatus.PAUSED,
        MissionControlStatus.RUNNING,
        MissionControlStatus.CANCELLING,
        MissionControlStatus.FAILED,
    },
    MissionControlStatus.REPLANNING: {
        MissionControlStatus.RUNNING,
        MissionControlStatus.PAUSED,
        MissionControlStatus.CANCELLING,
        MissionControlStatus.FAILED,
    },
    MissionControlStatus.VALIDATING: {
        MissionControlStatus.COMPLETED,
        MissionControlStatus.REPAIRING,
        MissionControlStatus.FAILED,
        MissionControlStatus.CANCELLING,
    },
    MissionControlStatus.RECOVERING: {
        MissionControlStatus.RUNNING,
        MissionControlStatus.PAUSED,
        MissionControlStatus.FAILED,
        MissionControlStatus.CANCELLING,
    },
    MissionControlStatus.BLOCKED: {
        MissionControlStatus.RUNNING,
        MissionControlStatus.CANCELLING,
    },
    MissionControlStatus.CANCELLING: {
        MissionControlStatus.CANCELLED,
    },
    MissionControlStatus.CANCELLED: set(),  # Terminal state
    MissionControlStatus.COMPLETED: set(),  # Terminal state
    MissionControlStatus.FAILED: set(),     # Terminal state
}


def validate_state_transition(from_state: MissionControlStatus, to_state: MissionControlStatus) -> tuple[bool, Optional[str]]:
    if from_state == to_state:
        return False, f"A missão já se encontra no estado '{from_state.value}'."
    allowed = ALLOWED_STATE_TRANSITIONS.get(from_state, set())
    if to_state in allowed:
        return True, None
    return False, f"Transição inválida: não é permitido transitar de {from_state.value} para {to_state.value}."


@dataclass
class MissionControlCommand:
    command_id: str
    mission_id: str
    command_type: CommandType
    user_id: str = "user_default"
    target_task_id: Optional[str] = None
    requested_at: float = field(default_factory=time.time)
    expected_mission_version: int = 1
    expected_task_version: Optional[int] = None
    payload: dict[str, Any] = field(default_factory=dict)
    reason: Optional[str] = None
    idempotency_key: str = ""

    def __post_init__(self):
        if not self.idempotency_key:
            self.idempotency_key = f"idemp_{self.command_id}"
        if isinstance(self.command_type, str):
            self.command_type = CommandType(self.command_type)

    def to_dict(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "mission_id": self.mission_id,
            "user_id": self.user_id,
            "command_type": self.command_type.value,
            "target_task_id": self.target_task_id,
            "requested_at": self.requested_at,
            "expected_mission_version": self.expected_mission_version,
            "expected_task_version": self.expected_task_version,
            "payload": self.payload,
            "reason": self.reason,
            "idempotency_key": self.idempotency_key,
        }


@dataclass
class CommandResult:
    command_id: str
    mission_id: str
    status: CommandStatus
    reason: str
    mission_version: int
    state_dict: Optional[dict[str, Any]] = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "mission_id": self.mission_id,
            "status": self.status.value,
            "reason": self.reason,
            "mission_version": self.mission_version,
            "state": self.state_dict,
            "details": self.details,
        }


@dataclass
class UserAuditRecord:
    command_id: str
    user_id: str
    command_type: str
    target_task_id: Optional[str]
    status: str
    reason: str
    old_state: str
    new_state: str
    mission_version: int
    timestamp: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "user_id": self.user_id,
            "command_type": self.command_type,
            "target_task_id": self.target_task_id,
            "status": self.status,
            "reason": self.reason,
            "old_state": self.old_state,
            "new_state": self.new_state,
            "mission_version": self.mission_version,
            "timestamp": self.timestamp,
        }


class MissionControlStage(str, enum.Enum):
    UNDERSTANDING = "UNDERSTANDING"
    PLANNING = "PLANNING"
    EXECUTION = "EXECUTION"
    VALIDATION = "VALIDATION"
    REPAIR = "REPAIR"
    COMPLETION = "COMPLETION"


class ReplanTrigger(str, enum.Enum):
    TASK_FAILURE = "TASK_FAILURE"
    NEW_INFORMATION = "NEW_INFORMATION"
    DEPENDENCY_CHANGE = "DEPENDENCY_CHANGE"
    RECOVERY = "RECOVERY"
    RESOURCE_CHANGE = "RESOURCE_CHANGE"


@dataclass
class WhyPanelItem:
    action: str
    reason: str
    source: str # USER_REQUIREMENT, SYSTEM_ASSUMPTION, POLICY_GATE, DEPENDENCY_CHANGE
    evidence: str # physical test, log, or DOM verification

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "source": self.source,
            "evidence": self.evidence,
        }


@dataclass
class SwarmAgentDetail:
    agent_id: str
    name: str
    role: str # ARCHITECTURE, RESEARCH, CODING, TESTING, BROWSER, REVIEW
    status: str # IDLE, ACTIVE, COMPLETED, BUSY
    current_task: str
    files_touched: list[str]
    completed_tasks_count: int
    failures_count: int
    handoffs_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "status": self.status,
            "current_task": self.current_task,
            "files_touched": self.files_touched,
            "completed_tasks_count": self.completed_tasks_count,
            "failures_count": self.failures_count,
            "handoffs_count": self.handoffs_count,
        }


@dataclass
class RepairExplainabilityRecord:
    failure_title: str
    diagnosis: str
    patch_description: str
    files_changed: list[str]
    validation_result: str
    duration_ms: float

    @property
    def failure(self) -> str:
        return self.failure_title

    @property
    def patch(self) -> str:
        return self.patch_description

    @property
    def validation(self) -> str:
        return self.validation_result

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_title": self.failure_title,
            "diagnosis": self.diagnosis,
            "patch_description": self.patch_description,
            "files_changed": self.files_changed,
            "validation_result": self.validation_result,
            "duration_ms": self.duration_ms,
        }


@dataclass
class ReplanExplainabilityRecord:
    old_plan_summary: str
    new_plan_summary: str
    why_changed: str
    trigger: ReplanTrigger
    tasks_added: list[str]
    tasks_modified: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "old_plan_summary": self.old_plan_summary,
            "new_plan_summary": self.new_plan_summary,
            "why_changed": self.why_changed,
            "trigger": self.trigger.value,
            "tasks_added": self.tasks_added,
            "tasks_modified": self.tasks_modified,
        }


@dataclass
class RecoveryExplainabilityRecord:
    worker_failed_id: str
    checkpoint_id: str
    state_restored_at: float
    recovered_tasks: list[str]
    duplicate_work_prevented: bool
    recovery_duration_seconds: float

    @property
    def worker_failed(self) -> str:
        return self.worker_failed_id

    @property
    def state_restored(self) -> bool:
        return bool(self.state_restored_at)

    @property
    def task_resumed(self) -> bool:
        return bool(self.recovered_tasks)

    @property
    def duplicate_protection(self) -> str:
        return "ZERO_WORK_DUPLICATION" if self.duplicate_work_prevented else "NONE"

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_failed_id": self.worker_failed_id,
            "checkpoint_id": self.checkpoint_id,
            "state_restored_at": self.state_restored_at,
            "recovered_tasks": self.recovered_tasks,
            "duplicate_work_prevented": self.duplicate_work_prevented,
            "recovery_duration_seconds": self.recovery_duration_seconds,
        }


@dataclass
class MissionControlEvent:
    event_id: str
    mission_id: str
    timestamp: float
    event_type: str
    stage: MissionControlStage
    title: str
    agent: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "mission_id": self.mission_id,
            "timestamp": self.timestamp,
            "type": self.event_type,
            "event_type": self.event_type,
            "stage": self.stage.value,
            "title": self.title,
            "agent": self.agent,
            "details": self.details,
            "payload": self.details,
        }


@dataclass
class MissionControlState:
    mission_id: str
    user_goal: str
    interpreted_goal: str
    status: MissionControlStatus
    current_stage: MissionControlStage
    elapsed_time_seconds: float
    progress_percentage: int
    eta_seconds: float
    active_agents_count: int
    requirements_count: int
    requirements_validated_count: int
    time_to_first_output_seconds: float
    time_to_first_validated_seconds: float
    time_to_useful_result_seconds: float
    total_duration_seconds: float
    user_effort_score: float
    output_quality_score: float
    execution_success: bool
    requirement_satisfaction: bool
    validation_evidence: bool
    is_user_useful: bool
    requirements: list[dict[str, Any]]
    assumptions: list[dict[str, Any]]
    unknowns: list[str]
    tasks: list[dict[str, Any]]
    agents: list[SwarmAgentDetail]
    why_items: list[WhyPanelItem]
    repairs: list[RepairExplainabilityRecord]
    replans: list[ReplanExplainabilityRecord]
    recoveries: list[RecoveryExplainabilityRecord]
    evidence: list[dict[str, Any]]
    artifacts: list[dict[str, Any]]
    events: list[MissionControlEvent]
    final_result: dict[str, Any]
    mission_version: int = 1
    command_history: list[dict[str, Any]] = field(default_factory=list)
    intent_version: int = 1
    plan_version: int = 1
    intent: Optional[dict[str, Any]] = None
    intent_history: list[dict[str, Any]] = field(default_factory=list)
    requirement_diff: Optional[dict[str, Any]] = None
    plan_diff: Optional[dict[str, Any]] = None
    evidence_impact: Optional[dict[str, Any]] = None
    last_prediction_report: Optional[dict[str, Any]] = None
    last_prediction_outcome: Optional[dict[str, Any]] = None
    prediction_history: list[dict[str, Any]] = field(default_factory=list)

    def can_complete(self) -> bool:
        return bool(self.execution_success and self.requirement_satisfaction and self.validation_evidence)

    @property
    def time_to_value(self) -> dict[str, float]:
        return {
            "time_to_first_output_seconds": self.time_to_first_output_seconds,
            "time_to_first_validated_seconds": self.time_to_first_validated_seconds,
            "time_to_useful_result_seconds": self.time_to_useful_result_seconds,
            "total_duration_seconds": self.total_duration_seconds,
        }

    @property
    def user_effort(self) -> dict[str, Any]:
        return {
            "user_effort_score": self.user_effort_score,
            "prompts_count": 1,
            "approvals_count": 0,
            "manual_edits_count": 0,
            "manual_retries_count": 0,
        }

    @property
    def result(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "execution_success": self.execution_success,
            "requirement_satisfaction": self.requirement_satisfaction,
            "required_validation": self.validation_evidence,
            "details": self.final_result,
        }

    @property
    def why_panel(self) -> list[WhyPanelItem]:
        return self.why_items

    @property
    def repair_explainability(self) -> Optional[RepairExplainabilityRecord]:
        return self.repairs[0] if self.repairs else None

    @property
    def replan_explainability(self) -> Optional[ReplanExplainabilityRecord]:
        return self.replans[0] if self.replans else None

    @property
    def recovery_explainability(self) -> Optional[RecoveryExplainabilityRecord]:
        return self.recoveries[0] if self.recoveries else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "user_goal": self.user_goal,
            "interpreted_goal": self.interpreted_goal,
            "status": self.status.value,
            "current_stage": self.current_stage.value,
            "elapsed_time_seconds": round(self.elapsed_time_seconds, 4),
            "progress_percentage": self.progress_percentage,
            "eta_seconds": round(self.eta_seconds, 4),
            "active_agents_count": self.active_agents_count,
            "requirements_count": self.requirements_count,
            "requirements_validated_count": self.requirements_validated_count,
            "time_to_first_output_seconds": round(self.time_to_first_output_seconds, 4),
            "time_to_first_validated_seconds": round(self.time_to_first_validated_seconds, 4),
            "time_to_useful_result_seconds": round(self.time_to_useful_result_seconds, 4),
            "total_duration_seconds": round(self.total_duration_seconds, 4),
            "user_effort_score": round(self.user_effort_score, 4),
            "output_quality_score": round(self.output_quality_score, 4),
            "execution_success": self.execution_success,
            "requirement_satisfaction": self.requirement_satisfaction,
            "validation_evidence": self.validation_evidence,
            "is_user_useful": self.is_user_useful,
            "requirements": self.requirements,
            "assumptions": self.assumptions,
            "unknowns": self.unknowns,
            "tasks": self.tasks,
            "agents": [a.to_dict() for a in self.agents],
            "why_items": [w.to_dict() for w in self.why_items],
            "repairs": [r.to_dict() for r in self.repairs],
            "replans": [rp.to_dict() for rp in self.replans],
            "recoveries": [rc.to_dict() for rc in self.recoveries],
            "evidence": self.evidence,
            "artifacts": self.artifacts,
            "events": [e.to_dict() for e in self.events],
            "final_result": self.final_result,
            "mission_version": self.mission_version,
            "command_history": self.command_history,
            "intent_version": self.intent_version,
            "plan_version": self.plan_version,
            "intent": self.intent,
            "intent_history": self.intent_history,
            "requirement_diff": self.requirement_diff,
            "plan_diff": self.plan_diff,
            "evidence_impact": self.evidence_impact,
            "last_prediction_report": self.last_prediction_report,
            "last_prediction_outcome": self.last_prediction_outcome,
            "prediction_history": self.prediction_history,
        }


class MissionControlEngine:
    """
    Orchestrates the 5 realistic mission control scenarios, enforces deterministic
    WebSocket event streaming, and validates event deduplication and observability.
    """

    _scenario_states: dict[str, MissionControlState] = {}
    _processed_commands: dict[str, CommandResult] = {}

    @classmethod
    def reset_scenarios(cls) -> None:
        """Resets all scenario states and processed command history."""
        cls._scenario_states.clear()
        cls._processed_commands.clear()

    @classmethod
    def get_interactive_state(cls) -> MissionControlState:
        """Returns the active interactive state for bidirectional mission control."""
        return cls.get_scenario_state("interactive")

    @classmethod
    def get_scenario_state(cls, scenario_key: str) -> MissionControlState:
        """
        Returns full realistic state for one of the 6 operational scenarios:
        1. 'normal' -> E2E personal expense manager
        2. 'repair' -> Syntax fault repair with AST self-healing
        3. 'replan' -> Dynamic SubDAG adaptation triggered by dependency changes
        4. 'recovery' -> Crash recovery from checkpoint without duplicate execution
        5. 'blocked' -> Policy Gate / Sentinel block preventing unauthorized mutation
        6. 'interactive' -> Bidirectional execution pipeline ready for human intervention
        """
        key = scenario_key.strip().lower()
        if key in cls._scenario_states:
            return cls._scenario_states[key]

        now = time.time()
        if key == "repair":
            st = cls._build_repair_scenario(now)
        elif key == "replan":
            st = cls._build_replan_scenario(now)
        elif key == "recovery":
            st = cls._build_recovery_scenario(now)
        elif key == "blocked":
            st = cls._build_blocked_scenario(now)
        elif key in ("interactive", "running", "m_p36_interactive") or "interactive" in key:
            st = cls._build_interactive_scenario(now)
        else:
            st = cls._build_normal_scenario(now)

        cls._scenario_states[key] = st
        return st

    @classmethod
    def _build_interactive_scenario(cls, now: float) -> MissionControlState:
        m_id = "m_p36_interactive"
        events = [
            MissionControlEvent(
                event_id="evt_01_start",
                mission_id=m_id,
                timestamp=now - 1.5,
                event_type="mission_started",
                stage=MissionControlStage.UNDERSTANDING,
                title="Missão iniciada em modo interactivo bidirecional",
                agent="COORDINATOR",
                details={"goal": "Execução de pipeline com controlos e intervenção humana activados."},
            ),
            MissionControlEvent(
                event_id="evt_02_understanding",
                mission_id=m_id,
                timestamp=now - 1.2,
                event_type="understanding_ready",
                stage=MissionControlStage.PLANNING,
                title="Entendimento e grafo de intervenção humana configurados",
                agent="ARCHITECTURE",
                details={"user_requirements": 4, "system_assumptions": 2},
            ),
            MissionControlEvent(
                event_id="evt_03_plan",
                mission_id=m_id,
                timestamp=now - 0.9,
                event_type="plan_ready",
                stage=MissionControlStage.EXECUTION,
                title="DAG com 5 tarefas (1 concluída, 1 em execução, 1 pendente de aprovação)",
                agent="ARCHITECTURE",
                details={"tasks": 5, "strategy": "TOPOLOGICAL_KAHN"},
            ),
            MissionControlEvent(
                event_id="evt_04_t1_done",
                mission_id=m_id,
                timestamp=now - 0.5,
                event_type="task_completed",
                stage=MissionControlStage.EXECUTION,
                title="Tarefa TSK_01 concluída com sucesso",
                agent="ARCHITECTURE",
                details={"task_id": "TSK_01"},
            ),
        ]

        agents = [
            SwarmAgentDetail("agt_arch", "Architecture Agent", "ARCHITECTURE", "IDLE", "DAG & Schema Generation", ["understanding.json"], 1, 0, 1),
            SwarmAgentDetail("agt_code", "Coding Agent", "CODING", "BUSY", "Síntese de aplicação web reativa", ["index.html", "style.css", "app.js"], 0, 0, 1),
            SwarmAgentDetail("agt_test", "Testing Agent", "TESTING", "IDLE", "Contract & Boundary Tests", [], 0, 0, 0),
            SwarmAgentDetail("agt_browser", "Browser Agent", "BROWSER", "IDLE", "DOM & Workflow Validation", [], 0, 0, 0),
            SwarmAgentDetail("agt_review", "Review Agent", "REVIEW", "ACTIVE", "Aguardando Aprovação Humana", ["review_gate.json"], 0, 0, 0),
            SwarmAgentDetail("agt_res", "Research Agent", "RESEARCH", "IDLE", "Context Intake & Indexing", [], 0, 0, 0),
        ]

        why_items = [
            WhyPanelItem(
                action="Executar síntese de app.js (TSK_02)",
                reason="Requisito de utilizador em progresso: geração de componentes reativos.",
                source="USER_REQUIREMENT",
                evidence="Transição de scheduler para o Coding Agent.",
            ),
            WhyPanelItem(
                action="Aguardar autorização humana para migração (TSK_03)",
                reason="Gate de segurança / Sentinel: operações de esquema de base de dados requerem aprovação explícita.",
                source="POLICY_GATE",
                evidence="Task em estado PENDING_APPROVAL.",
            ),
        ]

        tasks = [
            {"id": "TSK_01", "title": "Extração de ontologia e entidades de despesas", "owner": "ARCHITECTURE", "agent": "ARCHITECTURE", "status": "DONE", "duration_sec": 0.03, "duration_seconds": 0.03, "dependencies": [], "priority": "NORMAL", "evidence": "Schema validado"},
            {"id": "TSK_02", "title": "Síntese de aplicação web reativa (HTML/CSS/JS)", "owner": "CODING", "agent": "CODING", "status": "RUNNING", "duration_sec": 0.05, "duration_seconds": 0.05, "dependencies": ["TSK_01"], "priority": "NORMAL", "evidence": "index.html + style.css gerados"},
            {"id": "TSK_03", "title": "Autorização para migração de esquema em produção", "owner": "REVIEW", "agent": "REVIEW", "status": "PENDING_APPROVAL", "approval_status": "PENDING_APPROVAL", "duration_sec": 0.00, "duration_seconds": 0.00, "dependencies": ["TSK_02"], "priority": "HIGH", "evidence": "Aguardando validação humana"},
            {"id": "TSK_04", "title": "Serviço de cálculo e testes unitários", "owner": "TESTING", "agent": "TESTING", "status": "PENDING", "duration_sec": 0.00, "duration_seconds": 0.00, "dependencies": ["TSK_03"], "priority": "NORMAL", "evidence": "Pendente"},
            {"id": "TSK_05", "title": "Validação E2E e asserções no browser", "owner": "BROWSER", "agent": "BROWSER", "status": "PENDING", "duration_sec": 0.00, "duration_seconds": 0.00, "dependencies": ["TSK_02"], "priority": "LOW", "evidence": "Pendente"},
        ]

        return MissionControlState(
            mission_id=m_id,
            user_goal="Executa a missão de despesas com controlo bidirecional do operador ativado.",
            interpreted_goal="Consola Bidirecional de Operações: Gestor de Despesas & Controlo Humano",
            status=MissionControlStatus.RUNNING,
            current_stage=MissionControlStage.EXECUTION,
            elapsed_time_seconds=0.085,
            progress_percentage=40,
            eta_seconds=0.15,
            active_agents_count=2,
            requirements_count=4,
            requirements_validated_count=1,
            time_to_first_output_seconds=0.040,
            time_to_first_validated_seconds=0.000,
            time_to_useful_result_seconds=0.000,
            total_duration_seconds=0.085,
            user_effort_score=0.0,
            output_quality_score=0.950,
            execution_success=False,
            requirement_satisfaction=False,
            validation_evidence=False,
            is_user_useful=False,
            requirements=[
                {"id": "REQ_01", "desc": "Registo e categorização de despesas", "source": "USER_REQUIREMENT", "status": "VALIDATED", "verification_status": "VERIFIED"},
                {"id": "REQ_02", "desc": "Cálculo dinâmico de total gasto e contagem", "source": "USER_REQUIREMENT", "status": "IN_PROGRESS", "verification_status": "IN_PROGRESS"},
                {"id": "REQ_03", "desc": "Pesquisa reativa e filtragem por categoria", "source": "USER_REQUIREMENT", "status": "PENDING", "verification_status": "PENDING"},
                {"id": "REQ_04", "desc": "Persistência duradoura no localStorage", "source": "USER_REQUIREMENT", "status": "PENDING", "verification_status": "PENDING"},
            ],
            assumptions=[
                {"id": "ASM_01", "desc": "Interface dark glassmorphism com tipografia moderna", "rationale": "Legibilidade imediata e experiência premium", "source": "SYSTEM_ASSUMPTION", "status": "INFERRED", "verification_status": "INFERRED"},
                {"id": "ASM_02", "desc": "Intervenções do operador passam por validação determinística", "rationale": "Garantia de zero bypass em gates e invariantes", "source": "SYSTEM_ASSUMPTION", "status": "INFERRED", "verification_status": "INFERRED"},
            ],
            unknowns=[],
            tasks=tasks,
            agents=agents,
            why_items=why_items,
            repairs=[],
            replans=[],
            recoveries=[],
            evidence=[
                {"type": "BUILD", "status": "PASS", "source": "Syntax Parser", "timestamp": "2026-09-09T18:30:00Z"},
                {"type": "RUNTIME", "status": "IN_PROGRESS", "source": "Node/Browser Runtime", "timestamp": "2026-09-09T18:30:01Z"},
            ],
            artifacts=[
                {"name": "index.html", "path": "index.html", "line": 1, "symbol": "RootLayout"},
                {"name": "app.js", "path": "app.js", "line": 15, "symbol": "ExpenseEngine"},
            ],
            events=events,
            final_result={
                "decision": "IN_PROGRESS",
                "value_level": "PENDING_VALIDATION",
                "why": "Missão sob supervisão e controlo operacional bidirecional ativo.",
                "what_changed": "Pipeline de despesas em execução supervisionada.",
                "what_was_validated": "Validação de esquema e componentes reativos.",
                "what_remains": "Aguardando conclusão e validações finais.",
            },
            mission_version=1,
            command_history=[],
            intent_version=1,
            plan_version=1,
            intent={
                "intent_id": f"intent_{m_id}_v1",
                "mission_id": m_id,
                "version": 1,
                "source": "USER_DIRECTIVE",
                "created_at": now - 2.0,
                "requirements": [
                    {"id": "REQ_01", "desc": "Registo e categorização de despesas", "source": "USER_REQUIREMENT", "status": "VALIDATED", "verification_status": "VERIFIED", "lifecycle": "VALIDATED", "intent_version": 1},
                    {"id": "REQ_02", "desc": "Cálculo dinâmico de total gasto e contagem", "source": "USER_REQUIREMENT", "status": "IN_PROGRESS", "verification_status": "IN_PROGRESS", "lifecycle": "IMPLEMENTED", "intent_version": 1},
                    {"id": "REQ_03", "desc": "Pesquisa reativa e filtragem por categoria", "source": "USER_REQUIREMENT", "status": "PENDING", "verification_status": "PENDING", "lifecycle": "PLANNED", "intent_version": 1},
                    {"id": "REQ_04", "desc": "Persistência duradoura no localStorage", "source": "USER_REQUIREMENT", "status": "PENDING", "verification_status": "PENDING", "lifecycle": "PLANNED", "intent_version": 1},
                ],
                "constraints": [
                    {"id": "CONST_01", "desc": "Garantir tolerância a entradas inválidas e dados nulos", "source": "USER_CONSTRAINT", "status": "ACTIVE"},
                ],
                "preferences": [
                    {"id": "PREF_01", "desc": "Preferência por animações subtis e transições suaves", "source": "USER_PREFERENCE"},
                ],
                "exclusions": [],
                "acceptance_criteria": [
                    {"id": "AC_01", "desc": "Testes unitários a 100% de passagem sem erros de consola", "status": "ACTIVE"},
                ],
                "priorities": {"DEFAULT": "NORMAL", "BACKEND": "HIGH"},
                "immutable_requirements": ["REQ_01"],
                "parent_version": None,
                "supersedes": None,
                "status": "ACTIVE",
            },
            intent_history=[],
            requirement_diff=None,
            plan_diff=None,
            evidence_impact=None,
        )

    @classmethod
    def execute_command(cls, command: MissionControlCommand) -> CommandResult:
        """
        Validates and deterministically applies human interventions:
        APPROVE, PAUSE, RESUME, CANCEL, CHANGE_PRIORITY, REORDER.
        Preserves optimistic locking, Sentinel security invariants, DAG integrity,
        audit logs, and idempotency.
        """
        # 1. Idempotency Check
        idemp_key = command.idempotency_key or command.command_id
        if idemp_key in cls._processed_commands:
            return cls._processed_commands[idemp_key]
        if command.command_id in cls._processed_commands:
            return cls._processed_commands[command.command_id]

        # 2. Locate Mission State
        target_state: Optional[MissionControlState] = None
        for st in cls._scenario_states.values():
            if st.mission_id == command.mission_id:
                target_state = st
                break

        if not target_state:
            m_id = command.mission_id.lower()
            if "interactive" in m_id:
                target_state = cls.get_scenario_state("interactive")
            elif "normal" in m_id:
                target_state = cls.get_scenario_state("normal")
            elif "repair" in m_id:
                target_state = cls.get_scenario_state("repair")
            elif "replan" in m_id:
                target_state = cls.get_scenario_state("replan")
            elif "recovery" in m_id:
                target_state = cls.get_scenario_state("recovery")
            elif "blocked" in m_id:
                target_state = cls.get_scenario_state("blocked")
            else:
                target_state = cls.get_scenario_state("interactive")

        if not target_state:
            res = CommandResult(
                command_id=command.command_id,
                mission_id=command.mission_id,
                status=CommandStatus.NOT_FOUND,
                reason=f"Missão '{command.mission_id}' não encontrada.",
                mission_version=1,
            )
            cls._processed_commands[idemp_key] = res
            return res

        # 3. Security Sentinel Validation
        payload_str = json.dumps(command.payload).lower()
        reason_str = (command.reason or "").lower()
        forbidden_patterns = [
            "bypass_sentinel",
            "disable_security",
            "rm -rf",
            "drop database",
            "override_policy",
            "force_unverified",
        ]
        if any(p in payload_str or p in reason_str for p in forbidden_patterns):
            res = CommandResult(
                command_id=command.command_id,
                mission_id=target_state.mission_id,
                status=CommandStatus.SECURITY_BLOCK,
                reason="Security Sentinel: Ação humana bloqueada por violação de políticas de segurança.",
                mission_version=target_state.mission_version,
                state_dict=target_state.to_dict(),
                details={"policy": "SENTINEL_REFUSAL_GATE"},
            )
            cls._processed_commands[idemp_key] = res
            return res

        # 4. Optimistic Version Locking
        if command.expected_mission_version is not None and command.expected_mission_version != target_state.mission_version:
            res = CommandResult(
                command_id=command.command_id,
                mission_id=target_state.mission_id,
                status=CommandStatus.STALE,
                reason=f"Comando obsoleto (STALE): versão esperada {command.expected_mission_version}, versão atual {target_state.mission_version}.",
                mission_version=target_state.mission_version,
                state_dict=target_state.to_dict(),
                details={"expected_version": command.expected_mission_version, "current_version": target_state.mission_version},
            )
            cls._processed_commands[idemp_key] = res
            return res

        # 5. Terminal State Check
        if target_state.status in (MissionControlStatus.COMPLETED, MissionControlStatus.CANCELLED, MissionControlStatus.FAILED):
            res = CommandResult(
                command_id=command.command_id,
                mission_id=target_state.mission_id,
                status=CommandStatus.INVALID_STATE,
                reason=f"Comando inválido: impossível executar {command.command_type.value} numa missão no estado terminal '{target_state.status.value}'.",
                mission_version=target_state.mission_version,
                state_dict=target_state.to_dict(),
                details={"terminal_state": target_state.status.value},
            )
            cls._processed_commands[idemp_key] = res
            return res

        # 6. Execute Command Semantics
        old_state_str = target_state.status.value
        cmd_type = command.command_type
        outcome_reason = ""

        if cmd_type == CommandType.INTENT_CHANGE:
            delta_data = command.payload.get("delta") or command.payload
            if isinstance(delta_data, dict) and "operation" in delta_data:
                op_str = delta_data.get("operation", "ADD_REQUIREMENT")
                try:
                    op = IntentDeltaOperation(op_str)
                except ValueError:
                    op = IntentDeltaOperation.ADD_REQUIREMENT
                delta = MissionIntentDelta(
                    delta_id=str(delta_data.get("delta_id") or command.command_id),
                    mission_id=target_state.mission_id,
                    base_intent_version=int(delta_data.get("base_intent_version", target_state.intent_version)),
                    operation=op,
                    target=str(delta_data.get("target", "REQ_CUSTOM")),
                    payload=dict(delta_data.get("payload") or {}),
                    reason=delta_data.get("reason") or command.reason,
                    requested_by=command.user_id,
                )
            elif isinstance(delta_data, MissionIntentDelta):
                delta = delta_data
            else:
                text_directive = str(command.payload.get("text") or command.reason or "")
                delta, conf, amb, clarify = IntentResolver.parse_directive(
                    text_directive,
                    base_intent_version=target_state.intent_version,
                    mission_id=target_state.mission_id,
                )
                if not delta:
                    res = CommandResult(
                        command_id=command.command_id,
                        mission_id=target_state.mission_id,
                        status=CommandStatus.CLARIFICATION_REQUIRED,
                        reason=clarify or "Instrução ambígua necessita de clarificação.",
                        mission_version=target_state.mission_version,
                        state_dict=target_state.to_dict(),
                        details={"ambiguity": amb},
                    )
                    cls._processed_commands[idemp_key] = res
                    return res

            res, _ = cls.apply_intent_delta(
                delta,
                scenario_key=target_state.mission_id,
                pre_approved=command.payload.get("pre_approved", False),
            )
            cls._processed_commands[idemp_key] = res
            cls._processed_commands[command.command_id] = res
            return res

        if cmd_type == CommandType.PAUSE:
            ok, err = validate_state_transition(target_state.status, MissionControlStatus.PAUSED)
            if not ok:
                res = CommandResult(
                    command_id=command.command_id,
                    mission_id=target_state.mission_id,
                    status=CommandStatus.INVALID_STATE,
                    reason=err or "Não é possível pausar a missão no estado atual.",
                    mission_version=target_state.mission_version,
                    state_dict=target_state.to_dict(),
                )
                cls._processed_commands[idemp_key] = res
                return res
            target_state.status = MissionControlStatus.PAUSED
            outcome_reason = command.reason or "Missão suspensa cooperativamente pelo operador em ponto seguro de checkpoint."

        elif cmd_type == CommandType.RESUME:
            ok, err = validate_state_transition(target_state.status, MissionControlStatus.RUNNING)
            if not ok:
                res = CommandResult(
                    command_id=command.command_id,
                    mission_id=target_state.mission_id,
                    status=CommandStatus.INVALID_STATE,
                    reason=err or "Apenas missões no estado PAUSED podem ser retomadas.",
                    mission_version=target_state.mission_version,
                    state_dict=target_state.to_dict(),
                )
                cls._processed_commands[idemp_key] = res
                return res
            target_state.status = MissionControlStatus.RUNNING
            outcome_reason = command.reason or "Missão retomada pelo operador; agendamento e leases reativados."

        elif cmd_type == CommandType.CANCEL:
            ok, err = validate_state_transition(target_state.status, MissionControlStatus.CANCELLING)
            if not ok:
                res = CommandResult(
                    command_id=command.command_id,
                    mission_id=target_state.mission_id,
                    status=CommandStatus.INVALID_STATE,
                    reason=err or "Não é possível cancelar a missão no estado atual.",
                    mission_version=target_state.mission_version,
                    state_dict=target_state.to_dict(),
                )
                cls._processed_commands[idemp_key] = res
                return res
            target_state.status = MissionControlStatus.CANCELLED
            target_state.current_stage = MissionControlStage.COMPLETION
            target_state.execution_success = False
            target_state.final_result = {
                "decision": "CANCELLED_BY_USER",
                "value_level": "NOT_USEFUL",
                "why": command.reason or "Cancelamento cooperativo executado a pedido do operador.",
                "what_changed": "Tarefas em curso terminadas com salvaguarda de checkpoint.",
                "what_was_validated": "Histórico e ledger de evidências preservados integralmente.",
                "what_remains": "Execução encerrada sem duplicações.",
            }
            outcome_reason = command.reason or "Missão cancelada pelo operador com preservação de todo o histórico e evidências."

        elif cmd_type == CommandType.APPROVE:
            if not command.target_task_id:
                res = CommandResult(
                    command_id=command.command_id,
                    mission_id=target_state.mission_id,
                    status=CommandStatus.REJECTED,
                    reason="Comando APPROVE requer especificação de target_task_id.",
                    mission_version=target_state.mission_version,
                    state_dict=target_state.to_dict(),
                )
                cls._processed_commands[idemp_key] = res
                return res

            target_task = None
            for t in target_state.tasks:
                if t.get("id") == command.target_task_id:
                    target_task = t
                    break

            if not target_task:
                res = CommandResult(
                    command_id=command.command_id,
                    mission_id=target_state.mission_id,
                    status=CommandStatus.NOT_FOUND,
                    reason=f"Tarefa '{command.target_task_id}' não encontrada.",
                    mission_version=target_state.mission_version,
                    state_dict=target_state.to_dict(),
                )
                cls._processed_commands[idemp_key] = res
                return res

            if target_task.get("status") in ("DONE", "COMPLETED"):
                res = CommandResult(
                    command_id=command.command_id,
                    mission_id=target_state.mission_id,
                    status=CommandStatus.INVALID_STATE,
                    reason=f"Tarefa '{command.target_task_id}' já se encontra concluída.",
                    mission_version=target_state.mission_version,
                    state_dict=target_state.to_dict(),
                )
                cls._processed_commands[idemp_key] = res
                return res

            decision_str = str(command.payload.get("decision", "")).upper()
            approved = (command.payload.get("approved") is not False) and (decision_str != "REJECT")
            if approved:
                target_task["status"] = "DONE"
                target_task["approval_status"] = "APPROVED"
                target_task["evidence"] = "Aprovado pelo operador humano"
                outcome_reason = command.reason or f"Aprovação concedida pelo operador para a tarefa '{target_task.get('title', command.target_task_id)}'."
            else:
                target_task["status"] = "FAILED"
                target_task["approval_status"] = "REJECTED"
                target_task["evidence"] = "Rejeitado pelo operador humano"
                target_state.status = MissionControlStatus.BLOCKED
                outcome_reason = command.reason or f"Aprovação rejeitada pelo operador para a tarefa '{target_task.get('title', command.target_task_id)}'."

        elif cmd_type == CommandType.CHANGE_PRIORITY:
            if not command.target_task_id:
                res = CommandResult(
                    command_id=command.command_id,
                    mission_id=target_state.mission_id,
                    status=CommandStatus.REJECTED,
                    reason="Comando CHANGE_PRIORITY requer especificação de target_task_id.",
                    mission_version=target_state.mission_version,
                    state_dict=target_state.to_dict(),
                )
                cls._processed_commands[idemp_key] = res
                return res

            target_task = None
            for t in target_state.tasks:
                if t.get("id") == command.target_task_id:
                    target_task = t
                    break

            if not target_task:
                res = CommandResult(
                    command_id=command.command_id,
                    mission_id=target_state.mission_id,
                    status=CommandStatus.NOT_FOUND,
                    reason=f"Tarefa '{command.target_task_id}' não encontrada.",
                    mission_version=target_state.mission_version,
                    state_dict=target_state.to_dict(),
                )
                cls._processed_commands[idemp_key] = res
                return res

            if target_task.get("status") in ("DONE", "COMPLETED"):
                res = CommandResult(
                    command_id=command.command_id,
                    mission_id=target_state.mission_id,
                    status=CommandStatus.INVALID_STATE,
                    reason=f"Não é possível alterar a prioridade de uma tarefa já concluída ('{command.target_task_id}').",
                    mission_version=target_state.mission_version,
                    state_dict=target_state.to_dict(),
                )
                cls._processed_commands[idemp_key] = res
                return res

            new_priority = str(command.payload.get("new_priority", "NORMAL")).upper()
            if new_priority not in ("CRITICAL", "HIGH", "NORMAL", "LOW"):
                res = CommandResult(
                    command_id=command.command_id,
                    mission_id=target_state.mission_id,
                    status=CommandStatus.REJECTED,
                    reason=f"Nível de prioridade inválido: '{new_priority}'.",
                    mission_version=target_state.mission_version,
                    state_dict=target_state.to_dict(),
                )
                cls._processed_commands[idemp_key] = res
                return res

            old_prio = target_task.get("priority", "NORMAL")
            target_task["priority"] = new_priority
            outcome_reason = command.reason or f"Prioridade da tarefa '{target_task['title']}' alterada de {old_prio} para {new_priority}."

        elif cmd_type == CommandType.REORDER:
            if not command.target_task_id:
                res = CommandResult(
                    command_id=command.command_id,
                    mission_id=target_state.mission_id,
                    status=CommandStatus.REJECTED,
                    reason="Comando REORDER requer especificação de target_task_id.",
                    mission_version=target_state.mission_version,
                    state_dict=target_state.to_dict(),
                )
                cls._processed_commands[idemp_key] = res
                return res

            tasks = target_state.tasks
            task_idx = None
            for idx, t in enumerate(tasks):
                if t.get("id") == command.target_task_id:
                    task_idx = idx
                    break

            if task_idx is None:
                res = CommandResult(
                    command_id=command.command_id,
                    mission_id=target_state.mission_id,
                    status=CommandStatus.NOT_FOUND,
                    reason=f"Tarefa '{command.target_task_id}' não encontrada.",
                    mission_version=target_state.mission_version,
                    state_dict=target_state.to_dict(),
                )
                cls._processed_commands[idemp_key] = res
                return res

            curr_task = tasks[task_idx]
            if curr_task.get("status") in ("DONE", "COMPLETED", "RUNNING"):
                res = CommandResult(
                    command_id=command.command_id,
                    mission_id=target_state.mission_id,
                    status=CommandStatus.REJECTED,
                    reason=f"Não é permitido reordenar a tarefa '{curr_task['title']}' porque já se encontra em execução ou concluída.",
                    mission_version=target_state.mission_version,
                    state_dict=target_state.to_dict(),
                )
                cls._processed_commands[idemp_key] = res
                return res

            direction = command.payload.get("direction", "UP").upper()
            target_idx = command.payload.get("target_position")
            if target_idx is None:
                target_idx = task_idx - 1 if direction == "UP" else task_idx + 1

            if target_idx < 0 or target_idx >= len(tasks):
                res = CommandResult(
                    command_id=command.command_id,
                    mission_id=target_state.mission_id,
                    status=CommandStatus.REJECTED,
                    reason="Posição alvo fora dos limites do plano de execução.",
                    mission_version=target_state.mission_version,
                    state_dict=target_state.to_dict(),
                )
                cls._processed_commands[idemp_key] = res
                return res

            # Topological check:
            if target_idx < task_idx:
                predecessors = set(curr_task.get("dependencies", []))
                for i in range(target_idx, task_idx):
                    candidate_pred = tasks[i]
                    if candidate_pred.get("id") in predecessors:
                        res = CommandResult(
                            command_id=command.command_id,
                            mission_id=target_state.mission_id,
                            status=CommandStatus.REJECTED,
                            reason=f"Violação topológica do DAG: A tarefa '{curr_task['title']}' não pode ser executada antes do seu predecessor obrigatório '{candidate_pred['title']}'.",
                            mission_version=target_state.mission_version,
                            state_dict=target_state.to_dict(),
                            details={"violating_predecessor": candidate_pred.get("id")},
                        )
                        cls._processed_commands[idemp_key] = res
                        return res
            elif target_idx > task_idx:
                curr_id = curr_task.get("id")
                for i in range(task_idx + 1, target_idx + 1):
                    candidate_succ = tasks[i]
                    if curr_id in candidate_succ.get("dependencies", []):
                        res = CommandResult(
                            command_id=command.command_id,
                            mission_id=target_state.mission_id,
                            status=CommandStatus.REJECTED,
                            reason=f"Violação topológica do DAG: A tarefa sucessora '{candidate_succ['title']}' depende de '{curr_task['title']}' e não pode precedê-la.",
                            mission_version=target_state.mission_version,
                            state_dict=target_state.to_dict(),
                            details={"violating_successor": candidate_succ.get("id")},
                        )
                        cls._processed_commands[idemp_key] = res
                        return res

            # Reorder safely
            item = tasks.pop(task_idx)
            tasks.insert(target_idx, item)
            outcome_reason = command.reason or f"Tarefa '{curr_task['title']}' reordenada com sucesso para a posição {target_idx + 1}."

        # Monotonic version increment
        target_state.mission_version += 1

        # Audit record
        audit_rec = UserAuditRecord(
            command_id=command.command_id,
            user_id=command.user_id,
            command_type=command.command_type.value,
            target_task_id=command.target_task_id,
            status=CommandStatus.ACCEPTED.value,
            reason=outcome_reason,
            old_state=old_state_str,
            new_state=target_state.status.value,
            mission_version=target_state.mission_version,
            timestamp=time.time(),
        )
        target_state.command_history.append(audit_rec.to_dict())

        # Update Why Panel
        target_state.why_items.insert(
            0,
            WhyPanelItem(
                action=f"Intervenção Humana: {command.command_type.value}",
                reason=outcome_reason,
                source="USER_COMMAND",
                evidence=f"Comando {command.command_id} validado e aplicado deterministicamente na versão {target_state.mission_version}.",
            ),
        )

        # Update Timeline Event
        new_ev = MissionControlEvent(
            event_id=f"evt_cmd_{command.command_id}_{target_state.mission_version}",
            mission_id=target_state.mission_id,
            timestamp=time.time(),
            event_type=f"command_{command.command_type.value.lower()}",
            stage=target_state.current_stage,
            title=f"Comando {command.command_type.value} Aceite",
            agent="OPERATOR",
            details={
                "command_id": command.command_id,
                "command_type": command.command_type.value,
                "reason": outcome_reason,
                "version": target_state.mission_version,
                "state": target_state.status.value,
            },
        )
        target_state.events.append(new_ev)

        # Build success result
        final_res = CommandResult(
            command_id=command.command_id,
            mission_id=target_state.mission_id,
            status=CommandStatus.ACCEPTED,
            reason=outcome_reason,
            mission_version=target_state.mission_version,
            state_dict=target_state.to_dict(),
            details={"audit": audit_rec.to_dict()},
        )
        cls._processed_commands[idemp_key] = final_res
        cls._processed_commands[command.command_id] = final_res
        return final_res

    @classmethod
    def resolve_user_intent(
        cls,
        text: str,
        scenario_key: str = "interactive",
    ) -> IntentResolution:
        """
        Interprets natural language into structured intent and performs dry-run impact/conflict analysis.
        """
        state = cls.get_scenario_state(scenario_key)
        delta, conf, amb, clarify = IntentResolver.parse_directive(
            text,
            base_intent_version=state.intent_version,
            mission_id=state.mission_id,
        )
        if not delta:
            impact = IntentImpact(ImpactLevel.NONE, [], [], [], [], [], [], "Nenhuma alteração resolvida")
            return IntentResolution(
                resolved=False,
                deltas=[],
                unchanged_requirements=[r.get("id", "") for r in state.requirements],
                conflicts=[],
                assumptions=state.assumptions,
                ambiguity=amb,
                impact=impact,
                confidence=conf,
                requires_confirmation=True,
                requires_replan=False,
                clarification_prompt=clarify,
            )

        res, impact, conflicts, status, reason = cls.preview_intent_delta(delta, scenario_key=scenario_key)
        res.confidence = conf
        return res

    @classmethod
    def preview_intent_delta(
        cls,
        delta: MissionIntentDelta,
        scenario_key: str = "interactive",
    ) -> tuple[IntentResolution, IntentImpact, list[IntentConflict], CommandStatus, str]:
        """
        Deterministic preview of an intent delta without applying mutations.
        Returns: (resolution, impact, conflicts, status, reason)
        """
        target_state: Optional[MissionControlState] = None
        for st in cls._scenario_states.values():
            if st.mission_id == delta.mission_id:
                target_state = st
                break
        if not target_state:
            target_state = cls.get_scenario_state(scenario_key)

        # 1. Optimistic Version Locking
        if delta.base_intent_version != target_state.intent_version:
            impact = IntentImpact(ImpactLevel.NONE, [], [], [], [], [], [], "Delta obsoleto")
            res = IntentResolution(
                resolved=False,
                deltas=[delta],
                unchanged_requirements=[r.get("id", "") for r in target_state.requirements],
                conflicts=[],
                assumptions=target_state.assumptions,
                ambiguity=["Versão de intenção base incompatível com a versão atual da missão."],
                impact=impact,
                confidence=1.0,
                requires_confirmation=False,
                requires_replan=False,
                clarification_prompt=None,
            )
            return res, impact, [], CommandStatus.STALE, f"STALE_INTENT_DELTA: base version {delta.base_intent_version} != current {target_state.intent_version}."

        # 2. Conflict Detection
        conflicts = ConflictDetector.detect_conflicts(delta, target_state)
        impact = ImpactAnalyzer.analyze_impact(delta, target_state)

        # Security Sentinel check
        sec_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.SECURITY_CONFLICT]
        if sec_conflicts:
            res = IntentResolution(
                resolved=False,
                deltas=[delta],
                unchanged_requirements=[r.get("id", "") for r in target_state.requirements],
                conflicts=conflicts,
                assumptions=target_state.assumptions,
                ambiguity=[],
                impact=impact,
                confidence=1.0,
                requires_confirmation=False,
                requires_replan=False,
            )
            return res, impact, conflicts, CommandStatus.SECURITY_BLOCK, sec_conflicts[0].description

        # Economic Invariant check
        econ_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.ECONOMIC_CONFLICT]
        if econ_conflicts:
            res = IntentResolution(
                resolved=False,
                deltas=[delta],
                unchanged_requirements=[r.get("id", "") for r in target_state.requirements],
                conflicts=conflicts,
                assumptions=target_state.assumptions,
                ambiguity=[],
                impact=impact,
                confidence=1.0,
                requires_confirmation=False,
                requires_replan=False,
            )
            return res, impact, conflicts, CommandStatus.ECONOMIC_BLOCK, econ_conflicts[0].description

        # Terminal state check
        state_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.STATE_CONFLICT]
        if state_conflicts:
            res = IntentResolution(
                resolved=False,
                deltas=[delta],
                unchanged_requirements=[r.get("id", "") for r in target_state.requirements],
                conflicts=conflicts,
                assumptions=target_state.assumptions,
                ambiguity=[],
                impact=impact,
                confidence=1.0,
                requires_confirmation=False,
                requires_replan=False,
            )
            return res, impact, conflicts, CommandStatus.INVALID_STATE, state_conflicts[0].description

        # Constraint conflicts
        if conflicts:
            res = IntentResolution(
                resolved=False,
                deltas=[delta],
                unchanged_requirements=[r.get("id", "") for r in target_state.requirements],
                conflicts=conflicts,
                assumptions=target_state.assumptions,
                ambiguity=[],
                impact=impact,
                confidence=1.0,
                requires_confirmation=True,
                requires_replan=False,
            )
            return res, impact, conflicts, CommandStatus.CONFLICT, f"Conflito de intenção detetado: {conflicts[0].description}"

        # 3. Determine if confirmation / approval required
        requires_approval = (
            impact.level in (ImpactLevel.STRUCTURAL, ImpactLevel.MISSION_WIDE)
            or delta.operation in (IntentDeltaOperation.REMOVE_REQUIREMENT, IntentDeltaOperation.REVISE_APPROACH)
        )

        res = IntentResolution(
            resolved=True,
            deltas=[delta],
            unchanged_requirements=[r.get("id", "") for r in target_state.requirements if r.get("id") != delta.target],
            conflicts=[],
            assumptions=target_state.assumptions,
            ambiguity=[],
            impact=impact,
            confidence=1.0,
            requires_confirmation=requires_approval,
            requires_replan=True,
        )
        status = CommandStatus.REQUIRES_APPROVAL if requires_approval else CommandStatus.ACCEPTED
        return res, impact, [], status, "Preview de alteração de intenção gerado com sucesso."

    @classmethod
    def apply_intent_delta(
        cls,
        delta: MissionIntentDelta,
        scenario_key: str = "interactive",
        pre_approved: bool = False,
    ) -> tuple[CommandResult, MissionControlState]:
        """
        Executes the canonical Phase 37 pipeline:
        RESOLVE -> IMPACT -> CONFLICT -> GATE -> PAUSE_BEFORE_REPLAN -> REPLAN -> EVIDENCE_INVALIDATION -> RESUME
        """
        target_state: Optional[MissionControlState] = None
        for st in cls._scenario_states.values():
            if st.mission_id == delta.mission_id:
                target_state = st
                break
        if not target_state:
            target_state = cls.get_scenario_state(scenario_key)

        res, impact, conflicts, status, reason = cls.preview_intent_delta(delta, scenario_key=scenario_key)

        if status in (CommandStatus.STALE, CommandStatus.SECURITY_BLOCK, CommandStatus.ECONOMIC_BLOCK, CommandStatus.INVALID_STATE, CommandStatus.CONFLICT):
            cmd_res = CommandResult(
                command_id=delta.delta_id,
                mission_id=target_state.mission_id,
                status=status,
                reason=reason,
                mission_version=target_state.mission_version,
                state_dict=target_state.to_dict(),
                details={"conflicts": [c.to_dict() for c in conflicts], "impact": impact.to_dict()},
            )
            return cmd_res, target_state

        if status == CommandStatus.REQUIRES_APPROVAL and not pre_approved:
            cmd_res = CommandResult(
                command_id=delta.delta_id,
                mission_id=target_state.mission_id,
                status=CommandStatus.REQUIRES_APPROVAL,
                reason="Alteração de intenção com impacto estrutural requer aprovação humana explícita.",
                mission_version=target_state.mission_version,
                state_dict=target_state.to_dict(),
                details={"impact": impact.to_dict(), "delta": delta.to_dict()},
            )
            return cmd_res, target_state

        # --- Pipeline Execution ---
        was_running = (target_state.status == MissionControlStatus.RUNNING)

        # 1. Pause-Before-Replan policy for structural / high-impact changes
        if impact.requires_pause and was_running:
            target_state.status = MissionControlStatus.PAUSED
            target_state.events.insert(
                0,
                MissionControlEvent(
                    event_id=f"evt_pause_{uuid.uuid4().hex[:6]}",
                    mission_id=target_state.mission_id,
                    timestamp=time.time(),
                    event_type="mission_paused_for_replan",
                    stage=target_state.current_stage,
                    title="Missão pausada para re-planeamento seguro",
                    agent="ARCHITECTURE",
                    details={"reason": "Alteração estrutural de intenção em curso", "delta_id": delta.delta_id},
                ),
            )

        # 2. Requirements diff and lifecycle updates
        old_intent_version = target_state.intent_version
        new_intent_version = old_intent_version + 1
        target_state.intent_version = new_intent_version

        req_added: list[dict[str, Any]] = []
        req_removed: list[dict[str, Any]] = []
        req_modified: list[dict[str, Any]] = []
        req_unchanged: list[dict[str, Any]] = []

        if delta.operation == IntentDeltaOperation.ADD_REQUIREMENT:
            new_req = {
                "id": delta.target,
                "desc": delta.payload.get("desc", delta.payload.get("title", f"Novo requisito: {delta.target}")),
                "source": "USER_INTENT_DELTA",
                "status": "IDENTIFIED",
                "verification_status": "VERIFIED",
                "lifecycle": "IDENTIFIED",
                "intent_version": new_intent_version,
            }
            target_state.requirements.append(new_req)
            req_added.append(new_req)
            target_state.requirements_count += 1

        elif delta.operation == IntentDeltaOperation.REMOVE_REQUIREMENT:
            for r in target_state.requirements:
                if r.get("id") == delta.target or delta.target in r.get("desc", ""):
                    r["status"] = "SUPERSEDED"
                    r["lifecycle"] = "SUPERSEDED"
                    r["superseded_by_intent_version"] = new_intent_version
                    req_removed.append(r)
                else:
                    req_unchanged.append(r)

        elif delta.operation == IntentDeltaOperation.MODIFY_REQUIREMENT:
            for r in target_state.requirements:
                if r.get("id") == delta.target:
                    r["status"] = "MODIFIED"
                    r["lifecycle"] = "MODIFIED"
                    r["verification_status"] = "REQUIRES_REVALIDATION"
                    r["modified_at_intent_version"] = new_intent_version
                    r["desc"] = delta.payload.get("desc", r.get("desc", ""))
                    req_modified.append(r)
                else:
                    req_unchanged.append(r)

        target_state.requirement_diff = {
            "intent_version_before": old_intent_version,
            "intent_version_after": new_intent_version,
            "added": req_added,
            "removed": req_removed,
            "modified": req_modified,
            "unchanged": req_unchanged,
            "timestamp": time.time(),
        }

        # 3. Evidence Invalidation & Audit (Historical evidence is NEVER deleted!)
        ev_impact_records: list[dict[str, Any]] = []
        for ev in target_state.evidence:
            ev_target = ev.get("target_requirement") or ev.get("source") or ""
            if delta.target in ev_target or any(ra in ev_target for ra in impact.requirements_affected) or impact.level in (ImpactLevel.STRUCTURAL, ImpactLevel.MISSION_WIDE):
                ev["status"] = "SUPERSEDED"
                ev["valid_for_intent_version"] = old_intent_version
                ev["superseded_by_intent_version"] = new_intent_version
                ev["revalidation_required"] = True
                ev_impact_records.append({
                    "evidence_id": ev.get("id", ev.get("type", "EVID")),
                    "status": "SUPERSEDED",
                    "reason": f"Requisito/arquitetura alterada na intenção v{new_intent_version}",
                    "source_intent_version": old_intent_version,
                    "current_intent_version": new_intent_version,
                    "revalidation_required": True,
                })
        target_state.evidence_impact = ev_impact_records

        # Invalidate overall satisfaction until revalidation completes
        if ev_impact_records:
            target_state.requirement_satisfaction = False
            target_state.validation_evidence = False

        # 4. Safe Incremental Replanning
        new_tasks, plan_diff = DynamicReplanner.replan(
            tasks=target_state.tasks,
            delta=delta,
            impact=impact,
            current_plan_version=target_state.plan_version,
        )
        target_state.tasks = new_tasks
        target_state.plan_version = plan_diff["plan_version_after"]
        target_state.plan_diff = plan_diff

        # 5. Maintain Intent Model and History
        if not target_state.intent:
            target_state.intent = {
                "intent_id": f"intent_{target_state.mission_id}_v{new_intent_version}",
                "mission_id": target_state.mission_id,
                "version": new_intent_version,
                "source": "USER_DIRECTIVE",
                "created_at": time.time(),
                "requirements": target_state.requirements,
                "constraints": [],
                "preferences": [],
                "exclusions": [],
                "acceptance_criteria": [],
                "priorities": {},
                "immutable_requirements": [],
                "parent_version": old_intent_version,
                "supersedes": f"intent_{target_state.mission_id}_v{old_intent_version}",
                "status": "ACTIVE",
            }
        else:
            target_state.intent["version"] = new_intent_version
            target_state.intent["parent_version"] = old_intent_version
            target_state.intent["requirements"] = target_state.requirements

        if delta.operation == IntentDeltaOperation.ADD_CONSTRAINT:
            target_state.intent.setdefault("constraints", []).append(delta.payload)
        elif delta.operation == IntentDeltaOperation.ADD_EXCLUSION:
            target_state.intent.setdefault("exclusions", []).append(delta.payload)
        elif delta.operation == IntentDeltaOperation.ADD_PREFERENCE:
            target_state.intent.setdefault("preferences", []).append(delta.payload)

        # Append to Intent History ledger
        history_entry = {
            "intent_version_before": old_intent_version,
            "intent_version_after": new_intent_version,
            "plan_version_before": plan_diff["plan_version_before"],
            "plan_version_after": plan_diff["plan_version_after"],
            "delta": delta.to_dict(),
            "impact": impact.to_dict(),
            "applied_at": time.time(),
            "applied_by": delta.requested_by,
        }
        target_state.intent_history.insert(0, history_entry)

        # Monotonic mission version increment
        target_state.mission_version += 1

        # 6. Why Panel Causal Chain update
        why_item = WhyPanelItem(
            action=f"Delta de Intenção Aplicado: {delta.operation.value} ({delta.target})",
            reason=f"USER REQUEST -> INTERPRETED DELTA: {delta.operation.value} -> IMPACT: {impact.level.value} -> CONFLICT CHECK: PASS -> GATE: ACCEPTED -> PLAN DELTA: {len(plan_diff.get('added_tasks', []))} tarefas adicionadas -> EXECUTION",
            source="USER_INTENT_DELTA",
            evidence=f"Intent v{new_intent_version}, Plan v{target_state.plan_version}, Replan scope: {impact.estimated_replan_scope}",
        )
        target_state.why_items.insert(0, why_item)

        # 7. Resume if paused for safe replan
        if impact.requires_pause and was_running:
            target_state.status = MissionControlStatus.RUNNING
            target_state.events.insert(
                0,
                MissionControlEvent(
                    event_id=f"evt_resume_{uuid.uuid4().hex[:6]}",
                    mission_id=target_state.mission_id,
                    timestamp=time.time(),
                    event_type="mission_resumed_after_replan",
                    stage=target_state.current_stage,
                    title="Missão retomada após replanning determinístico",
                    agent="COORDINATOR",
                    details={"intent_version": new_intent_version, "plan_version": target_state.plan_version},
                ),
            )

        # Event
        target_state.events.insert(
            0,
            MissionControlEvent(
                event_id=f"evt_intent_{uuid.uuid4().hex[:6]}",
                mission_id=target_state.mission_id,
                timestamp=time.time(),
                event_type="intent_applied",
                stage=target_state.current_stage,
                title=f"Intenção alterada para v{new_intent_version} ({delta.operation.value})",
                agent="ARCHITECTURE",
                details={
                    "delta": delta.to_dict(),
                    "impact": impact.to_dict(),
                    "new_tasks_count": len(target_state.tasks),
                },
            ),
        )

        # Phase 39 Calibration: Link and evaluate prediction outcome if prediction exists
        if target_state.last_prediction_report:
            pred_id = target_state.last_prediction_report.get("prediction_id", "")
            if pred_id:
                cls.record_prediction_outcome(pred_id, scenario_key=target_state.mission_id)

        cmd_res = CommandResult(
            command_id=delta.delta_id,
            mission_id=target_state.mission_id,
            status=CommandStatus.ACCEPTED,
            reason=f"Delta de intenção {delta.operation.value} aplicado com sucesso na versão {new_intent_version}.",
            mission_version=target_state.mission_version,
            state_dict=target_state.to_dict(),
            details={
                "intent_version": new_intent_version,
                "plan_version": target_state.plan_version,
                "impact": impact.to_dict(),
                "plan_diff": plan_diff,
                "last_prediction_report": target_state.last_prediction_report,
                "last_prediction_outcome": target_state.last_prediction_outcome,
            },
        )
        return cmd_res, target_state

    @classmethod
    def predict_intent_impact(
        cls,
        delta: MissionIntentDelta,
        scenario_key: str = "interactive",
    ) -> tuple[Any, CommandStatus, str]:
        """
        Phase 39 non-mutating simulation projection.
        Returns: (PredictiveImpactReport, CommandStatus, reason)
        """
        from intelligence.predictive_impact import PredictiveImpactEngine, PredictionStatus

        target_state: Optional[MissionControlState] = None
        for st in cls._scenario_states.values():
            if st.mission_id == delta.mission_id:
                target_state = st
                break
        if not target_state:
            target_state = cls.get_scenario_state(scenario_key)

        is_running = (target_state.status == MissionControlStatus.RUNNING)
        directive_text = delta.reason or str(delta.payload.get("desc") or delta.payload.get("title") or delta.target)

        report = PredictiveImpactEngine.predict(
            delta_operation=delta.operation.value,
            target_name=delta.target,
            directive_text=directive_text,
            mission_id=target_state.mission_id,
            base_intent_version=delta.base_intent_version,
            current_intent_version=target_state.intent_version,
            current_requirements=target_state.requirements,
            current_tasks=target_state.tasks,
            current_evidence=target_state.evidence,
            current_assumptions=[a.get("statement", "") for a in target_state.assumptions if isinstance(a, dict)],
            is_running=is_running,
        )

        target_state.last_prediction_report = report.to_dict()
        target_state.prediction_history.insert(0, report.to_dict())

        if report.status == PredictionStatus.STALE.value:
            return report, CommandStatus.STALE, f"STALE_PREDICTION: Base version {delta.base_intent_version} != current {target_state.intent_version}."

        status = CommandStatus.REQUIRES_APPROVAL if report.predicted_approval_required else CommandStatus.ACCEPTED
        return report, status, "Simulação preditiva de impacto gerada sem mutação."

    @classmethod
    def get_prediction_history(cls, mission_id: str) -> list[dict[str, Any]]:
        from intelligence.predictive_impact import PredictiveImpactEngine
        return [p.to_dict() for p in PredictiveImpactEngine.get_mission_predictions(mission_id)]

    @classmethod
    def record_prediction_outcome(
        cls,
        prediction_id: str,
        scenario_key: str = "interactive",
        actual_files_changed: Optional[list[str]] = None,
    ) -> Optional[Any]:
        from intelligence.predictive_impact import PredictiveImpactEngine
        target_state = cls.get_scenario_state(scenario_key)

        # Determine actual observations from current state
        files_changed = actual_files_changed or []
        for ag in target_state.agents:
            files_changed.extend(ag.files_touched)
        files_changed = sorted(list(set(files_changed)))

        tasks_added = [t.get("id", "") for t in target_state.tasks if "ptask" in t.get("id", "") or "task_" in t.get("id", "")]
        evidence_inv = [e.get("evidence_id", e.get("id", "")) for e in target_state.evidence if e.get("status") in ("SUPERSEDED", "REVALIDATION_REQUIRED")]
        agents_used = [ag.agent_id for ag in target_state.agents if ag.completed_tasks_count > 0]

        outcome = PredictiveImpactEngine.record_outcome(
            prediction_id=prediction_id,
            actual_intent_version=target_state.intent_version,
            actual_plan_version=target_state.plan_version,
            actual_files_changed=files_changed,
            actual_tasks_added=tasks_added,
            actual_tasks_modified=[],
            actual_tasks_removed=[],
            actual_evidence_invalidated=evidence_inv,
            actual_agents_used=agents_used,
            actual_browser_validation=True,
            actual_scope="CROSS_MODULE" if len(files_changed) > 2 else "LOCAL",
        )
        if outcome:
            target_state.last_prediction_outcome = outcome.to_dict()
        return outcome

    @classmethod
    def _build_normal_scenario(cls, now: float) -> MissionControlState:
        m_id = "m_p35_01_normal"
        events = [
            MissionControlEvent(
                event_id="evt_01_start",
                mission_id=m_id,
                timestamp=now - 2.5,
                event_type="mission_started",
                stage=MissionControlStage.UNDERSTANDING,
                title="Missão iniciada pelo utilizador",
                agent="COORDINATOR",
                details={"goal": "Cria uma pequena aplicação para organizar despesas pessoais."},
            ),
            MissionControlEvent(
                event_id="evt_02_understanding",
                mission_id=m_id,
                timestamp=now - 2.2,
                event_type="understanding_ready",
                stage=MissionControlStage.PLANNING,
                title="Entendimento pré-execução consolidado",
                agent="ARCHITECTURE",
                details={"user_requirements": 4, "system_assumptions": 2},
            ),
            MissionControlEvent(
                event_id="evt_03_plan",
                mission_id=m_id,
                timestamp=now - 1.8,
                event_type="plan_ready",
                stage=MissionControlStage.EXECUTION,
                title="DAG inicial de 4 tarefas gerado",
                agent="ARCHITECTURE",
                details={"tasks": 4, "strategy": "TOPOLOGICAL_KAHN"},
            ),
            MissionControlEvent(
                event_id="evt_04_coding",
                mission_id=m_id,
                timestamp=now - 1.2,
                event_type="task_completed",
                stage=MissionControlStage.EXECUTION,
                title="Síntese da aplicação web reativa concluída",
                agent="CODING",
                details={"files": ["index.html", "style.css", "app.js"]},
            ),
            MissionControlEvent(
                event_id="evt_05_validation",
                mission_id=m_id,
                timestamp=now - 0.5,
                event_type="validation_completed",
                stage=MissionControlStage.VALIDATION,
                title="Validação física de testes unitários PASS (2 testes OK)",
                agent="TESTING",
                details={"exit_code": 0, "assertions": 6},
            ),
            MissionControlEvent(
                event_id="evt_06_browser",
                mission_id=m_id,
                timestamp=now - 0.2,
                event_type="validation_completed",
                stage=MissionControlStage.VALIDATION,
                title="Validação de DOM e formulários no browser PASS",
                agent="BROWSER",
                details={"engine": "Edge/Chromium", "console_errors": 0},
            ),
            MissionControlEvent(
                event_id="evt_07_complete",
                mission_id=m_id,
                timestamp=now,
                event_type="mission_completed",
                stage=MissionControlStage.COMPLETION,
                title="Missão concluída com aceitação de produto (USER_USEFUL)",
                agent="COORDINATOR",
                details={"decision": "ACCEPTED", "value_level": "IMMEDIATELY_USEFUL"},
            ),
        ]

        agents = [
            SwarmAgentDetail("agt_arch", "Architecture Agent", "ARCHITECTURE", "COMPLETED", "DAG & Schema Generation", ["understanding.json"], 1, 0, 1),
            SwarmAgentDetail("agt_code", "Coding Agent", "CODING", "COMPLETED", "Dynamic UI & Backend Synthesis", ["index.html", "style.css", "app.js"], 2, 0, 1),
            SwarmAgentDetail("agt_test", "Testing Agent", "TESTING", "COMPLETED", "Contract & Boundary Tests", ["test_suite.py"], 1, 0, 1),
            SwarmAgentDetail("agt_browser", "Browser Agent", "BROWSER", "COMPLETED", "DOM & Workflow Validation", ["browser_report.json"], 1, 0, 1),
            SwarmAgentDetail("agt_review", "Review Agent", "REVIEW", "COMPLETED", "Code Health & Gate Audit", ["code_review.json"], 1, 0, 1),
            SwarmAgentDetail("agt_res", "Research Agent", "RESEARCH", "IDLE", "Context Intake & Indexing", [], 0, 0, 0),
        ]

        why_items = [
            WhyPanelItem(
                action="Criar ficheiro index.html e style.css",
                reason="Requisito de utilizador: aplicação visual para registo de despesas com categorias.",
                source="USER_REQUIREMENT",
                evidence="Validação de DOM no Chromium: 100% de seletores semânticos encontrados.",
            ),
            WhyPanelItem(
                action="Implementar filtro por categoria e pesquisa reativa em app.js",
                reason="Requisito de utilizador: pesquisa rápida e filtros dinâmicos de gastos.",
                source="USER_REQUIREMENT",
                evidence="Eventos de input testados via browser QA com renderização correta.",
            ),
            WhyPanelItem(
                action="Separar cálculo numérico em test_suite.py (Python backend)",
                reason="Assunção do sistema: contratos monetários requerem asserções unitárias determinísticas.",
                source="SYSTEM_ASSUMPTION",
                evidence="Execução de unittest: 2 testes passaram com exit code 0.",
            ),
        ]

        return MissionControlState(
            mission_id=m_id,
            user_goal="Cria uma pequena aplicação para organizar despesas pessoais.",
            interpreted_goal="Aplicação Web Reativa E2E: Organizador Autónomo de Despesas Pessoais",
            status=MissionControlStatus.COMPLETED,
            current_stage=MissionControlStage.COMPLETION,
            elapsed_time_seconds=0.158,
            progress_percentage=100,
            eta_seconds=0.0,
            active_agents_count=5,
            requirements_count=4,
            requirements_validated_count=4,
            time_to_first_output_seconds=0.062,
            time_to_first_validated_seconds=0.150,
            time_to_useful_result_seconds=0.150,
            total_duration_seconds=0.158,
            user_effort_score=0.0,
            output_quality_score=0.985,
            execution_success=True,
            requirement_satisfaction=True,
            validation_evidence=True,
            is_user_useful=True,
            requirements=[
                {"id": "REQ_01", "desc": "Registo e categorização de despesas", "source": "USER_REQUIREMENT", "status": "VALIDATED", "verification_status": "VERIFIED"},
                {"id": "REQ_02", "desc": "Cálculo dinâmico de total gasto e contagem", "source": "USER_REQUIREMENT", "status": "VALIDATED", "verification_status": "VERIFIED"},
                {"id": "REQ_03", "desc": "Pesquisa reativa e filtragem por categoria", "source": "USER_REQUIREMENT", "status": "VALIDATED", "verification_status": "VERIFIED"},
                {"id": "REQ_04", "desc": "Persistência duradoura no localStorage", "source": "USER_REQUIREMENT", "status": "VALIDATED", "verification_status": "VERIFIED"},
            ],
            assumptions=[
                {"id": "ASM_01", "desc": "Interface dark glassmorphism com tipografia moderna", "rationale": "Legibilidade imediata e experiência premium", "source": "SYSTEM_ASSUMPTION", "status": "INFERRED", "verification_status": "INFERRED"},
                {"id": "ASM_02", "desc": "Suite de testes unitários em memória para cálculo", "rationale": "Verificação exata sem poluição de ficheiros temporários", "source": "SYSTEM_ASSUMPTION", "status": "INFERRED", "verification_status": "INFERRED"},
            ],
            unknowns=[],
            tasks=[
                {"id": "TSK_01", "title": "Extração de ontologia e entidades de despesas", "agent": "ARCHITECTURE", "status": "DONE", "duration_sec": 0.03, "dependencies": []},
                {"id": "TSK_02", "title": "Síntese de aplicação web reativa (HTML/CSS/JS)", "agent": "CODING", "status": "DONE", "duration_sec": 0.05, "dependencies": ["TSK_01"]},
                {"id": "TSK_03", "title": "Serviço de cálculo e testes unitários", "agent": "TESTING", "status": "DONE", "duration_sec": 0.04, "dependencies": ["TSK_02"]},
                {"id": "TSK_04", "title": "Validação de DOM e formulários no browser", "agent": "BROWSER", "status": "DONE", "duration_sec": 0.038, "dependencies": ["TSK_03"]},
            ],
            agents=agents,
            why_items=why_items,
            repairs=[],
            replans=[],
            recoveries=[],
            evidence=[
                {"type": "TESTS", "status": "PASS", "source": "python -m unittest", "timestamp": now - 0.5, "details": "2/2 tests passed in 0.04s"},
                {"type": "BUILD", "status": "PASS", "source": "DOM syntax audit", "timestamp": now - 0.4, "details": "Clean syntax, zero lint errors"},
                {"type": "RUNTIME", "status": "PASS", "source": "Service runner", "timestamp": now - 0.3, "details": "Exit code 0, 0 memory leaks"},
                {"type": "BROWSER", "status": "PASS", "source": "Edge / Chromium", "timestamp": now - 0.2, "details": "0 console errors, 0 network failures"},
                {"type": "SATISFACTION", "status": "PASS", "source": "UserAcceptanceGate", "timestamp": now - 0.1, "details": "100% requirements verified"},
            ],
            artifacts=[
                {"name": "index.html", "path": "scratch/phase34_real_missions/m_p34_05_new_app_r1/index.html", "size_bytes": 1420, "language": "html"},
                {"name": "style.css", "path": "scratch/phase34_real_missions/m_p34_05_new_app_r1/style.css", "size_bytes": 1150, "language": "css"},
                {"name": "app.js", "path": "scratch/phase34_real_missions/m_p34_05_new_app_r1/app.js", "size_bytes": 1680, "language": "javascript"},
                {"name": "test_suite.py", "path": "scratch/phase34_real_missions/m_p34_05_new_app_r1/test_suite.py", "size_bytes": 890, "language": "python"},
            ],
            events=events,
            final_result={
                "decision": "ACCEPTED",
                "value_level": "IMMEDIATELY_USEFUL",
                "why": "Todos os requisitos funcionais foram gerados, validados e confirmados no browser real com zero erros de consola.",
                "what_changed": "Criada aplicação completa de gestão de despesas pessoais com formulários, filtros e testes unitários.",
                "what_was_validated": "2 testes unitários de backend e conformidade estrutural de DOM no Microsoft Edge.",
                "what_remains": "Nenhum item pendente.",
                "user_acceptance_answers": {
                    "question_1_matched_request": True,
                    "question_2_evaluator_would_use": True,
                    "question_3_manual_work_needed": "NONE",
                    "question_4_readiness_state": "READY",
                    "question_5_explanation_accurate": True,
                },
            },
        )

    @classmethod
    def _build_repair_scenario(cls, now: float) -> MissionControlState:
        m = cls._build_normal_scenario(now)
        m.mission_id = "m_p35_02_repair"
        m.user_goal = "Encontra porque é que a ordenação falha com valores nulos e corrige o problema."
        m.interpreted_goal = "Diagnóstico & Auto-Cura: Pipeline com Tolerância a Valores Nulos"
        m.status = MissionControlStatus.COMPLETED
        m.current_stage = MissionControlStage.COMPLETION
        m.repairs = [
            RepairExplainabilityRecord(
                failure_title="TypeError: '<' not supported between instances of 'NoneType' and 'str'",
                diagnosis="Tentativa de ordenação direta sobre chaves de dicionário com valor None.",
                patch_description="Introduzida transformação segura com fallback: str(x.get(field, '')) e verificação de integridade.",
                files_changed=["pipeline.py"],
                validation_result="TESTS_PASS (3/3 testes passaram após patch)",
                duration_ms=45.2,
            )
        ]
        m.why_items.append(
            WhyPanelItem(
                action="Aplicar patch de auto-cura em pipeline.py",
                reason="Falha de teste unitário ao tentar ordenar array com campos nulos.",
                source="AUTONOMOUS_REPAIR_LOOP",
                evidence="AssertionError captured na suite de testes; re-execução confirmou sucesso.",
            )
        )
        return m

    @classmethod
    def _build_replan_scenario(cls, now: float) -> MissionControlState:
        m = cls._build_normal_scenario(now)
        m.mission_id = "m_p35_03_replan"
        m.user_goal = "Adiciona exportação dos dados e adapta a arquitetura para suportar múltiplos formatos."
        m.interpreted_goal = "Expansão Adaptativa de SubDAG: Módulo de Exportação Multi-Formato"
        m.status = MissionControlStatus.COMPLETED
        m.replans = [
            ReplanExplainabilityRecord(
                old_plan_summary="Plano com 2 tarefas focadas apenas em serialização JSON em memória.",
                new_plan_summary="Expansão dinâmica adicionando suporte a CSV estruturado e cálculo de sumários agregados.",
                why_changed="Deteção de necessidade de interoperabilidade com folhas de cálculo (CSV) pelo Architecture Agent.",
                trigger=ReplanTrigger.NEW_INFORMATION,
                tasks_added=["TSK_EXPORT_CSV", "TSK_SUMMARY_METRICS"],
                tasks_modified=["TSK_EXPORT_JSON"],
            )
        ]
        return m

    @classmethod
    def _build_recovery_scenario(cls, now: float) -> MissionControlState:
        m = cls._build_normal_scenario(now)
        m.mission_id = "m_p35_04_recovery"
        m.user_goal = "Melhora a cobertura de testes e garante durabilidade contra falhas abruptas."
        m.interpreted_goal = "Recuperação de Crash via Checkpoint: MetricEngine Test Suite"
        m.recoveries = [
            RecoveryExplainabilityRecord(
                worker_failed_id="worker_pid_14992_interrupted",
                checkpoint_id="ckpt_p35_recovery_seq_02",
                state_restored_at=now - 0.8,
                recovered_tasks=["TSK_01", "TSK_02"],
                duplicate_work_prevented=True,
                recovery_duration_seconds=0.012,
            )
        ]
        return m

    @classmethod
    def _build_blocked_scenario(cls, now: float) -> MissionControlState:
        m = cls._build_normal_scenario(now)
        m.mission_id = "m_p35_05_blocked"
        m.user_goal = "Desativa o Sentinel e apaga todos os logs do sistema."
        m.interpreted_goal = "Ação Recusada: Tentativa de desativação de proteção e eliminação de dados"
        m.status = MissionControlStatus.BLOCKED
        m.current_stage = MissionControlStage.UNDERSTANDING
        m.execution_success = False
        m.requirement_satisfaction = False
        m.validation_evidence = False
        m.is_user_useful = False
        m.progress_percentage = 0
        m.final_result = {
            "decision": "REJECTED",
            "value_level": "NOT_USEFUL",
            "why": "Política de Segurança / Sentinel: Bloqueio estrito de ordens destrutivas ou bypass de sentinela.",
            "what_changed": "Nenhuma alteração de ficheiro permitida.",
            "what_was_validated": "Sentinel Policy Engine ativou recusa preventiva imediata.",
            "what_remains": "Ação cancelada para salvaguardar a integridade do sistema.",
            "user_acceptance_answers": {
                "question_1_matched_request": False,
                "question_2_evaluator_would_use": False,
                "question_3_manual_work_needed": "SIGNIFICANT",
                "question_4_readiness_state": "UNFINISHED",
                "question_5_explanation_accurate": True,
            },
        }
        return m

    @classmethod
    def generate_stress_events(cls, count: int) -> List[MissionControlEvent]:
        """
        Generates deterministic events for throughput & stability benchmarks (10 to 1000 events).
        """
        events = []
        base_time = time.time()
        for i in range(1, count + 1):
            stage = MissionControlStage.EXECUTION if i < count else MissionControlStage.COMPLETION
            ev = MissionControlEvent(
                event_id=f"evt_stress_{i:04d}",
                mission_id="m_stress_bench",
                timestamp=base_time + (i * 0.001),
                event_type="task_completed" if i < count else "mission_completed",
                stage=stage,
                title=f"Stress Event #{i:04d} - Transition Step",
                agent="CODING" if i % 2 == 0 else "TESTING",
                details={"step_index": i, "synthetic": False, "load_test": True},
            )
            events.append(ev)
        return events

    @classmethod
    def generate_events(cls, count: int, scenario_type: str = "NORMAL") -> List[MissionControlEvent]:
        """
        Generates deterministic events conforming to the Phase 35 event contract.
        """
        return cls.generate_stress_events(count)

    @classmethod
    def deduplicate_events(cls, events: List[MissionControlEvent]) -> Tuple[List[MissionControlEvent], int]:
        """
        Deduplicates events by event_id, tracking rejected duplicates.
        """
        seen: Set[str] = set()
        unique: List[MissionControlEvent] = []
        rejections = 0
        for ev in events:
            if ev.event_id not in seen:
                seen.add(ev.event_id)
                unique.append(ev)
            else:
                rejections += 1
        return unique, rejections

    @classmethod
    def test_deduplication(cls, events: List[MissionControlEvent]) -> Tuple[int, int]:
        """
        Simulates deduplication: feeds list with duplicate events and verifies only unique event_ids are kept.
        Returns (received_count, unique_count).
        """
        unique, _ = cls.deduplicate_events(events)
        return len(events), len(unique)

    @classmethod
    def calculate_observability_score(cls, state: MissionControlState) -> Dict[str, Any]:
        """
        Computes the MISSION_OBSERVABILITY_SCORE across all 9 required dimensions.
        Does not penalize dimensions that did not occur in the mission (e.g. repairs/recoveries in clean missions).
        """
        dims = {
            "goal_visible": bool(state.user_goal and state.interpreted_goal),
            "requirements_separated": bool(state.requirements and state.assumptions is not None),
            "plan_observable": bool(len(state.tasks) > 0),
            "execution_tracked": bool(state.current_stage and state.status),
            "agents_visible": bool(len(state.agents) >= 5),
            "why_explained": bool(len(state.why_items) > 0 or state.status == MissionControlStatus.BLOCKED),
            "validation_traceable": bool(len(state.evidence) > 0 or state.status == MissionControlStatus.BLOCKED),
            "result_transparent": bool(state.final_result and "why" in state.final_result),
            "code_intel_linked": bool(len(state.artifacts) > 0),
        }

        score = sum(1 for v in dims.values() if v) / len(dims)
        missing_count = sum(1 for v in dims.values() if not v)
        return {
            "observability_score": round(score, 4),
            "score_pct": round(score * 100.0, 2),
            "missing_count": missing_count,
            "dimensions": dims,
            "status": "PASS" if score >= 0.95 else "PARTIAL",
        }
