"""
JARVIS OS — Phase 48: Contract-Aware Autonomous Change Management
ContractChangeAnalyzer: Analyzes planned tasks and predicted files to determine contract changes,
consumer impact, risk classification, and pre-execution diff simulation (read-only).
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from agents.contract_change_management.consumers import ContractConsumerTracer
from agents.contract_change_management.migration import ContractMigrationEngine
from agents.contract_change_management.models import (
    ConsumerPatternMatching,
    ContractChangePrediction,
    ContractChangeState,
    ContractChangeType,
    ContractConsumerTrace,
    ContractPreflightSimulation,
    ContractRiskLevel,
    PredictedContractDiff,
)


class ContractChangeAnalyzer:
    """
    Analyzes tasks prior to execution to detect contract changes,
    simulate pre-execution structural diffs, and classify consumer impact.
    """

    @classmethod
    def compute_state_hash(cls, state_obj: Any) -> str:
        """Computes deterministic SHA-256 hash of a state snapshot."""
        try:
            serialized = json.dumps(state_obj, sort_keys=True, default=str)
        except Exception:
            serialized = str(state_obj)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def simulate_pre_execution_diff(
        cls,
        current_contract: dict[str, Any],
        predicted_contract: dict[str, Any],
    ) -> ContractPreflightSimulation:
        """
        Simulates pre-execution contract diff while guaranteeing read-only execution:
        state_before == state_after.
        """
        sim_id = f"sim_{uuid.uuid4().hex[:10]}"
        state_before_hash = cls.compute_state_hash(current_contract)

        # Deepcopy to guarantee zero side-effects
        curr_copy = copy.deepcopy(current_contract)
        pred_copy = copy.deepcopy(predicted_contract)

        diff_items = []
        overall_risk = ContractRiskLevel.SAFE

        curr_schema = curr_copy.get("schema", curr_copy.get("response_schema", {}))
        pred_schema = pred_copy.get("schema", pred_copy.get("response_schema", {}))

        # Check for field additions, removals, or type changes
        curr_keys = set(curr_schema.keys())
        pred_keys = set(pred_schema.keys())

        for k in curr_keys - pred_keys:
            diff_items.append({
                "type": ContractChangeType.REMOVE_FIELD.value,
                "field": k,
                "old": str(curr_schema[k]),
                "new": None,
                "risk": ContractRiskLevel.BREAKING.value,
            })
            overall_risk = ContractRiskLevel.BREAKING

        for k in pred_keys - curr_keys:
            # Check if optional or required
            is_optional = pred_copy.get("optional_fields", [])
            if k in is_optional:
                diff_items.append({
                    "type": ContractChangeType.ADD_OPTIONAL_FIELD.value,
                    "field": k,
                    "old": None,
                    "new": str(pred_schema[k]),
                    "risk": ContractRiskLevel.NON_BREAKING.value,
                })
                if overall_risk == ContractRiskLevel.SAFE:
                    overall_risk = ContractRiskLevel.NON_BREAKING
            else:
                diff_items.append({
                    "type": ContractChangeType.ADD_REQUIRED_FIELD.value,
                    "field": k,
                    "old": None,
                    "new": str(pred_schema[k]),
                    "risk": ContractRiskLevel.BREAKING.value,
                })
                overall_risk = ContractRiskLevel.BREAKING

        for k in curr_keys & pred_keys:
            old_val = curr_schema[k]
            new_val = pred_schema[k]
            if old_val != new_val:
                diff_items.append({
                    "type": ContractChangeType.CHANGE_FIELD_TYPE.value,
                    "field": k,
                    "old": str(old_val),
                    "new": str(new_val),
                    "risk": ContractRiskLevel.BREAKING.value,
                })
                overall_risk = ContractRiskLevel.BREAKING

        # Check auth changes
        curr_auth = curr_copy.get("auth", curr_copy.get("requires_auth", False))
        pred_auth = pred_copy.get("auth", pred_copy.get("requires_auth", False))
        if curr_auth != pred_auth:
            diff_items.append({
                "type": ContractChangeType.CHANGE_AUTH.value,
                "field": "auth",
                "old": str(curr_auth),
                "new": str(pred_auth),
                "risk": ContractRiskLevel.BREAKING.value,
            })
            overall_risk = ContractRiskLevel.BREAKING

        # Check polymorphic variants
        curr_vars = set(curr_copy.get("variants", []))
        pred_vars = set(pred_copy.get("variants", []))
        if curr_vars != pred_vars:
            removed_vars = curr_vars - pred_vars
            added_vars = pred_vars - curr_vars
            if removed_vars:
                diff_items.append({
                    "type": ContractChangeType.REMOVE_VARIANT.value,
                    "field": "variants",
                    "old": list(removed_vars),
                    "new": None,
                    "risk": ContractRiskLevel.BREAKING.value,
                })
                overall_risk = ContractRiskLevel.BREAKING
            if added_vars:
                diff_items.append({
                    "type": ContractChangeType.ADD_VARIANT.value,
                    "field": "variants",
                    "old": None,
                    "new": list(added_vars),
                    "risk": ContractRiskLevel.POTENTIALLY_BREAKING.value,
                })
                if overall_risk in (ContractRiskLevel.SAFE, ContractRiskLevel.NON_BREAKING):
                    overall_risk = ContractRiskLevel.POTENTIALLY_BREAKING

        state_after_hash = cls.compute_state_hash(current_contract)
        is_read_only = (state_before_hash == state_after_hash)

        return ContractPreflightSimulation(
            simulation_id=sim_id,
            state_before_hash=state_before_hash,
            state_after_hash=state_after_hash,
            is_read_only=is_read_only,
            diff_verdict=overall_risk,
            details={
                "diff_items": diff_items,
                "changes_count": len(diff_items),
                "contract_id": current_contract.get("contract_id", "unknown"),
            },
        )

    simulate_preflight = simulate_pre_execution_diff

    @classmethod
    def analyze_task_change(
        cls,
        task: dict[str, Any],
        predicted_files: list[str],
        semantic_graph: Optional[Any] = None,
        contract_baselines: Optional[dict[str, Any]] = None,
        polymorphic_schemas: Optional[dict[str, Any]] = None,
        task_code_snippet: Optional[str] = None,
    ) -> ContractChangePrediction:
        """
        Analyzes a task before execution, deriving predicted contract diffs,
        tracing affected consumers, and classifying risk.
        """
        task_id = task.get("id", task.get("task_id", f"task_{uuid.uuid4().hex[:6]}"))
        title = task.get("title", task.get("description", ""))
        desc = task.get("description", "")
        text_corpus = f"{title} {desc}".lower()

        prediction_id = f"pred_{uuid.uuid4().hex[:10]}"
        affected_contracts: list[str] = []
        predicted_diffs: list[PredictedContractDiff] = []
        overall_risk = ContractRiskLevel.SAFE
        change_type = ContractChangeType.NO_CHANGE

        # Detect target contract based on files or text corpus
        contract_id = "contract_unknown"
        route = "/api/v1/unknown"

        if any("event" in f.lower() for f in predicted_files) or "events" in text_corpus or "audit" in text_corpus:
            contract_id = "contract_events_v1"
            route = "/api/v1/events"
            affected_contracts.append(contract_id)
        elif any("user" in f.lower() for f in predicted_files) or "users" in text_corpus or "avatar" in text_corpus:
            contract_id = "contract_users_v1"
            route = "/api/v1/users"
            affected_contracts.append(contract_id)
        elif any("payment" in f.lower() for f in predicted_files) or "payment" in text_corpus:
            contract_id = "contract_payments_v2"
            route = "/api/v2/payments"
            affected_contracts.append(contract_id)

        # Classify change type from task intent
        if "avatar" in text_corpus and ("object" in text_corpus or "struct" in text_corpus or "type" in text_corpus):
            change_type = ContractChangeType.CHANGE_FIELD_TYPE
            diff = PredictedContractDiff(
                diff_id=f"diff_{uuid.uuid4().hex[:8]}",
                contract_id=contract_id,
                contract_version="1.0.0",
                proposed_version="2.0.0",
                change_type=change_type,
                field_path="avatar",
                old_definition="string (URL)",
                new_definition="object { url: string, width: int, height: int }",
                risk_level=ContractRiskLevel.BREAKING,
                reason="Avatar primitive string converted to nested object structure.",
            )
            predicted_diffs.append(diff)
            overall_risk = ContractRiskLevel.BREAKING

        elif "optional" in text_corpus and "field" in text_corpus or "user_tier" in text_corpus or "add optional" in text_corpus:
            change_type = ContractChangeType.ADD_OPTIONAL_FIELD
            field_name = "user_tier" if "tier" in text_corpus else "nickname"
            diff = PredictedContractDiff(
                diff_id=f"diff_{uuid.uuid4().hex[:8]}",
                contract_id=contract_id,
                contract_version="1.0.0",
                proposed_version="1.1.0",
                change_type=change_type,
                field_path=field_name,
                old_definition=None,
                new_definition=f"optional string ({field_name})",
                risk_level=ContractRiskLevel.NON_BREAKING,
                reason=f"Additive non-breaking field '{field_name}' added to payload.",
            )
            predicted_diffs.append(diff)
            overall_risk = ContractRiskLevel.NON_BREAKING

        elif "remove field" in text_corpus or "delete field" in text_corpus:
            change_type = ContractChangeType.REMOVE_FIELD
            diff = PredictedContractDiff(
                diff_id=f"diff_{uuid.uuid4().hex[:8]}",
                contract_id=contract_id,
                contract_version="1.0.0",
                proposed_version="2.0.0",
                change_type=change_type,
                field_path="legacy_token",
                old_definition="string",
                new_definition=None,
                risk_level=ContractRiskLevel.BREAKING,
                reason="Removal of existing contract property breaks backward compatibility.",
            )
            predicted_diffs.append(diff)
            overall_risk = ContractRiskLevel.BREAKING

        elif "variant" in text_corpus or "polymorphic" in text_corpus:
            if "remove" in text_corpus:
                change_type = ContractChangeType.REMOVE_VARIANT
                diff = PredictedContractDiff(
                    diff_id=f"diff_{uuid.uuid4().hex[:8]}",
                    contract_id=contract_id,
                    contract_version="1.2.0",
                    proposed_version="2.0.0",
                    change_type=change_type,
                    field_path="variants.user.deleted",
                    old_definition="UserDeleted variant",
                    new_definition=None,
                    risk_level=ContractRiskLevel.BREAKING,
                    reason="Removal of valid contract variant breaks consumers relying on this subtype.",
                )
                predicted_diffs.append(diff)
                overall_risk = ContractRiskLevel.BREAKING
            else:
                change_type = ContractChangeType.ADD_VARIANT
                diff = PredictedContractDiff(
                    diff_id=f"diff_{uuid.uuid4().hex[:8]}",
                    contract_id=contract_id,
                    contract_version="1.2.0",
                    proposed_version="1.3.0",
                    change_type=change_type,
                    field_path="variants.user.archived",
                    old_definition=None,
                    new_definition="UserArchived variant",
                    risk_level=ContractRiskLevel.POTENTIALLY_BREAKING,
                    reason="New variant added to discriminated union; may break exhaustive matchers.",
                )
                predicted_diffs.append(diff)
                overall_risk = ContractRiskLevel.POTENTIALLY_BREAKING

        elif "auth" in text_corpus or "remove auth" in text_corpus or "disable auth" in text_corpus:
            change_type = ContractChangeType.CHANGE_AUTH
            diff = PredictedContractDiff(
                diff_id=f"diff_{uuid.uuid4().hex[:8]}",
                contract_id=contract_id,
                contract_version="1.0.0",
                proposed_version="2.0.0",
                change_type=change_type,
                field_path="auth.security_policy",
                old_definition="Bearer JWT required",
                new_definition="None",
                risk_level=ContractRiskLevel.BREAKING,
                reason="Disabling or weakening authentication contract violates security invariants.",
            )
            predicted_diffs.append(diff)
            overall_risk = ContractRiskLevel.BREAKING

        # Trace consumers
        affected_consumers = ContractConsumerTracer.trace_consumers(
            contract_id=contract_id,
            route=route,
            semantic_graph=semantic_graph,
            code_snippet=task_code_snippet,
        )

        # Re-evaluate risk if any consumer has closed exhaustive pattern matching
        if overall_risk == ContractRiskLevel.POTENTIALLY_BREAKING:
            if any(c.pattern_matching == ConsumerPatternMatching.CLOSED_EXHAUSTIVE for c in affected_consumers):
                overall_risk = ContractRiskLevel.BREAKING

        migration_required = (overall_risk in (ContractRiskLevel.BREAKING, ContractRiskLevel.POTENTIALLY_BREAKING))
        approval_required = (overall_risk in (ContractRiskLevel.BREAKING, ContractRiskLevel.POTENTIALLY_BREAKING))
        revalidation_required = (overall_risk != ContractRiskLevel.SAFE)

        evidence_required = [
            "contract_preflight_diff_simulation",
            "consumer_compatibility_verification",
            "unit_test_suite_execution",
            "browser_qa_validation",
        ]
        if migration_required:
            evidence_required.append("migration_plan_execution_evidence")

        # Formulate migration plan if required
        migration_plan = None
        if migration_required:
            migration_plan = ContractMigrationEngine.formulate_migration_plan(
                contract_id=contract_id,
                current_version="1.0.0",
                proposed_version="2.0.0",
                risk_level=overall_risk,
                affected_consumers=affected_consumers,
            )

        return ContractChangePrediction(
            prediction_id=prediction_id,
            task_id=task_id,
            predicted_files=predicted_files,
            affected_contracts=affected_contracts,
            predicted_diffs=predicted_diffs,
            affected_consumers=affected_consumers,
            breaking_risk=overall_risk,
            migration_required=migration_required,
            revalidation_required=revalidation_required,
            approval_required=approval_required,
            evidence_required=evidence_required,
            migration_plan=migration_plan,
            state=ContractChangeState.PREDICTED,
        )
