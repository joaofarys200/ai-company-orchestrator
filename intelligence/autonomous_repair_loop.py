"""
JARVIS OS — Autonomous Repair Loop (Fase 10: Coding Agent 2.0)
Orquestrador do ciclo: OBSERVE -> CLASSIFY -> ROOT_CAUSE -> MINIMAL_REPAIR -> BUILD -> TEST -> BROWSER -> VERIFY
com salvaguardas anti-looping (NO_REPEATED_PATCH), MAX_REPAIR_ATTEMPTS e ROLLBACK_ON_REGRESSION.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib
import os
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from intelligence.ast_repair_v2 import ASTRepairEngineV2, RepairResult
from intelligence.build_pipeline import DeterministicBuildPipeline, PipelineReport, PipelineStage, StageStatus
from intelligence.cross_file_validator import ContractIssueType, ContractValidationIssue
from intelligence.repository_graph import RepositoryGraph


class RepairLoopState(str, Enum):
    OBSERVE = "OBSERVE"
    CLASSIFY = "CLASSIFY"
    ROOT_CAUSE = "ROOT_CAUSE"
    MINIMAL_REPAIR = "MINIMAL_REPAIR"
    BUILD_TEST = "BUILD_TEST"
    VERIFY = "VERIFY"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


@dataclass(slots=True)
class RepairIterationRecord:
    """Registo de uma iteração de reparação autónoma."""
    iteration_number: int
    state: str
    target_file: str
    issue_type: str
    patch_fingerprint: str
    strategy: str
    applied_changes: List[str]
    pipeline_passed: bool
    duration_seconds: float
    regression_detected: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AutonomousRepairReport:
    """Relatório final do ciclo de reparação autónoma."""
    success: bool
    total_attempts: int
    max_attempts: int
    duration_seconds: float
    files_repaired: List[str]
    iterations: List[RepairIterationRecord]
    applied_patch_fingerprints: List[str]
    regressions_count: int
    rollbacks_count: int
    final_pipeline_report: Optional[PipelineReport] = None
    failure_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AutonomousRepairLoop:
    """Orquestrador do ciclo de reparação autónoma com proteções de estabilidade."""

    def __init__(
        self,
        workspace_root: str,
        max_repair_attempts: int = 4,
    ) -> None:
        self.workspace_root = os.path.realpath(os.path.abspath(workspace_root))
        self.max_repair_attempts = max_repair_attempts
        self.pipeline = DeterministicBuildPipeline(workspace_root)
        self.repair_engine = ASTRepairEngineV2(self.pipeline.graph)
        self.applied_fingerprints: Set[str] = set()
        self.iterations: List[RepairIterationRecord] = []
        self.file_checkpoints: Dict[str, str] = {}  # file_path -> original_content

    def _compute_patch_fingerprint(self, file_path: str, diff_text: str) -> str:
        raw = f"{file_path}::{diff_text}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _save_checkpoint(self, file_path: str) -> None:
        abs_p = os.path.join(self.workspace_root, file_path)
        if os.path.isfile(abs_p) and file_path not in self.file_checkpoints:
            try:
                with open(abs_p, "r", encoding="utf-8", errors="replace") as f:
                    self.file_checkpoints[file_path] = f.read()
            except OSError:
                pass

    def _rollback_file(self, file_path: str) -> bool:
        if file_path in self.file_checkpoints:
            abs_p = os.path.join(self.workspace_root, file_path)
            try:
                with open(abs_p, "w", encoding="utf-8") as f:
                    f.write(self.file_checkpoints[file_path])
                return True
            except OSError:
                return False
        return False

    def run_repair_cycle(self) -> AutonomousRepairReport:
        """Executa o loop completo até o build passar ou atingir o limite de tentativas."""
        start_time = time.time()
        self.applied_fingerprints.clear()
        self.iterations.clear()
        self.file_checkpoints.clear()
        repaired_files: Set[str] = set()
        regressions_count = 0
        rollbacks_count = 0

        current_attempt = 0

        while current_attempt < self.max_repair_attempts:
            current_attempt += 1
            iter_start = time.time()

            # 1. OBSERVE: Executar pipeline de build para obter estado atual
            report = self.pipeline.run_pipeline()
            if report.overall_status == StageStatus.PASSED.value:
                # O projeto já compila e passa em todos os testes!
                return AutonomousRepairReport(
                    success=True,
                    total_attempts=current_attempt - 1,
                    max_attempts=self.max_repair_attempts,
                    duration_seconds=round(time.time() - start_time, 3),
                    files_repaired=sorted(repaired_files),
                    iterations=self.iterations,
                    applied_patch_fingerprints=list(self.applied_fingerprints),
                    regressions_count=regressions_count,
                    rollbacks_count=rollbacks_count,
                    final_pipeline_report=report,
                )

            # 2. CLASSIFY & ROOT_CAUSE: Identificar o primeiro problema acionável
            issue_target, issue_type, issue_obj = self._extract_root_cause_issue(report)
            if not issue_target:
                break

            self._save_checkpoint(issue_target)
            abs_target = os.path.join(self.workspace_root, issue_target)

            try:
                with open(abs_target, "r", encoding="utf-8", errors="replace") as f:
                    current_content = f.read()
            except OSError:
                current_content = ""

            # 3. MINIMAL_REPAIR: Aplicar reparação determinística
            repair_res = self._apply_deterministic_fix(issue_target, issue_type, current_content, issue_obj)
            if not repair_res or not repair_res.success:
                # Reparação determinística não aplicável
                break

            patch_diff = "\n".join(repair_res.applied_changes)
            fp = self._compute_patch_fingerprint(issue_target, patch_diff)

            # Salvaguarda: NO_REPEATED_PATCH (Anti-looping)
            if fp in self.applied_fingerprints:
                # Patch repetido detectado! Aborta para evitar loop infinito
                return AutonomousRepairReport(
                    success=False,
                    total_attempts=current_attempt,
                    max_attempts=self.max_repair_attempts,
                    duration_seconds=round(time.time() - start_time, 3),
                    files_repaired=sorted(repaired_files),
                    iterations=self.iterations,
                    applied_patch_fingerprints=list(self.applied_fingerprints),
                    regressions_count=regressions_count,
                    rollbacks_count=rollbacks_count,
                    final_pipeline_report=report,
                    failure_reason=f"Patch repetido detetado para '{issue_target}'. Interrupção defensiva anti-looping.",
                )

            self.applied_fingerprints.add(fp)

            # Grava ficheiro reparado
            try:
                with open(abs_target, "w", encoding="utf-8") as f:
                    f.write(repair_res.repaired_content)
                repaired_files.add(issue_target)
            except OSError:
                break

            # 4. BUILD & TEST: Validar se a alteração melhorou o sistema
            new_report = self.pipeline.run_pipeline()

            # 5. VERIFY: Verificar regressão
            is_regression = (
                new_report.failed_stages > report.failed_stages
                or (new_report.overall_status == StageStatus.FAILED.value and new_report.first_failure_stage == PipelineStage.SYNTAX.value and report.first_failure_stage != PipelineStage.SYNTAX.value)
            )

            if is_regression:
                regressions_count += 1
                self._rollback_file(issue_target)
                rollbacks_count += 1
                state_record = RepairLoopState.ROLLED_BACK.value
            else:
                state_record = RepairLoopState.VERIFY.value

            iter_rec = RepairIterationRecord(
                iteration_number=current_attempt,
                state=state_record,
                target_file=issue_target,
                issue_type=issue_type,
                patch_fingerprint=fp,
                strategy=repair_res.strategy,
                applied_changes=repair_res.applied_changes,
                pipeline_passed=new_report.overall_status == StageStatus.PASSED.value,
                duration_seconds=round(time.time() - iter_start, 3),
                regression_detected=is_regression,
            )
            self.iterations.append(iter_rec)

            if new_report.overall_status == StageStatus.PASSED.value:
                return AutonomousRepairReport(
                    success=True,
                    total_attempts=current_attempt,
                    max_attempts=self.max_repair_attempts,
                    duration_seconds=round(time.time() - start_time, 3),
                    files_repaired=sorted(repaired_files),
                    iterations=self.iterations,
                    applied_patch_fingerprints=list(self.applied_fingerprints),
                    regressions_count=regressions_count,
                    rollbacks_count=rollbacks_count,
                    final_pipeline_report=new_report,
                )

        # Se esgotou as tentativas sem sucesso
        final_rep = self.pipeline.run_pipeline()
        return AutonomousRepairReport(
            success=final_rep.overall_status == StageStatus.PASSED.value,
            total_attempts=current_attempt,
            max_attempts=self.max_repair_attempts,
            duration_seconds=round(time.time() - start_time, 3),
            files_repaired=sorted(repaired_files),
            iterations=self.iterations,
            applied_patch_fingerprints=list(self.applied_fingerprints),
            regressions_count=regressions_count,
            rollbacks_count=rollbacks_count,
            final_pipeline_report=final_rep,
            failure_reason="Limite de tentativas de reparação atingido sem convergência total.",
        )

    def _extract_root_cause_issue(self, report: PipelineReport) -> Tuple[Optional[str], str, Optional[Any]]:
        """Extrai o primeiro ficheiro e causa raiz a ser reparado."""
        for stage in report.stage_results:
            if stage.status == StageStatus.FAILED.value:
                if stage.stage == PipelineStage.SYNTAX.value and stage.errors:
                    first_err = stage.errors[0]
                    file_name = first_err.split(":")[0].split(" - ")[0].strip()
                    return file_name, "SYNTAX_ERROR", None

                elif stage.stage == PipelineStage.CONTRACTS.value:
                    issues = stage.metadata.get("issues", [])
                    if issues:
                        first_issue = issues[0]
                        return first_issue.get("source_file"), first_issue.get("issue_type"), first_issue

                elif stage.stage == PipelineStage.TESTS.value and stage.errors:
                    # Tenta inferir ficheiro de teste com falha
                    for test_f in self.pipeline.graph.test_mappings.keys():
                        return test_f, "TEST_FAILURE", None

        return None, "UNKNOWN", None

    def _apply_deterministic_fix(
        self,
        file_path: str,
        issue_type: str,
        content: str,
        issue_obj: Optional[Dict[str, Any]],
    ) -> Optional[RepairResult]:
        """Encaminha o problema para a estratégia determinística correta no ASTRepairEngineV2."""
        if issue_type == "SYNTAX_ERROR":
            if file_path.endswith(".py"):
                return self.repair_engine.repair_syntax_python(content, file_path)
            elif file_path.endswith((".js", ".jsx", ".ts", ".tsx")):
                return self.repair_engine.repair_syntax_javascript(content, file_path)

        elif issue_type == ContractIssueType.MISSING_IMPORT.value and issue_obj:
            missing_sym = issue_obj.get("target", "")
            return self.repair_engine.repair_missing_import(content, missing_sym, file_path)

        elif issue_type == ContractIssueType.MISSING_EXPORT.value and issue_obj:
            missing_sym = issue_obj.get("target", "")
            target_f = issue_obj.get("context_data", {}).get("resolved_target", file_path)
            # Lê o ficheiro alvo e injeta o stub
            abs_target = os.path.join(self.workspace_root, target_f)
            if os.path.isfile(abs_target):
                with open(abs_target, "r", encoding="utf-8") as f:
                    t_content = f.read()
                stub_res = self.repair_engine.repair_missing_stub(t_content, missing_sym, target_f)
                if stub_res.success:
                    with open(abs_target, "w", encoding="utf-8") as f:
                        f.write(stub_res.repaired_content)
                return stub_res

        elif issue_type == ContractIssueType.API_CONTRACT_MISMATCH.value and issue_obj:
            issue_typed = ContractValidationIssue(**issue_obj)
            return self.repair_engine.repair_api_contract_mismatch(content, file_path, issue_typed)

        elif issue_type == ContractIssueType.INVALID_PATH_ALIAS.value and issue_obj:
            invalid_alias = issue_obj.get("target", "")
            return self.repair_engine.repair_invalid_path_alias(content, invalid_alias, file_path)

        return None
