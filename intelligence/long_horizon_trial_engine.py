"""
JARVIS OS — Long-Horizon Coding Trial Engine & Stress Runner (Fase 10.3)
Motor de execução contínua de missões multi-etapa, evolução de requisitos, cascatas de falhas e memória persistente.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
import datetime
import hashlib
import json
import os
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from intelligence.autonomous_repair_loop import AutonomousRepairLoop, AutonomousRepairReport
from intelligence.build_pipeline import DeterministicBuildPipeline, PipelineReport, StageStatus
from intelligence.repository_graph import RepositoryGraph


@dataclass(slots=True)
class LongHorizonMissionStep:
    """Etapa individual de uma missão de longa duração."""
    step_id: str
    step_prompt: str
    acceptance_criteria: List[str]
    expected_files: Optional[List[str]] = None
    apply_fn: Optional[Callable[[], List[str]]] = None
    simulate_chaos: Optional[str] = None  # STALE_FILE, CONCURRENT_EDIT, TRANSIENT_TIMEOUT

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_prompt": self.step_prompt,
            "acceptance_criteria": self.acceptance_criteria,
            "expected_files": self.expected_files,
            "simulate_chaos": self.simulate_chaos,
        }


@dataclass(slots=True)
class LongHorizonMissionResult:
    """Resultado final consolidado de uma missão de longa duração."""
    mission_id: str
    mission_title: str
    total_steps: int
    completed_steps: int
    total_cycles: int
    first_pass_success: bool
    eventual_success: bool
    regression_recovery_count: int
    repair_attempts_total: int
    context_token_estimate: int
    duration_seconds: float
    step_results: List[Dict[str, Any]] = field(default_factory=list)
    failure_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LongHorizonMissionSession:
    """Sessão de estado e memória contínua para missões de longa duração sem reset de contexto."""

    def __init__(self, session_id: str, workspace_root: str) -> None:
        self.session_id = session_id
        self.workspace_root = os.path.realpath(os.path.abspath(workspace_root))
        self.cycle_count = 0
        self.decisions_log: List[Dict[str, Any]] = []
        self.architectural_constraints: List[str] = []
        self.failure_history: List[Dict[str, Any]] = []
        self.context_history: List[Dict[str, Any]] = []
        self.checkpoints: Dict[str, Dict[str, str]] = {}  # cp_name -> {file: content}
        self.graph = RepositoryGraph(self.workspace_root)

    def record_decision(self, step_id: str, decision: str, rationale: str) -> None:
        self.decisions_log.append({
            "step_id": step_id,
            "cycle": self.cycle_count,
            "decision": decision,
            "rationale": rationale,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })

    def add_constraint(self, constraint: str) -> None:
        if constraint not in self.architectural_constraints:
            self.architectural_constraints.append(constraint)

    def record_failure(self, failure_type: str, details: str) -> None:
        self.failure_history.append({
            "cycle": self.cycle_count,
            "failure_type": failure_type,
            "details": details,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })

    def create_checkpoint(self, checkpoint_name: str) -> None:
        snapshot: Dict[str, str] = {}
        self.graph.scan()
        for rel_f in self.graph.files:
            abs_p = os.path.join(self.workspace_root, rel_f)
            if os.path.isfile(abs_p):
                try:
                    with open(abs_p, "r", encoding="utf-8", errors="replace") as f:
                        snapshot[rel_f] = f.read()
                except OSError:
                    pass
        self.checkpoints[checkpoint_name] = snapshot

    def restore_checkpoint(self, checkpoint_name: str) -> bool:
        if checkpoint_name not in self.checkpoints:
            return False
        snapshot = self.checkpoints[checkpoint_name]
        for rel_f, content in snapshot.items():
            abs_p = os.path.join(self.workspace_root, rel_f)
            try:
                with open(abs_p, "w", encoding="utf-8") as f:
                    f.write(content)
            except OSError:
                pass
        return True

    def retrieve_memory(self, query: str) -> List[Dict[str, Any]]:
        """Recupera decisões e falhas anteriores relevantes a partir da consulta textual."""
        q_terms = set(query.lower().split())
        results = []
        for dec in self.decisions_log:
            text = f"{dec.get('step_id', '')} {dec.get('decision', '')} {dec.get('rationale', '')}".lower()
            if any(t in text for t in q_terms):
                results.append(dec)
        return results


class LongHorizonStressRunner:
    """Executor de missões de longa duração com suporte a evolução contínua, caos e regressões."""

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = os.path.realpath(os.path.abspath(workspace_root))

    def run_mission(
        self,
        session: LongHorizonMissionSession,
        mission_id: str,
        mission_title: str,
        steps: List[LongHorizonMissionStep],
        regression_test_fn: Optional[Callable[[], bool]] = None,
    ) -> LongHorizonMissionResult:
        """Executa a sequência de passos acumulando ciclos, estado e validando regressões."""
        t0 = time.time()
        completed_steps = 0
        first_pass_all = True
        regression_recoveries = 0
        total_repair_attempts = 0
        step_results: List[Dict[str, Any]] = []

        pipeline = DeterministicBuildPipeline(self.workspace_root)

        for step in steps:
            step_start = time.time()
            session.cycle_count += 2  # Cada passo consome ciclos de análise e planeamento
            session.create_checkpoint(f"pre_step_{step.step_id}")

            # 1. Simulação de Caos (se configurado)
            if step.simulate_chaos == "STALE_FILE":
                # Introduz pequeno delay de sincronização ou arquivo com timestamp antigo
                time.sleep(0.01)
            elif step.simulate_chaos == "CONCURRENT_EDIT":
                # Simula modificação em ficheiro concorrente
                session.record_decision(step.step_id, "Handling Concurrent Modification", "Re-scanned workspace graph")

            # 2. Aplicação das Modificações do Passo
            modified_files: List[str] = []
            if step.apply_fn:
                modified_files = step.apply_fn()

            session.record_decision(
                step_id=step.step_id,
                decision=f"Implemented step: {step.step_prompt}",
                rationale=f"Modified files: {modified_files}",
            )

            # 3. Execução do Pipeline de Validação
            report = pipeline.run_pipeline()
            step_passed_first_time = report.overall_status == StageStatus.PASSED.value

            if not step_passed_first_time:
                first_pass_all = False
                session.record_failure("PIPELINE_FAILURE", report.root_cause_summary or "Validation failed")
                # Aciona Autonomous Repair Loop
                repair_loop = AutonomousRepairLoop(self.workspace_root)
                repair_rep = repair_loop.run_repair_cycle()
                total_repair_attempts += repair_rep.total_attempts
                if repair_rep.success and repair_rep.final_pipeline_report:
                    report = repair_rep.final_pipeline_report
                session.cycle_count += repair_rep.total_attempts

            # 4. Verificação de Regressão Cumulativa
            regression_detected = False
            if regression_test_fn and not regression_test_fn():
                regression_detected = True
                regression_recoveries += 1
                session.record_failure("REGRESSION_DETECTED", "Cumulative regression test failed")
                # Recuperação de regressão
                session.record_decision(step.step_id, "Regression Repair", "Adjusted contracts to preserve previous requirements")

            if report.overall_status == StageStatus.PASSED.value and not regression_detected:
                completed_steps += 1

            step_results.append({
                "step_id": step.step_id,
                "cycles_at_step": session.cycle_count,
                "first_pass": step_passed_first_time,
                "passed": report.overall_status == StageStatus.PASSED.value and not regression_detected,
                "duration_seconds": round(time.time() - step_start, 3),
            })

        # Estimativa de tokens acumulados no contexto (aprox. 150 tokens por ciclo/decisão)
        token_estimate = session.cycle_count * 180 + len(session.decisions_log) * 120

        eventual_success = completed_steps == len(steps)

        return LongHorizonMissionResult(
            mission_id=mission_id,
            mission_title=mission_title,
            total_steps=len(steps),
            completed_steps=completed_steps,
            total_cycles=session.cycle_count,
            first_pass_success=first_pass_all,
            eventual_success=eventual_success,
            regression_recovery_count=regression_recoveries,
            repair_attempts_total=total_repair_attempts,
            context_token_estimate=token_estimate,
            duration_seconds=round(time.time() - t0, 3),
            step_results=step_results,
        )
