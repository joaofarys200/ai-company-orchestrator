"""Real domain dispatchers for mission governance, loop, contract, and quality operations.

Replaces legacy unimplemented stub operations in `MissionWebSocketHandler` with direct
lazy-imported routing to `MissionControlEngine`, `LongHorizonMissionBridge`, and
`EngineeringQualityGovernanceBridge` (avoiding circular top-level imports with `server.py`).
"""

from __future__ import annotations

from typing import Any, Callable


GovernanceHandler = Callable[[dict[str, Any]], dict[str, Any]]


def _control_engine() -> Any:
    from agents.mission_control_engine import MissionControlEngine

    return MissionControlEngine


def _long_horizon_bridge() -> Any:
    from backend.agents.long_horizon_missions.bridge import LongHorizonMissionBridge

    return LongHorizonMissionBridge.get_instance()


def _quality_bridge() -> Any:
    from backend.agents.engineering_quality_governance.bridge import (
        EngineeringQualityGovernanceBridge,
    )

    return EngineeringQualityGovernanceBridge.get_instance()


def _mission_id(message: dict[str, Any], default: str = "default_mission") -> str:
    raw = str(message.get("mission_id") or "").strip()
    return raw or default


def _scenario_key(message: dict[str, Any]) -> str:
    raw = str(message.get("scenario_key") or "").strip()
    return raw or "interactive"


def _handle_loop_status(message: dict[str, Any]) -> dict[str, Any]:
    mid = _mission_id(message, default="m_p36_interactive")
    summary = _control_engine().get_autonomous_loop_summary(
        mission_id=mid,
        scenario_key=_scenario_key(message),
    )
    return {
        "type": "mission_loop_status_result",
        "mission_id": summary.get("mission_id", mid),
        "summary": summary,
    }


def _handle_loop_step(message: dict[str, Any]) -> dict[str, Any]:
    mid = _mission_id(message, default="m_p36_interactive")
    loop_state, decision = _control_engine().step_autonomous_loop(
        mission_id=mid,
        scenario_key=_scenario_key(message),
        simulated_executions=message.get("simulated_executions"),
        simulated_validations=message.get("simulated_validations"),
        sentinel_violation=bool(message.get("sentinel_violation", False)),
        economic_approval_needed=bool(message.get("economic_approval_needed", False)),
        plan_invalid_signal=bool(message.get("plan_invalid_signal", False)),
        human_approval_signal=bool(message.get("human_approval_signal", False)),
    )
    return {
        "type": "mission_loop_step_result",
        "mission_id": mid,
        "loop_state": loop_state,
        "decision": decision,
    }


def _handle_loop_run(message: dict[str, Any]) -> dict[str, Any]:
    engine = _control_engine()
    mid = _mission_id(message, default="m_p36_interactive")
    scenario = _scenario_key(message)
    max_steps = min(max(int(message.get("max_steps") or 3), 1), 25)
    steps: list[dict[str, Any]] = []
    for _ in range(max_steps):
        loop_state, decision = engine.step_autonomous_loop(
            mission_id=mid,
            scenario_key=scenario,
            simulated_executions=message.get("simulated_executions"),
            simulated_validations=message.get("simulated_validations"),
        )
        steps.append({"loop_state": loop_state, "decision": decision})
        stage = str(loop_state.get("current_stage") or "").upper()
        if stage in {"COMPLETED", "BLOCKED", "WAITING_HUMAN", "FAILED", "CANCELLED"}:
            break
    summary = engine.get_autonomous_loop_summary(
        mission_id=mid,
        scenario_key=scenario,
    )
    return {
        "type": "mission_loop_run_result",
        "mission_id": summary.get("mission_id", mid),
        "steps_executed": len(steps),
        "steps": steps,
        "summary": summary,
    }


def _handle_loop_respond_human(message: dict[str, Any]) -> dict[str, Any]:
    mid = _mission_id(message, default="m_p36_interactive")
    scenario = _scenario_key(message)
    action = str(message.get("action") or "APPROVE").strip().upper()
    feedback = message.get("feedback")
    controller = _control_engine().get_autonomous_loop_controller(
        mission_id=mid,
        scenario_key=scenario,
    )
    controller.respond_to_human(action=action, feedback=feedback)
    return {
        "type": "mission_loop_respond_human_result",
        "mission_id": controller.mission_id,
        "action": action,
        "summary": controller.get_summary(),
    }


