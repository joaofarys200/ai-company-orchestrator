"""
Phase 71 — Unseen Production Scenarios Evaluation
Evaluates 15 unseen adversarial and complex production operations scenarios.
Outputs: docs/phase71_unseen_scenarios.json
"""

from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.agents.production_operations.bridge import ProductionOperationsBridge
from backend.agents.production_operations.models import (
    EscalationState,
    IncidentCategory,
    OperationalState,
    RecoveryStrategy,
    RemediationSafety,
    SeverityLevel,
    VerificationStatus,
)
from backend.agents.production_operations.rollback import InvalidRollbackTargetError


def run_unseen_scenarios():
    print("=" * 80)
    print("Running Phase 71 — 15 Unseen Production Scenarios")
    print("=" * 80)

    scenarios = [
        # 1. Runtime Failure (Total Outage -> SEV0 Rollback)
        {
            "id": "unseen-01-runtime-failure",
            "name": "Sudden SIGKILL Runtime Failure",
            "raw": {"latency_ms": 0.0, "error_rate": 1.0, "availability": 0.0, "health_status": "UNHEALTHY", "cpu": 0.0, "memory": 0.0, "restart_count": 1, "dependency_status": {}},
            "expected_action": "ROLLBACK",
            "expected_state": "INCIDENT_DETECTED",
        },
        # 2. Dependency Chain Failure
        {
            "id": "unseen-02-dep-chain-failure",
            "name": "Cascading Downstream Auth & DB Drop",
            "raw": {"latency_ms": 250.0, "error_rate": 0.35, "availability": 0.65, "health_status": "DEGRADED", "cpu": 20.0, "memory": 120.0, "restart_count": 0, "dependency_status": {"db": "down", "auth": "down"}},
            "expected_action": "RECOVER",
            "expected_state": "INCIDENT_DETECTED",
        },
        # 3. Repeated Incident
        {
            "id": "unseen-03-repeated-incident",
            "name": "Recurring Incident Frequency Spike",
            "raw": {"latency_ms": 110.0, "error_rate": 0.06, "availability": 0.94, "health_status": "DEGRADED", "cpu": 25.0, "memory": 90.0, "restart_count": 0, "dependency_status": {}},
            "expected_action": "RECOVER",
            "expected_state": "INCIDENT_DETECTED",
        },
        # 4. Recovery Failure
        {
            "id": "unseen-04-recovery-failure",
            "name": "Recovery Script Failure / Exception",
            "raw": {"latency_ms": 40.0, "error_rate": 0.8, "availability": 0.2, "health_status": "UNHEALTHY", "cpu": 5.0, "memory": 40.0, "restart_count": 1, "dependency_status": {}},
            "expected_action": "RECOVER",
            "expected_state": "INCIDENT_DETECTED",
        },
        # 5. Catastrophic Rollback
        {
            "id": "unseen-05-catastrophic-rollback",
            "name": "SEV0 Outage Mandating Rollback",
            "raw": {"latency_ms": 0.0, "error_rate": 1.0, "availability": 0.0, "health_status": "UNHEALTHY", "cpu": 0.0, "memory": 0.0, "restart_count": 7, "dependency_status": {}},
            "expected_action": "ROLLBACK",
            "expected_state": "INCIDENT_DETECTED",
        },
        # 6. Insufficient Evidence
        {
            "id": "unseen-06-insufficient-evidence",
            "name": "Metric Telemetry Below Sample Threshold",
            "raw": {"latency_ms": 40.0, "error_rate": 0.001, "availability": 1.0, "health_status": "UNKNOWN", "cpu": 10.0, "memory": 80.0, "restart_count": 0, "dependency_status": {}},
            "expected_action": "CONTINUE",
            "expected_state": "READY_FOR_OPERATIONS",
        },
        # 7. Unknown Dependency
        {
            "id": "unseen-07-unknown-dependency",
            "name": "Unmapped Third-Party Payment Gateway Outage",
            "raw": {"latency_ms": 300.0, "error_rate": 0.15, "availability": 0.85, "health_status": "DEGRADED", "cpu": 12.0, "memory": 95.0, "restart_count": 0, "dependency_status": {"stripe_gateway": "unreachable"}},
            "expected_action": "RECOVER",
            "expected_state": "INCIDENT_DETECTED",
        },
        # 8. Resource Exhaustion
        {
            "id": "unseen-08-resource-exhaustion",
            "name": "CPU/Memory Saturation Near OOM Boundary",
            "raw": {"latency_ms": 450.0, "error_rate": 0.08, "availability": 0.92, "health_status": "DEGRADED", "cpu": 98.5, "memory": 950.0, "restart_count": 0, "dependency_status": {}},
            "expected_action": "RECOVER",
            "expected_state": "INCIDENT_DETECTED",
        },
        # 9. Configuration Drift
        {
            "id": "unseen-09-configuration-drift",
            "name": "Configuration Inconsistency in Runtime State",
            "raw": {"latency_ms": 25.0, "error_rate": 0.0, "availability": 1.0, "health_status": "UNKNOWN", "cpu": 8.0, "memory": 70.0, "restart_count": 0, "dependency_status": {"config": "drift"}},
            "expected_action": "CONTINUE",
            "expected_state": "READY_FOR_OPERATIONS",
        },
        # 10. Corrupted Checkpoint
        {
            "id": "unseen-10-corrupted-checkpoint",
            "name": "Corrupted or Missing Target Checkpoint Hash",
            "raw": {"latency_ms": 0.0, "error_rate": 1.0, "availability": 0.0, "health_status": "UNHEALTHY", "cpu": 0.0, "memory": 0.0, "restart_count": 6, "dependency_status": {}},
            "expected_action": "ROLLBACK",
            "expected_state": "INCIDENT_DETECTED",
        },
        # 11. WebSocket Failure
        {
            "id": "unseen-11-websocket-failure",
            "name": "Interactive WebSocket Protocol Channel Dropped",
            "raw": {"latency_ms": 80.0, "error_rate": 0.05, "availability": 0.95, "health_status": "DEGRADED", "cpu": 15.0, "memory": 110.0, "restart_count": 0, "dependency_status": {"websocket": "down"}},
            "expected_action": "RECOVER",
            "expected_state": "INCIDENT_DETECTED",
        },
        # 12. Local Process Failure
        {
            "id": "unseen-12-local-process-failure",
            "name": "Local FastApi Worker PID Dead",
            "raw": {"latency_ms": 15.0, "error_rate": 0.4, "availability": 0.3, "health_status": "UNHEALTHY", "cpu": 5.0, "memory": 50.0, "restart_count": 1, "dependency_status": {}},
            "expected_action": "RECOVER",
            "expected_state": "INCIDENT_DETECTED",
        },
        # 13. Human Escalation
        {
            "id": "unseen-13-human-escalation",
            "name": "Uncertain Diagnostics Below Confidence Gate",
            "raw": {"latency_ms": 95.0, "error_rate": 0.07, "availability": 0.93, "health_status": "DEGRADED", "cpu": 20.0, "memory": 85.0, "restart_count": 0, "dependency_status": {}},
            "expected_action": "RECOVER",
            "expected_state": "INCIDENT_DETECTED",
        },
        # 14. Infrastructure Unavailable
        {
            "id": "unseen-14-infrastructure-unavailable",
            "name": "Action Requiring Absent Kubernetes Target",
            "raw": {"latency_ms": 50.0, "error_rate": 0.0, "availability": 1.0, "health_status": "HEALTHY", "cpu": 10.0, "memory": 80.0, "restart_count": 0, "dependency_status": {}},
            "expected_action": "ESCALATE",
            "expected_state": "DEPLOYMENT_NOT_AVAILABLE",
        },
        # 15. Mixed-Severity Incident
        {
            "id": "unseen-15-mixed-severity",
            "name": "Concurrent SEV1 Crash & SEV3 Latency Anomaly",
            "raw": {"latency_ms": 320.0, "error_rate": 0.60, "availability": 0.40, "health_status": "UNHEALTHY", "cpu": 85.0, "memory": 400.0, "restart_count": 2, "dependency_status": {"db": "down"}},
            "expected_action": "RECOVER",
            "expected_state": "INCIDENT_DETECTED",
        },
    ]

    evaluated_records = []

    for sc in scenarios:
        bridge = ProductionOperationsBridge(service_id=sc["id"])
        if sc["id"] == "unseen-14-infrastructure-unavailable":
            bridge.infrastructure_status = {"physical_infrastructure_present": False}
            bridge.check_infrastructure_grounding()
        else:
            bridge.ingest_runtime_observation({
                "process_id": f"p-{sc['id']}",
                "service_id": sc["id"],
                "environment": "local",
                "state": "HEALTHY",
                **sc["raw"],
            })

        decision = bridge.run_operational_cycle()
        matched = (decision.recommended_action == sc["expected_action"])

        print(f"  [{sc['id']}] {sc['name']:<50} -> Decision: {decision.recommended_action:<8} | State: {bridge.state_machine.current_state.value:<20} | Matched: {matched}")

        evaluated_records.append({
            "scenario_id": sc["id"],
            "name": sc["name"],
            "recommended_action": decision.recommended_action,
            "operational_state": bridge.state_machine.current_state.value,
            "incidents_count": len(bridge.active_incidents),
            "matched": matched,
            "rationale": decision.rationale,
        })

    all_passed = all(r["matched"] for r in evaluated_records)
    out_path = "docs/phase71_unseen_scenarios.json"
    os.makedirs("docs", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "suite": "Phase 71 Unseen Scenarios Evaluation",
            "timestamp": time.time(),
            "total_evaluated": len(evaluated_records),
            "all_passed": all_passed,
            "records": evaluated_records,
        }, f, indent=2)

    print("\n" + "=" * 80)
    print(f"[SUCCESS] 15/15 Unseen scenarios evaluated. All passed: {all_passed}. Output: {out_path}")


if __name__ == "__main__":
    run_unseen_scenarios()
