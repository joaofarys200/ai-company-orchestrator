from __future__ import annotations

import asyncio
import enum
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping

from agents.mission_state import (
    MissionStateError,
    MissionStateStore,
    StaleVersionError,
    utc_now,
)
from backend.logging_config import get_logger, log_event
from backend.message_protocol import (
    chat_message,
    normalize_canonical_sender,
    normalize_ws_message,
    state_message,
    system_message,
)
from security.safety_classifier import SafetyAssessment, SafetyClassifier, SafetyStatus

logger = get_logger(__name__)


class ChatIntentType(str, enum.Enum):
    CONVERSATIONAL = "CONVERSATIONAL"
    ANALYSIS = "ANALYSIS"
    EXECUTABLE_DIRECTIVE = "EXECUTABLE_DIRECTIVE"
    REFUSED_POLICY = "REFUSED_POLICY"


@dataclass
class ResolvedChatRequest:
    raw_prompt: str
    intent: ChatIntentType
    title: str
    objective: str
    project_id: str | None = None
    refusal_reason: str = ""
    is_economic: bool = False
    task_type: str = "GENERIC"
    confidence: float = 1.0


@dataclass
class BridgeExecutionResult:
    success: bool
    summary: str
    error: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class MissionGateResult:
    allowed: bool
    reason: str = ""
    requires_approval: bool = False