def _handle_decision_quality_status(message: dict[str, Any]) -> dict[str, Any]:
    mid = _mission_id(message, default="m_p36_interactive")
    summary = _control_engine().get_decision_quality_summary(
        mission_id=mid,
        scenario_key=_scenario_key(message),
    )
    return {
        "type": "mission_decision_quality_status_result",
        "mission_id": mid,
        **summary,
    }


def _handle_policy_proposal_review(message: dict[str, Any]) -> dict[str, Any]:
    engine = _control_engine()
    if not engine._policy_proposals:
        engine.get_decision_quality_summary(
            mission_id=_mission_id(message, default="m_p36_interactive"),
        )
    proposal_id = str(message.get("proposal_id") or "").strip()
    action = str(message.get("action") or "APPROVE").strip().upper()
    operator = str(message.get("operator_id") or message.get("approver") or "human_operator")
    notes = str(message.get("notes") or "")
    try:
        if action in {"APPROVE", "ACCEPT"}:
            res = engine.approve_policy_proposal(
                proposal_id=proposal_id,
                approver=operator,
                notes=notes or "Approved via mission governance dispatch.",
            )
        elif action in {"REJECT", "DENY", "BLOCK"}:
            res = engine.reject_policy_proposal(
                proposal_id=proposal_id,
                rejector=operator,
                reason=notes or "Rejected via mission governance dispatch.",
            )
        else:
            res = {"success": False, "error": f"Unsupported policy review action '{action}'."}
    except ValueError as exc:
        res = {"success": False, "proposal_id": proposal_id, "error": str(exc)}
    return {
        "type": "mission_policy_proposal_review_result",
        **res,
    }


def _handle_policy_rollback(message: dict[str, Any]) -> dict[str, Any]:
    target_version = message.get("target_version")
    operator = str(message.get("operator_id") or message.get("operator") or "human_operator")
    try:
        res = _control_engine().rollback_policy(
            target_version=str(target_version) if target_version else None,
            operator=operator,
        )
    except Exception as exc:
        res = {"success": False, "error": str(exc)}
    return {
        "type": "mission_policy_rollback_result",
        **res,
    }


def _handle_experience_memory_status(message: dict[str, Any]) -> dict[str, Any]:
    summary = _control_engine().get_experience_memory_summary(
        mission_id=message.get("mission_id"),
    )
    return {
        "type": "mission_experience_memory_status_result",
        **summary,
    }


def _handle_experience_curate(message: dict[str, Any]) -> dict[str, Any]:
    res = _control_engine().curate_experience(
        experience_id=str(message.get("experience_id") or ""),
        action=str(message.get("action") or "APPROVE"),
        curator_id=str(message.get("curator_id") or message.get("operator_id") or "human_operator"),
        notes=str(message.get("notes") or ""),
    )
    return {
        "type": "mission_experience_curate_result",
        **res,
    }


def _handle_semantic_graph_status(message: dict[str, Any]) -> dict[str, Any]:
    summary = _control_engine().get_semantic_graph_summary(
        mission_id=message.get("mission_id"),
    )
    return {
        "type": "mission_semantic_graph_status_result",
        **summary,
    }


def _handle_contract_discovery_status(message: dict[str, Any]) -> dict[str, Any]:
    summary = _control_engine().get_contract_discovery_summary(
        mission_id=message.get("mission_id"),
    )
    return {
        "type": "mission_contract_discovery_status_result",
        **summary,
    }


def _handle_contract_proposal_review(message: dict[str, Any]) -> dict[str, Any]:
    res = _control_engine().review_contract_proposal(
        proposal_id=str(message.get("proposal_id") or ""),
        action=str(message.get("action") or "ACCEPT").upper(),
        operator_id=str(message.get("operator_id") or "human_operator"),
        notes=str(message.get("notes") or ""),
    )
    return {
        "type": "mission_contract_proposal_review_result",
        **res,
    }


def _handle_contract_health_status(message: dict[str, Any]) -> dict[str, Any]:
    summary = _control_engine().get_contract_health_summary(
        mission_id=message.get("mission_id"),
    )
    return {
        "type": "mission_contract_health_status_result",
        **summary,
    }


def _handle_contract_drift_review(message: dict[str, Any]) -> dict[str, Any]:
    res = _control_engine().review_contract_drift(
        drift_id=str(message.get("drift_id") or ""),
        action=str(message.get("action") or "APPROVE"),
        operator_id=str(message.get("operator_id") or "human_operator"),
        notes=str(message.get("notes") or ""),
    )
    return {
        "type": "mission_contract_drift_review_result",
        **res,
    }


