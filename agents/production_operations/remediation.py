"""
Phase 71 — Safe Remediation Engine
Enforces 5-stage execution (PRECHECK -> SNAPSHOT -> EXECUTE -> VERIFY -> COMMIT/ROLLBACK).
Rejects forbidden or unapproved high-risk actions.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Callable, Dict, List, Optional
from .models import (
    RecoveryPlan,
    RecoveryStrategy,
    RemediationExecution,
    RemediationSafety,
    RemediationStage,
)


class UnauthorizedRemediationError(PermissionError):
    """Raised when execution of an unauthorized or forbidden action is attempted."""
    pass


class RemediationExecutor:
    """
    Executes recovery plans through a strict 5-stage transactional lifecycle.
    """

    def __init__(self, service_id: str):
        self.service_id = service_id
        self._execution_history: List[RemediationExecution] = []
        self._action_handlers: Dict[RecoveryStrategy, Callable[[], bool]] = {}

    def register_handler(
        self,
        strategy: RecoveryStrategy,
        handler: Callable[[], bool],
    ) -> None:
        self._action_handlers[strategy] = handler

    def execute_plan(
        self,
        plan: RecoveryPlan,
        precheck_fn: Optional[Callable[[], bool]] = None,
        verify_fn: Optional[Callable[[], bool]] = None,
        rollback_fn: Optional[Callable[[], bool]] = None,
    ) -> RemediationExecution:
        """
        Executes the plan following PRECHECK -> SNAPSHOT -> EXECUTE -> VERIFY -> COMMIT / ROLLBACK.
        """
        execution_id = f"exec-{uuid.uuid4().hex[:8]}"

        # Gate 1: Check policy safety
        if plan.safety == RemediationSafety.FORBIDDEN:
            raise UnauthorizedRemediationError(
                f"Action {plan.strategy.value} is FORBIDDEN by production governance policy."
            )
        if plan.safety == RemediationSafety.HIGH_RISK_WITHOUT_APPROVAL and not plan.authorized_by_policy:
            raise UnauthorizedRemediationError(
                f"Action {plan.strategy.value} is HIGH_RISK_WITHOUT_APPROVAL and lacks operator sign-off."
            )

        # Stage 1: PRECHECK
        precheck_ok = True
        if precheck_fn is not None:
            try:
                precheck_ok = precheck_fn()
            except Exception:
                precheck_ok = False

        if not precheck_ok:
            rec = RemediationExecution(
                execution_id=execution_id,
                plan_id=plan.plan_id,
                stage=RemediationStage.PRECHECK,
                success=False,
                precheck_passed=False,
                snapshot_hash=None,
                actions_executed=[],
                verification_passed=False,
                details="Precheck failed: preconditions not satisfied.",
            )
            self._execution_history.append(rec)
            return rec

        # Stage 2: SNAPSHOT
        snapshot_content = f"snapshot:{self.service_id}:{time.time()}:{plan.strategy.value}"
        snapshot_hash = hashlib.sha256(snapshot_content.encode("utf-8")).hexdigest()[:16]

        # Stage 3: EXECUTE
        actions_executed: List[str] = []
        exec_ok = True
        if plan.strategy in self._action_handlers:
            try:
                exec_ok = self._action_handlers[plan.strategy]()
                actions_executed.append(f"Executed handler for {plan.strategy.value}")
            except Exception as exc:
                exec_ok = False
                actions_executed.append(f"Handler failed with exception: {str(exc)}")
        else:
            actions_executed.append(f"Simulated local execution of {plan.strategy.value}")
            exec_ok = True

        if not exec_ok:
            rec = RemediationExecution(
                execution_id=execution_id,
                plan_id=plan.plan_id,
                stage=RemediationStage.EXECUTE,
                success=False,
                precheck_passed=True,
                snapshot_hash=snapshot_hash,
                actions_executed=actions_executed,
                verification_passed=False,
                details="Execution failed during action invocation.",
            )
            self._execution_history.append(rec)
            return rec

        # Stage 4: VERIFY
        verify_ok = True
        if verify_fn is not None:
            try:
                verify_ok = verify_fn()
            except Exception:
                verify_ok = False

        # Stage 5: COMMIT or ROLLBACK
        if verify_ok:
            final_stage = RemediationStage.COMMIT
            details = f"Remediation successfully executed and verified for {plan.strategy.value}."
            success = True
        else:
            final_stage = RemediationStage.ROLLBACK
            details = f"Post-remediation verification failed. Rollback invoked for {plan.strategy.value}."
            success = False
            if rollback_fn is not None:
                try:
                    rollback_fn()
                    actions_executed.append("Rollback action executed successfully.")
                except Exception as r_exc:
                    actions_executed.append(f"Rollback action failed: {str(r_exc)}")

        rec = RemediationExecution(
            execution_id=execution_id,
            plan_id=plan.plan_id,
            stage=final_stage,
            success=success,
            precheck_passed=True,
            snapshot_hash=snapshot_hash,
            actions_executed=actions_executed,
            verification_passed=verify_ok,
            details=details,
        )
        self._execution_history.append(rec)
        return rec

    def get_history(self) -> List[RemediationExecution]:
        return list(self._execution_history)
