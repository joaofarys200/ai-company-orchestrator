"""
Phase 70 Unseen Release Scenarios Runner
Executes 15 diverse unseen scenarios to test edge cases, safety barriers, and policy gates:
1. healthy release
2. critical debt
3. security violation
4. contract break
5. behavior drift
6. performance regression
7. runtime unavailable
8. dependency unavailable
9. unsafe configuration
10. rollback unavailable
11. observability missing
12. browser regression
13. WebSocket failure
14. deployment unavailable
15. ambiguous release

Outputs to docs/phase70_unseen_scenarios.json.
"""

import os
import sys
import json
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.agents.release_readiness.bridge import ReleaseReadinessBridge
from backend.agents.release_readiness.models import ReleaseGateDecisionState


def run_unseen_scenarios():
    print("=" * 80)
    print("PHASE 70: 15 UNSEEN RELEASE SCENARIOS EVALUATION")
    print("=" * 80)

    bridge = ReleaseReadinessBridge()
    os.makedirs("docs", exist_ok=True)

    clean_base = {
        "quality_snapshot": {"overall_quality_score": 0.95, "dimensions": {"maintainability": 0.95}},
        "technical_debt_snapshot": {"critical_security_debt_count": 0, "critical_quality_debt_count": 0},
        "architecture_snapshot": {"forbidden_boundary_violations": 0, "unresolved_sccs": 0},
        "contract_snapshot": {"breaking_changes_count": 0, "migration_completed": True},
        "behavior_snapshot": {"invariants_violated_count": 0, "counterexamples_count": 0},
        "security_snapshot": {"secrets_detected_count": 0, "credential_exposure": False},
        "performance_baseline": {"latency_p95_ms": 10.0, "throughput_rps": 1000.0},
        "performance_current": {"latency_p95_ms": 10.1, "throughput_rps": 1010.0, "nature": "observed"},
        "runtime_evidence": {"process_started": True, "healthcheck_ok": True, "readiness_ok": True, "liveness_ok": True, "websocket_ok": True, "database_ok": True},
        "observability_data": {"structured_logs": True, "error_visibility": True, "health_signals": True, "request_tracing": True, "mission_telemetry": True},
        "dependency_data": {"dependencies_resolvable": True, "lockfile_consistent": True, "runtime_available": True},
        "configuration_data": {"missing_required_vars": [], "unsafe_defaults_detected": False, "secret_refs_valid": True},
        "rollback_data": {"snapshot_available": True, "artifacts_available": True, "checkpoint_verified": True}
    }

    scenarios = [
        # 1. Healthy release (with physical deployment available)
        ("unseen-01-healthy", "Healthy release with all checks passed", {}, True, ReleaseGateDecisionState.RELEASE_READY.value),
        # 2. Critical debt
        ("unseen-02-critical-debt", "Critical quality and security debt items unresolved", {"technical_debt_snapshot": {"critical_security_debt_count": 1}}, True, ReleaseGateDecisionState.BLOCKED.value),
        # 3. Security violation
        ("unseen-03-security-violation", "Plaintext API token leaked in git diff", {"security_snapshot": {"secrets_detected_count": 1, "credential_exposure": True}}, True, ReleaseGateDecisionState.BLOCKED.value),
        # 4. Contract break
        ("unseen-04-contract-break", "Unmigrated breaking contract change", {"contract_snapshot": {"breaking_changes_count": 1, "migration_completed": False}}, True, ReleaseGateDecisionState.BLOCKED.value),
        # 5. Behavior drift
        ("unseen-05-behavior-drift", "State machine transition drift detected against baseline", {"behavior_snapshot": {"invariants_violated_count": 0, "potential_drift_detected": True}}, True, ReleaseGateDecisionState.HUMAN_REVIEW.value),
        # 6. Performance regression
        ("unseen-06-performance-regression", "Severe latency spike (+80% p95)", {"performance_current": {"latency_p95_ms": 18.5, "nature": "observed"}}, True, ReleaseGateDecisionState.BLOCKED.value),
        # 7. Runtime unavailable
        ("unseen-07-runtime-unavailable", "Database unreachable from runtime pod", {"runtime_evidence": {"process_started": True, "healthcheck_ok": False, "database_ok": False}}, True, ReleaseGateDecisionState.BLOCKED.value),
        # 8. Dependency unavailable
        ("unseen-08-dependency-unavailable", "Lockfile checksum mismatch with manifest", {"dependency_data": {"lockfile_consistent": False}}, True, ReleaseGateDecisionState.BLOCKED.value),
        # 9. Unsafe configuration
        ("unseen-09-unsafe-configuration", "DEBUG=true and secret plaintext in production config", {"configuration_data": {"debug_mode_in_production": True, "unsafe_defaults_detected": True}}, True, ReleaseGateDecisionState.BLOCKED.value),
        # 10. Rollback unavailable
        ("unseen-10-rollback-unavailable", "Recovery checkpoint unverified prior to migration", {"rollback_data": {"checkpoint_verified": False, "snapshot_available": False}}, True, ReleaseGateDecisionState.BLOCKED.value),
        # 11. Observability missing
        ("unseen-11-observability-missing", "Zero structured logs and no health telemetry", {"observability_data": {"structured_logs": False, "error_visibility": False, "health_signals": False}}, True, ReleaseGateDecisionState.INSUFFICIENT_EVIDENCE.value),
        # 12. Browser regression
        ("unseen-12-browser-regression", "Browser render time exceeds threshold (+75%)", {"performance_current": {"browser_render_ms": 35.0, "latency_p95_ms": 10.0, "nature": "observed"}, "performance_baseline": {"browser_render_ms": 18.0, "latency_p95_ms": 10.0}}, True, ReleaseGateDecisionState.BLOCKED.value),
        # 13. WebSocket failure
        ("unseen-13-websocket-failure", "WebSocket connection fails handshake", {"runtime_evidence": {"process_started": True, "healthcheck_ok": True, "websocket_ok": False}}, True, ReleaseGateDecisionState.HUMAN_REVIEW.value),
        # 14. Deployment unavailable
        ("unseen-14-deployment-unavailable", "Valid candidate but no physical deploy target", {}, False, ReleaseGateDecisionState.DEPLOYMENT_NOT_AVAILABLE.value),
        # 15. Ambiguous release
        ("unseen-15-ambiguous-release", "Elevated uncertainty bound (0.45)", {"quality_snapshot": {"overall_quality_score": 0.88, "quality_uncertainty": 0.45}, "unresolved_unknown_count": 2}, True, ReleaseGateDecisionState.HUMAN_REVIEW.value),
    ]

    results = []

    for sid, desc, overrides, deploy_avail, exp_state in scenarios:
        print(f"\nScenario [{sid}]: {desc}")
        # Merge clean base with overrides
        inputs = json.loads(json.dumps(clean_base))
        for k, v in overrides.items():
            if isinstance(v, dict) and k in inputs:
                inputs[k].update(v)
            else:
                inputs[k] = v

        decision = bridge.evaluate_readiness(
            release_id=sid,
            evaluation_inputs=inputs,
            deployment_available=deploy_avail
        )

        entry = {
            "scenario_id": sid,
            "description": desc,
            "expected_state": exp_state,
            "actual_state": decision["state"],
            "allowed_to_release": decision["allowed_to_release"],
            "blockers_count": len(decision["blockers"]),
            "blockers": decision["blockers"],
            "risk_vector": decision["risk_vector"],
            "human_review_required": bool(decision.get("human_review_ticket")),
            "provenance_hash": decision["provenance_hash"],
            "evaluated_at": decision["evaluated_at"]
        }
        results.append(entry)

        print(f"  Outcome: {decision['state']} (Expected: {exp_state}) | Blockers: {len(decision['blockers'])}")
        assert decision["state"] == exp_state, f"Mismatch on {sid}: {decision['state']} != {exp_state}"

    out_file = os.path.join("docs", "phase70_unseen_scenarios.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "suite": "Phase 70 Unseen Release Scenarios",
                "scenarios_count": len(results),
                "all_passed": True,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "scenarios": results
            },
            f,
            indent=2
        )

    print(f"\n[SUCCESS] All 15 unseen scenarios successfully evaluated and persisted to {out_file}")


if __name__ == "__main__":
    run_unseen_scenarios()