def _handle_contract_rollback(message: dict[str, Any]) -> dict[str, Any]:
    res = _control_engine().rollback_contract_version(
        contract_id=str(message.get("contract_id") or ""),
        target_version=str(message.get("target_version") or ""),
        operator_id=str(message.get("operator_id") or "human_operator"),
        notes=str(message.get("notes") or ""),
    )
    return {
        "type": "mission_contract_rollback_result",
        **res,
    }


def _handle_polymorphic_schema_status(message: dict[str, Any]) -> dict[str, Any]:
    summary = _control_engine().get_polymorphic_schema_summary(
        mission_id=message.get("mission_id"),
    )
    return {
        "type": "mission_polymorphic_schema_status_result",
        **summary,
    }


def _handle_polymorphic_variant_review(message: dict[str, Any]) -> dict[str, Any]:
    res = _control_engine().review_polymorphic_variant(
        schema_id=str(message.get("schema_id") or ""),
        variant_id=str(message.get("variant_id") or ""),
        action=str(message.get("action") or "APPROVE"),
        operator_id=str(message.get("operator_id") or "human_operator"),
        notes=str(message.get("notes") or ""),
    )
    return {
        "type": "mission_polymorphic_variant_review_result",
        **res,
    }


def _handle_polymorphic_compatibility_check(message: dict[str, Any]) -> dict[str, Any]:
    old_schema_id = str(message.get("old_schema_id") or message.get("schema_id") or "")
    new_schema_id = str(
        message.get("new_schema_id")
        or message.get("target_schema_id")
        or old_schema_id
    )
    res = _control_engine().evaluate_polymorphic_compatibility(
        old_schema_id=old_schema_id,
        new_schema_id=new_schema_id,
    )
    return {
        "type": "mission_polymorphic_compatibility_check_result",
        "old_schema_id": old_schema_id,
        "new_schema_id": new_schema_id,
        **res,
    }


def _handle_contract_change_prediction(message: dict[str, Any]) -> dict[str, Any]:
    summary = _control_engine().get_contract_change_summary(
        mission_id=message.get("mission_id"),
    )
    return {
        "type": "mission_contract_change_prediction_result",
        **summary,
    }


def _handle_contract_migration_plan(message: dict[str, Any]) -> dict[str, Any]:
    migration_id = str(message.get("migration_id") or "").strip()
    summary = _control_engine().get_contract_change_summary(
        mission_id=message.get("mission_id"),
    )
    migrations = list(summary.get("migrations") or [])
    matched = next(
        (m for m in migrations if m.get("migration_id") == migration_id),
        None,
    )
    return {
        "type": "mission_contract_migration_plan_result",
        "migration_id": migration_id,
        "found": matched is not None,
        "migration": matched,
        "migrations": migrations,
    }


def _handle_contract_change_gate_action(message: dict[str, Any]) -> dict[str, Any]:
    res = _control_engine().process_contract_gate_action(
        migration_id=str(message.get("migration_id") or ""),
        action=str(message.get("action") or "APPROVE"),
        operator_id=str(message.get("operator_id") or "human_operator"),
        signature=message.get("signature"),
    )
    return {
        "type": "mission_contract_change_gate_action_result",
        **res,
    }


def _handle_build_contract_extraction_status(message: dict[str, Any]) -> dict[str, Any]:
    summary = _control_engine().get_build_contract_extraction_status(
        mission_id=message.get("mission_id"),
    )
    return {
        "type": "mission_build_contract_extraction_status_result",
        **summary,
    }


def _handle_dynamic_consumer_resolution(message: dict[str, Any]) -> dict[str, Any]:
    resolutions = _control_engine().get_dynamic_consumer_resolutions(
        mission_id=message.get("mission_id"),
    )
    return {
        "type": "mission_dynamic_consumer_resolution_result",
        "total": len(resolutions),
        "resolutions": resolutions,
    }


def _handle_build_contract_trigger_extract(message: dict[str, Any]) -> dict[str, Any]:
    res = _control_engine().trigger_build_contract_extraction(
        mission_id=message.get("mission_id"),
    )
    return {
        "type": "mission_build_contract_trigger_extract_result",
        **res,
    }