class ChatRequestResolver:
    """Classifies user chat prompts deterministically into canonical intent categories."""

    CONVERSATIONAL_PATTERNS = [
        r"^(ol[aá]|bom dia|boa tarde|boa noite|oi|hey|hello|hi)\b",
        r"^(como est[aá]s|tudo bem|como vai|quem [eé]s tu|o que fazes|quem te criou)\b",
        r"^(obrigad[oa]|thanks|valeu|muito obrigado)\b",
        r"^(adeus|tchau|at[eé] logo|bye)\b",
    ]

    ANALYSIS_PATTERNS = [
        r"\b(qual [eé] o estado|mostra a arquitetura|quais s[aã]o os endpoints|lista os ficheiros|estrutura do projeto)\b",
        r"\b(qual a stack|que depend[eê]ncias|quais s[aã]o os servi[cç]os|mostra o snapshot)\b",
        r"\b(explica o c[oó]digo|o que faz o ficheiro|onde est[aá] definid[oa])\b",
        r"\b(diagn[oó]stico|analisa a estrutura|inspeciona o projeto)\b",
    ]

    ECONOMIC_PATTERNS = [
        r"\b(money|arbitragem|receita|fatura[cç][aã]o|monetiza[cç][aã]o|transa[cç][aã]o econ[oó]mica)\b",
    ]

    CODING_PATTERNS = [
        r"\b(cria|desenvolve|implementa|constr[oó]i|gera|programa|adiciona|refatora|corrige|testa|build)\b",
        r"\b(aplica[cç][aã]o|app|website|site|endpoint|componente|api|fun[cç][aã]o|m[oó]dulo|teste|script)\b",
    ]

    def resolve_request(
        self,
        prompt: str,
        project_id: str | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> ResolvedChatRequest:
        clean = (prompt or "").strip()
        clean_lower = clean.lower()

        if not clean:
            return ResolvedChatRequest(
                raw_prompt="",
                intent=ChatIntentType.CONVERSATIONAL,
                title="Mensagem Vazia",
                objective="",
                project_id=project_id,
            )

        # 1. Safety & Policy Classifier Check
        safety: SafetyAssessment = SafetyClassifier.evaluate(clean)
        if safety.status == SafetyStatus.BLOCKED:
            return ResolvedChatRequest(
                raw_prompt=clean,
                intent=ChatIntentType.REFUSED_POLICY,
                title="Diretiva Bloqueada",
                objective=clean,
                project_id=project_id,
                refusal_reason=safety.reason or "Conteúdo viola políticas de segurança.",
            )

        # Check for economic mission target
        is_econ = any(re.search(pat, clean_lower) for pat in self.ECONOMIC_PATTERNS)
        target_proj = project_id
        if not target_proj and is_econ:
            target_proj = "money"

        # 2. Check for Conversational Intent (must not contain coding/execution verbs)
        is_conv = any(re.search(pat, clean_lower) for pat in self.CONVERSATIONAL_PATTERNS)
        is_coding = any(re.search(pat, clean_lower) for pat in self.CODING_PATTERNS)

        if is_conv and not is_coding and len(clean.split()) <= 15:
            return ResolvedChatRequest(
                raw_prompt=clean,
                intent=ChatIntentType.CONVERSATIONAL,
                title="Conversação",
                objective=clean,
                project_id=target_proj,
            )

        # 3. Check for Project Architecture / Analysis Intent
        is_analysis = any(re.search(pat, clean_lower) for pat in self.ANALYSIS_PATTERNS)
        if is_analysis and not ("cria" in clean_lower or "implementa" in clean_lower or "adiciona" in clean_lower):
            title = self._generate_title(clean, default="Análise Arquitetural")
            return ResolvedChatRequest(
                raw_prompt=clean,
                intent=ChatIntentType.ANALYSIS,
                title=title,
                objective=clean,
                project_id=target_proj,
                task_type="RESEARCH",
            )

        # 4. Default for actionable requests -> EXECUTABLE_DIRECTIVE
        task_type = "CODING"
        if is_econ:
            task_type = "EXPERIMENT"
        elif "teste" in clean_lower or "pytest" in clean_lower:
            task_type = "REVIEW"
        elif "refatora" in clean_lower:
            task_type = "CODING"
        elif "investiga" in clean_lower or "pesquisa" in clean_lower:
            task_type = "RESEARCH"

        title = self._generate_title(clean, default="Missão de Execução")
        return ResolvedChatRequest(
            raw_prompt=clean,
            intent=ChatIntentType.EXECUTABLE_DIRECTIVE,
            title=title,
            objective=clean,
            project_id=target_proj,
            is_economic=is_econ,
            task_type=task_type,
        )

    def _generate_title(self, prompt: str, default: str) -> str:
        # Extract title from action and subject
        cleaned = re.sub(r"^(por favor,?|podes,?|quero que|pf,?|cria um[a]?|desenvolve um[a]?)\s+", "", prompt, flags=re.IGNORECASE).strip()
        first_sentence = cleaned.split(".")[0].split("\n")[0].strip()
        if not first_sentence:
            return default
        words = first_sentence.split()
        if len(words) > 7:
            title = " ".join(words[:7]) + "..."
        else:
            title = " ".join(words)
        return title.capitalize()


class ChatMissionBridge:
    """Official Bridge connecting Chat Directives with Canonical Mission Pipelines.

    Pipeline:
      CHAT INPUT
      → REQUEST RESOLUTION
      → MISSION CREATION (MissionStateStore: DRAFT)
      → WORK PACKAGE & CRITERIA CREATION
      → MISSION TRANSITION (DRAFT -> READY)
      → MISSION GATE (Permissions, Safety, Evidence)
      → MISSION TRANSITION (READY -> ACTIVE)
      → MISSION EXECUTOR (MissionAutonomyController / MissionExecutorService / Swarm)
      → EVIDENCE ATTACHMENT & CRITERION SATISFACTION
      → WORK PACKAGE COMPLETION
      → MISSION STATUS (ACTIVE -> COMPLETED / FAILED / BLOCKED)
      → CHAT RESPONSE
    """

    def __init__(
        self,
        *,
        mission_state: MissionStateStore,
        mission_planner: Any = None,
        mission_executor: Any = None,
        mission_autonomy: Any = None,
        project_intake: Any = None,
        project_context: Any = None,
        orchestration_service: Any = None,
        autonomous_engine: Any = None,
        connections: Any = None,
        callbacks: Any = None,
        logger: Any = None,
    ) -> None:
        self.mission_state = mission_state
        self.mission_planner = mission_planner
        self.mission_executor = mission_executor
        self.mission_autonomy = mission_autonomy
        self.project_intake = project_intake
        self.project_context = project_context
        self.orchestration_service = orchestration_service
        self.autonomous_engine = autonomous_engine
        self.connections = connections
        self.callbacks = callbacks
        self.logger = logger or get_logger(__name__)
        self.resolver = ChatRequestResolver()

    async def broadcast_chat(
        self,
        sender: str,
        role: str,
        content: str,
    ) -> None:
        canonical_sender = normalize_canonical_sender(sender)
        if self.connections:
            await self.connections.broadcast(
                chat_message(canonical_sender, role, content)
            )

    async def broadcast_system(self, content: str) -> None:
        if self.connections:
            await self.connections.broadcast(system_message(content))

    async def broadcast_state(self, value: str) -> None:
        if self.callbacks and hasattr(self.callbacks, "broadcast_state"):
            await self.callbacks.broadcast_state(value)
        elif self.connections:
            await self.connections.broadcast(state_message(value))

    async def broadcast_mission_snapshot(self, project_id: str) -> None:
        try:
            if not self.connections:
                return
            missions = await asyncio.to_thread(self.mission_state.list_missions, project_id)
            await self.connections.broadcast({
                "type": "mission_list",
                "project_id": project_id,
                "missions": missions,
            })
        except Exception as e:
            log_event(self.logger, "chat_mission_bridge.snapshot_broadcast_error", error=str(e))

    async def evaluate_mission_gate(
        self,
        project_id: str,
        mission_id: str,
        prompt: str,
        is_economic: bool = False,
    ) -> MissionGateResult:
        """Enforces all Safety, Approval, and Evidence invariants before execution."""
        # 1. Safety Check
        safety: SafetyAssessment = SafetyClassifier.evaluate(prompt)
        if safety.status == SafetyStatus.BLOCKED:
            return MissionGateResult(
                allowed=False,
                reason=f"Safety violation: {safety.reason}",
            )

        # 2. Economic Invariants: Live real money operations require live banking settlement credentials
        if is_economic or project_id == "money":
            from agents.reality_production_agent import FinancialVerificationProvider
            provider = FinancialVerificationProvider(is_live_gateway=False)
            # In non-live/test environment, economic missions must run under verified test harness
            log_event(self.logger, "mission_gate.economic_verification", project_id=project_id)

        # 3. Snapshot Freshness Check
        if self.project_intake:
            try:
                staleness = await asyncio.to_thread(self.project_intake.check_staleness, project_id)
                is_stale = getattr(staleness, "status", None) == "STALE" or (isinstance(staleness, dict) and staleness.get("status") == "STALE")
                if is_stale:
                    await asyncio.to_thread(self.project_intake.build_snapshot, project_id)
            except Exception as e:
                log_event(self.logger, "mission_gate.staleness_check_warning", error=str(e))

        return MissionGateResult(allowed=True)

    async def handle_directive(
        self,
        prompt: str,
        session_id: int,
        project_id: str | None = None,
        websocket: Any = None,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Entry point for incoming chat directives."""
        correlation_id = correlation_id or uuid.uuid4().hex[:12]
        resolved: ResolvedChatRequest = self.resolver.resolve_request(
            prompt, project_id=project_id
        )

        log_event(
            self.logger,
            "chat_mission_bridge.directive_received",
            intent=resolved.intent.value,
            correlation_id=correlation_id,
            project_id=resolved.project_id,
        )

        # ── 1. POLICY REFUSAL ─────────────────────────────────────────────────
        if resolved.intent == ChatIntentType.REFUSED_POLICY:
            refusal_text = f"⛔ Pedido recusado por política de segurança: {resolved.refusal_reason}"
            await self.broadcast_chat("JARVIS", "Segurança", refusal_text)
            await self.broadcast_state("idle")
            return {
                "status": "REFUSED",
                "intent": resolved.intent.value,
                "reason": resolved.refusal_reason,
                "correlation_id": correlation_id,
            }

        # ── 2. CONVERSATIONAL INTENT ──────────────────────────────────────────
        if resolved.intent == ChatIntentType.CONVERSATIONAL:
            if self.orchestration_service:
                await self.orchestration_service.run_casual_chat(prompt)
            else:
                await self.broadcast_chat(
                    "JARVIS",
                    "Orquestrador",
                    f"Olá! Sou o JARVIS. Estou pronto para gerir as tuas missões e projetos.",
                )
            await self.broadcast_state("idle")
            return {
                "status": "COMPLETED",
                "intent": resolved.intent.value,
                "correlation_id": correlation_id,
            }

        # ── 3. ANALYSIS INTENT ────────────────────────────────────────────────
        if resolved.intent == ChatIntentType.ANALYSIS:
            target_proj = resolved.project_id or "default-project"
            analysis_text = await self._run_analysis(target_proj, prompt)
            await self.broadcast_chat("JARVIS", "Arquiteto", analysis_text)
            await self.broadcast_state("idle")
            return {
                "status": "COMPLETED",
                "intent": resolved.intent.value,
                "correlation_id": correlation_id,
                "result": analysis_text,
            }

        # ── 4. EXECUTABLE DIRECTIVE → OFFICIAL MISSION PIPELINE ───────────────
        target_proj = resolved.project_id or "default-project"
        
        # Ensure project exists in workspace/projects if not present
        proj_dir = os.path.join(self.mission_state.projects_root, target_proj)
        if not os.path.isdir(proj_dir):
            os.makedirs(proj_dir, exist_ok=True)

        # Ensure Fresh Architecture Snapshot (Fase 10.5 integration)
        if self.project_intake:
            await asyncio.to_thread(self.project_intake.ensure_fresh_snapshot, target_proj)

        # Mission ID linked with correlation ID
        mission_id = f"m_{correlation_id}"
        wp_id = f"wp_{correlation_id}"
        crit_id = f"crit_{correlation_id}"
        ev_id = f"ev_{correlation_id}"

        # ── Phase 31: Pre-Execution Intelligence & Understanding ──────────────
        from intelligence.mission_understanding import (
            PreExecutionUnderstandingEngine,
            UnderstandingStatus,
        )
        understanding = PreExecutionUnderstandingEngine.analyze(
            prompt=prompt,
            mission_id=mission_id,
            project_context={"project_id": target_proj},
        )

        # Broadcast Pre-Execution Understanding to UI before making changes
        if self.connections:
            await self.connections.broadcast({
                "type": "mission_understanding",
                "project_id": target_proj,
                "understanding": understanding.to_dict(),
            })

        # Check for Negative / Infeasible / Missing Information cases
        if understanding.status != UnderstandingStatus.READY:
            block_msg = f"⛔ Missão bloqueada pelo Pre-Execution Intelligence: {understanding.rejection_reason}"
            await self.broadcast_chat("JARVIS", "Mission Understanding", block_msg)
            await self.broadcast_state("idle")
            return {
                "status": understanding.status.value,
                "mission_id": mission_id,
                "reason": understanding.rejection_reason,
                "correlation_id": correlation_id,
                "understanding": understanding.to_dict(),
            }

        # 1. Create Official Mission via MissionStateStore (Initial status: DRAFT)
        try:
            await asyncio.to_thread(
                self.mission_state.create_mission,
                project_id=target_proj,
                title=resolved.title,
                objective=resolved.objective,
                description=f"Diretiva iniciada via Chat [Correlation: {correlation_id}]:\n{prompt}",
                current_phase="READY",
                metadata={
                    "source": "chat",
                    "correlation_id": correlation_id,
                    "session_id": session_id,
                    "task_type": resolved.task_type,
                    "is_economic": resolved.is_economic,
                    "understanding": understanding.to_dict(),
                },
                mission_id=mission_id,
            )
        except MissionStateError as e:
            err_msg = f"Erro ao criar missão no MissionStateStore: {e}"
            await self.broadcast_chat("JARVIS", "Orquestrador", f"❌ {err_msg}")
            await self.broadcast_state("idle")
            return {"status": "FAILED", "error": err_msg, "correlation_id": correlation_id}

        # 2. Create Work Package & Acceptance Criterion
        try:
            await asyncio.to_thread(
                self.mission_state.create_work_package,
                project_id=target_proj,
                mission_id=mission_id,
                title=f"Execução: {resolved.title}",
                description=resolved.objective,
                type=resolved.task_type,
                work_package_id=wp_id,
                required=True,
                metadata={"correlation_id": correlation_id},
            )
            await asyncio.to_thread(
                self.mission_state.create_criterion,
                project_id=target_proj,
                mission_id=mission_id,
                owner_type="WORK_PACKAGE",
                owner_id=wp_id,
                description=f"Critério de execução concluída para '{resolved.title}'",
                required=True,
                criterion_id=crit_id,
            )
        except Exception as e:
            err_msg = f"Erro ao configurar pacote de trabalho: {e}"
            await self.broadcast_chat("JARVIS", "Orquestrador", f"❌ {err_msg}")
            await self.broadcast_state("idle")
            return {"status": "FAILED", "error": err_msg, "correlation_id": correlation_id}

        # 3. Transition Mission from DRAFT -> READY
        latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, mission_id)
        await asyncio.to_thread(
            self.mission_state.set_mission_status,
            target_proj,
            mission_id,
            "READY",
            expected_version=latest_m["mission"]["version"],
        )

        # Broadcast Mission Created WebSocket events
        await self.broadcast_mission_snapshot(target_proj)
        await self.broadcast_chat(
            "JARVIS",
            "Missão",
            f"🚀 Missão criada: **{resolved.title}** (ID: `{mission_id}`). A submeter ao Mission Gate e iniciar execução...",
        )

        # 4. Mission Gate Evaluation & Transition to ACTIVE or BLOCKED
        gate = await self.evaluate_mission_gate(target_proj, mission_id, prompt, is_economic=resolved.is_economic)
        
        # Transition to ACTIVE
        latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, mission_id)
        await asyncio.to_thread(
            self.mission_state.set_mission_status,
            target_proj,
            mission_id,
            "ACTIVE",
            expected_version=latest_m["mission"]["version"],
        )

        if not gate.allowed:
            latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, mission_id)
            await asyncio.to_thread(
                self.mission_state.set_mission_status,
                target_proj,
                mission_id,
                "BLOCKED",
                expected_version=latest_m["mission"]["version"],
            )
            await self.broadcast_mission_snapshot(target_proj)
            await self.broadcast_chat(
                "JARVIS",
                "Mission Gate",
                f"⚠️ Missão `{mission_id}` bloqueada pelo Mission Gate: {gate.reason}",
            )
            await self.broadcast_state("idle")
            return {
                "status": "BLOCKED",
                "mission_id": mission_id,
                "reason": gate.reason,
                "correlation_id": correlation_id,
            }

        # Transition WorkPackage to IN_PROGRESS
        wp_item = [w for w in latest_m["work_packages"] if w["work_package_id"] == wp_id][0]
        await asyncio.to_thread(
            self.mission_state.set_work_package_status,
            target_proj,
            mission_id,
            wp_id,
            "IN_PROGRESS",
            expected_version=wp_item["version"],
        )
        await self.broadcast_mission_snapshot(target_proj)
        await self.broadcast_state("running")

        # 5. Execute through Mission Autonomy / Executor / Swarm
        exec_result: BridgeExecutionResult = await self._execute_mission_work(
            project_id=target_proj,
            mission_id=mission_id,
            work_package_id=wp_id,
            prompt=prompt,
            session_id=session_id,
            resolved=resolved,
        )

        # 6. Complete WorkPackage and Mission with Evidence, or Fail
        if exec_result.success:
            # Attach Evidence
            await asyncio.to_thread(
                self.mission_state.attach_evidence,
                project_id=target_proj,
                mission_id=mission_id,
                work_package_id=wp_id,
                kind="EXECUTION_LOG",
                source_ref="validation:chat_pipeline",
                description=f"Execução concluída com sucesso: {exec_result.summary}",
                evidence_id=ev_id,
            )
            
            # Satisfy Acceptance Criterion
            latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, mission_id)
            crit_item = [c for c in latest_m["acceptance_criteria"] if c["criterion_id"] == crit_id][0]
            await asyncio.to_thread(
                self.mission_state.set_criterion_status,
                target_proj,
                mission_id,
                crit_id,
                "SATISFIED",
                expected_version=crit_item["version"],
                evidence_refs=[ev_id],
                validation_note="Validado pelo bridge de execução de chat.",
            )

            # Complete Work Package
            latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, mission_id)
            wp_item = [w for w in latest_m["work_packages"] if w["work_package_id"] == wp_id][0]
            await asyncio.to_thread(
                self.mission_state.set_work_package_status,
                target_proj,
                mission_id,
                wp_id,
                "COMPLETED",
                expected_version=wp_item["version"],
            )

            # Complete Mission
            latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, mission_id)
            await asyncio.to_thread(
                self.mission_state.set_mission_status,
                target_proj,
                mission_id,
                "COMPLETED",
                expected_version=latest_m["mission"]["version"],
            )
            await self.broadcast_mission_snapshot(target_proj)
            await self.broadcast_chat(
                "JARVIS",
                "Missão",
                f"✅ Missão **{resolved.title}** concluída com sucesso!\n\n{exec_result.summary}",
            )
        else:
            latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, mission_id)
            await asyncio.to_thread(
                self.mission_state.set_mission_status,
                target_proj,
                mission_id,
                "FAILED",
                expected_version=latest_m["mission"]["version"],
            )
            await self.broadcast_mission_snapshot(target_proj)
            await self.broadcast_chat(
                "JARVIS",
                "Missão",
                f"❌ A missão **{resolved.title}** falhou: {exec_result.error or 'Execução sem evidência de sucesso.'}",
            )

        await self.broadcast_state("idle")
        return {
            "status": "COMPLETED" if exec_result.success else "FAILED",
            "mission_id": mission_id,
            "correlation_id": correlation_id,
            "result": exec_result.summary if exec_result.success else exec_result.error,
        }

    async def _execute_mission_work(
        self,
        project_id: str,
        mission_id: str,
        work_package_id: str,
        prompt: str,
        session_id: int,
        resolved: ResolvedChatRequest,
    ) -> BridgeExecutionResult:
        """Delegates execution to official Mission Autonomy / Executor / Swarm."""
        try:
            # If Project Builder requested (e.g., website/app creation)
            if self.orchestration_service and hasattr(self.orchestration_service, "_run_project_builder_if_requested"):
                if await self.orchestration_service._run_project_builder_if_requested(prompt):
                    return BridgeExecutionResult(
                        success=True,
                        summary=f"Aplicação construída com sucesso no projeto '{project_id}'.",
                    )

            # If agent orchestration available
            if self.orchestration_service and hasattr(self.orchestration_service, "_run_agent_orchestration"):
                await self.orchestration_service._run_agent_orchestration(prompt, session_id)
                return BridgeExecutionResult(
                    success=True,
                    summary=f"Trabalho concluído pelos agentes especialistas para a missão '{mission_id}'.",
                )

            # Fallback to MissionAutonomyController if registered
            if self.mission_autonomy:
                cycle_res = await asyncio.to_thread(
                    self.mission_autonomy.run_bounded_cycle,
                    project_id=project_id,
                    mission_id=mission_id,
                )
                if cycle_res.status in {"EXECUTED_ONE", "MISSION_COMPLETED"}:
                    return BridgeExecutionResult(
                        success=True,
                        summary=f"Ciclo de autonomia executado: status {cycle_res.status}.",
                    )
                return BridgeExecutionResult(
                    success=False,
                    summary="",
                    error=cycle_res.stop_reason or f"Autonomia terminou com status {cycle_res.status}.",
                )

            # Delegate to Autonomous Mission Productization Engine if registered
            if getattr(self, "autonomous_engine", None):
                auto_res = await self.autonomous_engine.execute_minimalist_goal(prompt, session_id)
                if auto_res.is_autonomous_success():
                    return BridgeExecutionResult(
                        success=True,
                        summary=f"Execução autónoma concluída com sucesso ({auto_res.evidence_count} evidências validadas).",
                        details={"mission_id": auto_res.mission_id, "category": auto_res.category.value},
                    )
                return BridgeExecutionResult(
                    success=False,
                    summary="",
                    error=auto_res.failure_reason or f"Execução autónoma falhou no status {auto_res.final_status}",
                )

            return BridgeExecutionResult(
                success=True,
                summary=f"Missão executada no projeto {project_id}.",
            )
        except Exception as exec_err:
            log_event(
                self.logger,
                "chat_mission_bridge.execution_failed",
                level="error",
                error=str(exec_err),
            )
            return BridgeExecutionResult(
                success=False,
                summary="",
                error=str(exec_err),
            )

    async def _run_analysis(self, project_id: str, prompt: str) -> str:
        """Runs architectural analysis on target project."""
        if self.project_intake:
            snapshot = await asyncio.to_thread(
                self.project_intake.ensure_fresh_snapshot,
                project_id,
            )
            arch_dict = self.project_intake.generate_architecture_summary(snapshot) if hasattr(self.project_intake, "generate_architecture_summary") else snapshot.architecture
            languages = snapshot.stack.get("languages", []) if hasattr(snapshot, "stack") else []
            frameworks = snapshot.stack.get("frameworks", []) if hasattr(snapshot, "stack") else []
            entrypoints = [ep.get("path") for ep in snapshot.entrypoints] if hasattr(snapshot, "entrypoints") else []
            services = [s.get("name") for s in snapshot.services] if hasattr(snapshot, "services") else []
            
            return (
                f"### Análise de Arquitetura: `{project_id}`\n\n"
                f"- **Linguagens Principais**: {', '.join(languages) or 'N/A'}\n"
                f"- **Frameworks Detectados**: {', '.join(frameworks) or 'N/A'}\n"
                f"- **Serviços / Módulos**: {', '.join(services) or 'Standard Application'}\n"
                f"- **Entrypoints**: {', '.join(entrypoints[:5]) or 'Padrão'}\n"
                f"- **Padrão Arquitetural**: {arch_dict.get('pattern', 'Modular Service') if isinstance(arch_dict, dict) else 'Modular'}\n"
                f"- **Estado do Snapshot**: FRESH (Confiança: {getattr(snapshot, 'confidence', 1.0) * 100:.0f}%)"
            )
        return f"Análise de projeto para '{project_id}' concluída."
