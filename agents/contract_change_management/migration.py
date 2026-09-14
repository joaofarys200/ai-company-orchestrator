"""
JARVIS OS — Phase 48: Contract-Aware Autonomous Change Management
ContractMigrationEngine: Formulates formal migration plans, derived DAG tasks, and rollback strategies.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional
from agents.contract_change_management.models import (
    ConsumerPatternMatching,
    ContractChangePrediction,
    ContractConsumerTrace,
    ContractMigrationPlan,
    ContractMigrationTask,
    ContractRiskLevel,
    MigrationStrategy,
    RolloutSafetyStrategy,
)


class ContractMigrationEngine:
    """
    Generates structured, auditable migration plans for contract changes,
    establishing dependency DAGs and rollback guarantees.
    """

    @classmethod
    def formulate_migration_plan(
        cls,
        contract_id: Any,
        current_version: Optional[str] = None,
        proposed_version: Optional[str] = None,
        risk_level: Optional[ContractRiskLevel] = None,
        affected_consumers: Optional[list[ContractConsumerTrace]] = None,
        preferred_strategy: Optional[MigrationStrategy] = None,
    ) -> ContractMigrationPlan:
        """
        Generates a ContractMigrationPlan with required tasks and rollback strategy.
        Accepts either a ContractChangePrediction instance or individual parameters.
        """
        if hasattr(contract_id, "affected_contracts") and hasattr(contract_id, "breaking_risk"):
            # contract_id is actually a ContractChangePrediction
            pred = contract_id
            c_id = pred.affected_contracts[0] if pred.affected_contracts else "unknown"
            c_ver = "1.0.0"
            p_ver = "2.0.0"
            if pred.predicted_diffs:
                c_ver = pred.predicted_diffs[0].contract_version
                p_ver = pred.predicted_diffs[0].proposed_version
            return cls.formulate_migration_plan(
                contract_id=c_id,
                current_version=c_ver,
                proposed_version=p_ver,
                risk_level=pred.breaking_risk,
                affected_consumers=pred.affected_consumers,
                preferred_strategy=preferred_strategy or (current_version if isinstance(current_version, MigrationStrategy) else None),
            )

        c_id = str(contract_id)
        c_ver = current_version or "1.0.0"
        p_ver = proposed_version or "1.1.0"
        r_level = risk_level or ContractRiskLevel.SAFE
        consumers = affected_consumers or []

        migration_id = f"mig_{uuid.uuid4().hex[:10]}"

        # 1. Determine compatibility strategy
        if preferred_strategy:
            strategy = preferred_strategy
        elif r_level == ContractRiskLevel.SAFE or r_level == ContractRiskLevel.NON_BREAKING:
            strategy = MigrationStrategy.BACKWARD_COMPATIBLE
        elif any(c.pattern_matching == ConsumerPatternMatching.CLOSED_EXHAUSTIVE for c in consumers):
            strategy = MigrationStrategy.MIGRATE_THEN_SWITCH
        elif r_level == ContractRiskLevel.BREAKING:
            strategy = MigrationStrategy.VERSIONED_ENDPOINT
        else:
            strategy = MigrationStrategy.BACKWARD_COMPATIBLE

        # 2. Derive required tasks with causal dependencies
        tasks: list[ContractMigrationTask] = []

        # Backend change task
        t_backend_id = f"task_{migration_id}_01_backend"
        tasks.append(ContractMigrationTask(
            task_id=t_backend_id,
            title=f"Deploy contract changes for {contract_id} ({proposed_version})",
            target_component="BACKEND",
            category="BACKEND",
            description=f"Update route schema and handlers to satisfy contract version {proposed_version}.",
            dependencies=[],
        ))

        # Consumer migration tasks (for affected consumers)
        prev_dep = t_backend_id if strategy != MigrationStrategy.MIGRATE_THEN_SWITCH else None
        consumer_task_ids = []
        for idx, consumer in enumerate(affected_consumers):
            if consumer.pattern_matching == ConsumerPatternMatching.CLOSED_EXHAUSTIVE or risk_level in (ContractRiskLevel.BREAKING, ContractRiskLevel.POTENTIALLY_BREAKING):
                t_consumer_id = f"task_{migration_id}_02_consumer_{idx+1}"
                deps = [t_backend_id] if strategy != MigrationStrategy.MIGRATE_THEN_SWITCH else []
                tasks.append(ContractMigrationTask(
                    task_id=t_consumer_id,
                    title=f"Migrate consumer {consumer.name}",
                    target_component=consumer.consumer_id,
                    category="FRONTEND" if consumer.language == "TypeScript" else "BACKEND",
                    description=f"Update {consumer.file_path}: {consumer.required_action} ({consumer.impact_reason}).",
                    dependencies=deps,
                ))
                consumer_task_ids.append(t_consumer_id)

        # Test verification task
        t_test_id = f"task_{migration_id}_03_tests"
        tasks.append(ContractMigrationTask(
            task_id=t_test_id,
            title=f"Update and execute contract test suite for {contract_id}",
            target_component="TESTS",
            category="TEST",
            description=f"Ensure integration and contract test suites validate {proposed_version}.",
            dependencies=[t_backend_id] + consumer_task_ids,
        ))

        # Browser verification task
        t_browser_id = f"task_{migration_id}_04_browser"
        tasks.append(ContractMigrationTask(
            task_id=t_browser_id,
            title=f"Run browser scenario QA for {contract_id}",
            target_component="BROWSER",
            category="BROWSER",
            description=f"Execute official browser end-to-end scenarios verifying visual rendering without console/network errors.",
            dependencies=[t_test_id],
        ))

        # 3. Formulate validation plan
        validation_plan = [
            f"Pre-flight schema comparison: {current_version} -> {proposed_version}",
            "Unit and integration test suites execution",
            "Consumer reverse dependency compatibility check",
            "Browser QA validation session in Microsoft Edge",
            "Zero false success confirmation via Contract Completion Gate",
        ]

        approval_required = risk_level in (ContractRiskLevel.BREAKING, ContractRiskLevel.POTENTIALLY_BREAKING) or strategy in (
            MigrationStrategy.BREAKING_CHANGE,
            MigrationStrategy.VERSIONED_ENDPOINT,
            MigrationStrategy.MIGRATE_THEN_SWITCH,
        )

        return ContractMigrationPlan(
            migration_id=migration_id,
            contract_id=contract_id,
            source_contract_version=current_version,
            target_contract_version=proposed_version,
            affected_consumers=affected_consumers,
            required_tasks=tasks,
            compatibility_strategy=strategy,
            rollout_strategy=RolloutSafetyStrategy.PREPARE_VALIDATE_MIGRATE_SWITCH,
            rollback_strategy=f"RESTORE_ACTIVE_VERSION_{current_version}_WITH_AUDIT_PRESERVATION",
            validation_plan=validation_plan,
            approval_required=approval_required,
            status="PROPOSED" if approval_required else "APPROVED",
        )