def _handle_behavioral_baseline_status(message: dict[str, Any]) -> dict[str, Any]:
    summary = _control_engine().get_behavioral_baseline_status(
        mission_id=message.get("mission_id"),
    )
    return {
        "type": "mission_behavioral_baseline_status_result",
        **summary,
    }


def _handle_behavioral_proof_status(message: dict[str, Any]) -> dict[str, Any]:
    proofs = _control_engine().get_behavioral_proof_status(
        mission_id=message.get("mission_id"),
    )
    return {
        "type": "mission_behavioral_proof_status_result",
        "total": len(proofs),
        "proofs": proofs,
    }


def _handle_behavioral_proof_trigger(message: dict[str, Any]) -> dict[str, Any]:
    res = _control_engine().trigger_behavioral_proof(
        mission_id=message.get("mission_id"),
    )
    return {
        "type": "mission_behavioral_proof_trigger_result",
        **res,
    }


def _handle_long_horizon_checkpoint_create(message: dict[str, Any]) -> dict[str, Any]:
    from backend.agents.long_horizon_missions.models import CheckpointType

    bridge = _long_horizon_bridge()
    mid = _mission_id(message)
    engine = bridge.engines.get(mid)
    if engine is None:
        return {
            "type": "mission_long_horizon_checkpoint_create_result",
            "success": False,
            "mission_id": mid,
            "error": f"Long-horizon mission '{mid}' not found.",
        }

    cp_type_raw = str(message.get("checkpoint_type") or "MILESTONE").upper()
    try:
        cp_type = CheckpointType(cp_type_raw)
    except ValueError:
        cp_type = CheckpointType.MILESTONE

    cp_mgr = bridge.checkpoint_managers[mid]
    mission = engine.mission
    checkpoint = cp_mgr.create_checkpoint(
        mission_id=mid,
        checkpoint_type=cp_type,
        mission_state=mission.current_state.value,
        objective_state={
            k: v.to_dict() if hasattr(v, "to_dict") else v
            for k, v in getattr(mission, "objectives", {}).items()
        } if isinstance(getattr(mission, "objectives", None), dict) else {},
        plan_dag=mission.plan.to_dict() if mission.plan else {},
        agent_states=dict(getattr(mission, "agent_states", {})),
        claims=list(getattr(mission, "claims", [])),
        workspace_states=dict(message.get("workspace_states") or {}),
        transaction_states=dict(message.get("transaction_states") or {}),
        architecture_hash=str(message.get("architecture_hash") or "arch_v1"),
        contract_hash=str(message.get("contract_hash") or "contract_v1"),
        behavior_hash=str(message.get("behavior_hash") or "behavior_v1"),
        verification_ledger=list(getattr(mission, "verification_ledger", [])),
        budget_remaining=(
            mission.budget.remaining_budget()
            if hasattr(mission.budget, "remaining_budget")
            else {}
        ),
        evidence_root=str(message.get("evidence_root") or "evidence://long_horizon"),
        checkpoint_id=message.get("checkpoint_id"),
    )
    return {
        "type": "mission_long_horizon_checkpoint_create_result",
        "success": True,
        "mission_id": mid,
        "checkpoint": checkpoint.to_dict(),
    }


def _handle_long_horizon_recover(message: dict[str, Any]) -> dict[str, Any]:
    from backend.agents.long_horizon_missions.models import MissionState

    bridge = _long_horizon_bridge()
    mid = _mission_id(message)
    mission = bridge.get_mission(mid)
    cp_mgr = bridge.checkpoint_managers.get(mid)
    recovery_engine = bridge.recovery_engines.get(mid)
    if mission is None or cp_mgr is None or recovery_engine is None:
        return {
            "type": "mission_long_horizon_recover_result",
            "success": False,
            "mission_id": mid,
            "error": f"Long-horizon mission '{mid}' not found.",
        }

    checkpoint_id = message.get("checkpoint_id")
    checkpoint = (
        cp_mgr.get_checkpoint(str(checkpoint_id))
        if checkpoint_id
        else cp_mgr.get_latest_checkpoint()
    )
    if checkpoint is None:
        return {
            "type": "mission_long_horizon_recover_result",
            "success": False,
            "mission_id": mid,
            "error": f"No checkpoint available to recover mission '{mid}'.",
        }

    decision, report = recovery_engine.reconcile_and_resume(
        mission=mission,
        checkpoint=checkpoint,
        current_workspace_state=dict(message.get("workspace_state") or {}),
        applied_transaction_ids=set(message.get("applied_transaction_ids") or []),
    )
    if decision == "RESUME" and mission.current_state == MissionState.RECOVERING:
        mission.current_state = MissionState.EXECUTING
    bridge.persistence.save_mission(mission)
    return {
        "type": "mission_long_horizon_recover_result",
        "success": True,
        "mission_id": mid,
        "decision": decision,
        "report": report,
        "mission": mission.to_dict(),
    }


def _handle_long_horizon_adapt(message: dict[str, Any]) -> dict[str, Any]:
    bridge = _long_horizon_bridge()
    mid = _mission_id(message)
    engine = bridge.engines.get(mid)
    if engine is None or engine.mission.plan is None:
        return {
            "type": "mission_long_horizon_adapt_result",
            "success": False,
            "mission_id": mid,
            "error": f"Long-horizon mission plan for '{mid}' not found.",
        }

    plan = engine.mission.plan
    default_milestone = plan.topological_order[0] if plan.topological_order else "M_01"
    completed_milestone_id = str(message.get("milestone_id") or default_milestone)
    observed_outputs = [str(x) for x in (message.get("observed_outputs") or [])]
    unresolved_issues = [str(x) for x in (message.get("unresolved_issues") or [])]
    primary_ids = set(getattr(engine.objectives, "primary_objective_ids", lambda: [])() or [])
    if not primary_ids and hasattr(engine.objectives, "objectives"):
        primary_ids = {
            oid for oid in getattr(engine.objectives, "objectives", {}).keys()
        }

    did_adapt, updated_plan, stall_state = engine.replanner.observe_and_adapt(
        plan=plan,
        completed_milestone_id=completed_milestone_id,
        observed_outputs=observed_outputs,
        unresolved_issues=unresolved_issues,
        primary_objective_ids=primary_ids,
    )
    engine.mission.plan = updated_plan
    bridge.persistence.save_mission(engine.mission)
    return {
        "type": "mission_long_horizon_adapt_result",
        "success": True,
        "mission_id": mid,
        "did_adapt": did_adapt,
        "stall_state": stall_state.value,
        "replan_count": updated_plan.replan_count,
        "plan": updated_plan.to_dict(),
    }


def _handle_long_horizon_completion_evaluate(message: dict[str, Any]) -> dict[str, Any]:
    bridge = _long_horizon_bridge()
    mid = _mission_id(message)
    engine = bridge.engines.get(mid)
    cp_mgr = bridge.checkpoint_managers.get(mid)
    if engine is None:
        return {
            "type": "mission_long_horizon_completion_evaluate_result",
            "success": False,
            "mission_id": mid,
            "error": f"Long-horizon mission '{mid}' not found.",
        }

    latest_cp = cp_mgr.get_latest_checkpoint() if cp_mgr else None
    milestones = engine.mission.plan.milestones.values() if engine.mission.plan else []
    all_completed = bool(milestones) and all(
        getattr(m.state, "value", str(m.state)) == "COMPLETED" for m in milestones
    )
    proof = engine.completion.evaluate(
        mission=engine.mission,
        primary_satisfied=bool(message.get("primary_satisfied", all_completed)),
        secondary_status=dict(message.get("secondary_status") or {}),
        all_milestones_completed=bool(message.get("all_milestones_completed", all_completed)),
        verification_passed=bool(message.get("verification_passed", True)),
        verification_coverage=float(message.get("verification_coverage", 1.0 if all_completed else 0.0)),
        architecture_stable=bool(message.get("architecture_stable", True)),
        contracts_intact=bool(message.get("contracts_intact", True)),
        behaviors_intact=bool(message.get("behaviors_intact", True)),
        security_safe=bool(message.get("security_safe", True)),
        unresolved_risks=[str(r) for r in (message.get("unresolved_risks") or [])],
        evidence_refs=[str(r) for r in (message.get("evidence_refs") or [])],
        final_checkpoint_id=str(
            message.get("final_checkpoint_id")
            or (latest_cp.checkpoint_id if latest_cp else "cp_none")
        ),
        residual_state=message.get("residual_state"),
    )
    bridge.persistence.save_mission(engine.mission)
    return {
        "type": "mission_long_horizon_completion_evaluate_result",
        "success": True,
        "mission_id": mid,
        "proof": proof.to_dict(),
    }


def _handle_quality_governance_baseline(message: dict[str, Any]) -> dict[str, Any]:
    bridge = _quality_bridge()
    mid = _mission_id(message)
    action = str(message.get("action") or "capture").lower()
    baseline = bridge.baseline_manager.get_baseline(mid)
    immutable = False
    if action in {"capture", "create"}:
        if baseline is None:
            baseline = bridge.capture_baseline(
                mid,
                context=message.get("context"),
                scope=str(message.get("scope") or "global"),
            )
        else:
            immutable = True
    return {
        "type": "mission_quality_governance_baseline_result",
        "mission_id": mid,
        "immutable": immutable,
        "baseline": baseline.to_dict() if baseline else None,
    }


def _handle_quality_governance_trend(message: dict[str, Any]) -> dict[str, Any]:
    bridge = _quality_bridge()
    mid = _mission_id(message)
    snapshots = []
    baseline = bridge.baseline_manager.get_baseline(mid)
    after = bridge.baseline_manager.get_after(mid)
    if baseline is not None:
        snapshots.append(baseline)
    if after is not None:
        snapshots.append(after)

    direction, details = bridge.trend_engine.analyze_trend(
        snapshots=snapshots,
        dimension_name=message.get("dimension"),
    )
    return {
        "type": "mission_quality_governance_trend_result",
        "mission_id": mid,
        "direction": direction.value,
        "details": details,
    }


MISSION_GOVERNANCE_DISPATCH_TABLE: dict[str, GovernanceHandler] = {
    "mission_loop_status": _handle_loop_status,
    "mission_loop_step": _handle_loop_step,
    "mission_loop_run": _handle_loop_run,
    "mission_loop_respond_human": _handle_loop_respond_human,
    "mission_decision_quality_status": _handle_decision_quality_status,
    "mission_policy_proposal_review": _handle_policy_proposal_review,
    "mission_policy_rollback": _handle_policy_rollback,
    "mission_experience_memory_status": _handle_experience_memory_status,
    "mission_experience_curate": _handle_experience_curate,
    "mission_semantic_graph_status": _handle_semantic_graph_status,
    "mission_contract_discovery_status": _handle_contract_discovery_status,
    "mission_contract_proposal_review": _handle_contract_proposal_review,
    "mission_contract_health_status": _handle_contract_health_status,
    "mission_contract_drift_review": _handle_contract_drift_review,
    "mission_contract_rollback": _handle_contract_rollback,
    "mission_polymorphic_schema_status": _handle_polymorphic_schema_status,
    "mission_polymorphic_variant_review": _handle_polymorphic_variant_review,
    "mission_polymorphic_compatibility_check": _handle_polymorphic_compatibility_check,
    "mission_contract_change_prediction": _handle_contract_change_prediction,
    "mission_contract_migration_plan": _handle_contract_migration_plan,
    "mission_contract_change_gate_action": _handle_contract_change_gate_action,
    "mission_build_contract_extraction_status": _handle_build_contract_extraction_status,
    "mission_dynamic_consumer_resolution": _handle_dynamic_consumer_resolution,
    "mission_build_contract_trigger_extract": _handle_build_contract_trigger_extract,
    "mission_behavioral_baseline_status": _handle_behavioral_baseline_status,
    "mission_behavioral_proof_status": _handle_behavioral_proof_status,
    "mission_behavioral_proof_trigger": _handle_behavioral_proof_trigger,
    "mission_long_horizon_checkpoint_create": _handle_long_horizon_checkpoint_create,
    "mission_long_horizon_recover": _handle_long_horizon_recover,
    "mission_long_horizon_adapt": _handle_long_horizon_adapt,
    "mission_long_horizon_completion_evaluate": _handle_long_horizon_completion_evaluate,
    "mission_quality_governance_baseline": _handle_quality_governance_baseline,
    "mission_quality_governance_trend": _handle_quality_governance_trend,
}

MISSION_GOVERNANCE_OPERATIONS = frozenset(MISSION_GOVERNANCE_DISPATCH_TABLE.keys())


def dispatch_mission_governance_operation(
    operation: str,
    message: dict[str, Any],
) -> dict[str, Any]:
    """Dispatch a mission governance operation to its concrete engine handler."""
    handler = MISSION_GOVERNANCE_DISPATCH_TABLE.get(operation)
    if handler is None:
        raise KeyError(f"Unsupported mission governance operation: {operation}")
    return handler(message)
