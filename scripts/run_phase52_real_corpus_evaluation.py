"""
JARVIS OS — Phase 52: Risk-Directed Behavioral Exploration & Adaptive Proof Search
Real Corpus Evaluation: Evaluates authentic contracts across the JARVIS OS repository.
Generates:
- docs/phase52_risk_scores.json
- docs/phase52_scenario_rankings.json
- docs/phase52_coverage.json
- docs/phase52_exploration.json
- docs/phase52_counterexamples.json
- docs/phase52_verification_ledger.json
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.risk_directed_exploration.bridge import RiskDirectedExplorationBridge
from agents.risk_directed_exploration.models import ExplorationPolicy


def run_real_corpus_evaluation() -> None:
    print("=== JARVIS OS Phase 52: Real Corpus Evaluation ===")

    bridge = RiskDirectedExplorationBridge()

    corpus_contracts = [
        {
            "migration_id": "mig_real_01_list_missions",
            "contract_id": "listMissionsEndpoint",
            "schema": {
                "type": "object",
                "required": ["limit", "offset"],
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    "offset": {"type": "integer", "minimum": 0},
                    "status_filter": {"type": "string", "enum": ["ACTIVE", "PAUSED", "COMPLETED", "FAILED"]},
                },
            },
            "consumers": ["frontend-mission-control", "cli-agent-runner", "audit-service"],
            "policy": ExplorationPolicy.STANDARD,
            "is_economic": False,
            "is_security": False,
            "impact": "MEDIUM",
            "uncertain_consumers": [],
        },
        {
            "migration_id": "mig_real_02_payment_clearing",
            "contract_id": "economicDisbursementContract",
            "schema": {
                "type": "object",
                "required": ["id", "amount", "currency", "beneficiary"],
                "properties": {
                    "id": {"type": "string"},
                    "amount": {"type": "number", "minimum": 0.01},
                    "currency": {"type": "string", "enum": ["EUR", "USD", "GBP"]},
                    "beneficiary": {"type": "string"},
                    "settlement_type": {"type": "string", "enum": ["INSTANT", "BATCH"]},
                },
            },
            "consumers": ["treasury-service", "ledger-sync"],
            "policy": ExplorationPolicy.ECONOMIC_CRITICAL,
            "is_economic": True,
            "is_security": False,
            "impact": "CRITICAL",
            "uncertain_consumers": [],
        },
        {
            "migration_id": "mig_real_03_auth_jwt_sentinel",
            "contract_id": "securityAuthSentinelVerify",
            "schema": {
                "type": "object",
                "required": ["token", "client_id"],
                "properties": {
                    "token": {"type": "string"},
                    "client_id": {"type": "string"},
                    "required_role": {"type": "string", "enum": ["OPERATOR", "AGENT", "ADMIN"]},
                },
            },
            "consumers": ["api-gateway", "websocket-server"],
            "policy": ExplorationPolicy.SECURITY_CRITICAL,
            "is_economic": False,
            "is_security": True,
            "impact": "HIGH",
            "uncertain_consumers": [],
        },
        {
            "migration_id": "mig_real_04_dynamic_unresolved",
            "contract_id": "runtimeDynamicPluginConsumer",
            "schema": {
                "type": "object",
                "required": ["plugin_id"],
                "properties": {
                    "plugin_id": {"type": "string"},
                    "config_payload": {"type": "object"},
                },
            },
            "consumers": ["plugin-loader"],
            "policy": ExplorationPolicy.STANDARD,
            "is_economic": False,
            "is_security": False,
            "impact": "LOW",
            "uncertain_consumers": ["UNCERTAIN_EXTERNAL_PLUGIN_RUNNER"],
        },
        {
            "migration_id": "mig_real_05_breaking_discount",
            "contract_id": "orderCalculationContract",
            "schema": {
                "type": "object",
                "required": ["order_id", "subtotal", "discount_rate"],
                "properties": {
                    "order_id": {"type": "string"},
                    "subtotal": {"type": "number"},
                    "discount_rate": {"type": "number"},
                },
            },
            "consumers": ["checkout-ui"],
            "policy": ExplorationPolicy.STANDARD,
            "is_economic": False,
            "is_security": False,
            "impact": "MEDIUM",
            "uncertain_consumers": [],
            "simulate_bug": True,
        },
    ]

    all_risk_scores = []
    all_rankings = []
    all_coverage = []
    all_exploration = []
    all_counterexamples = []
    verification_ledger = []

    os.makedirs("docs", exist_ok=True)

    for spec in corpus_contracts:
        m_id = spec["migration_id"]
        c_id = spec["contract_id"]
        print(f"\nEvaluating Contract: {c_id} ({m_id})...")

        t0 = time.perf_counter()

        def make_after_handler(has_bug: bool):
            if not has_bug:
                return None
            def buggy(payload: dict) -> dict:
                dr = payload.get("discount_rate")
                if dr is not None and isinstance(dr, (int, float)) and dr < 0:
                    return {"status_code": 422, "output": {"error": "UNPROCESSABLE_ENTITY"}}
                return {"status_code": 200, "output": {"id": payload.get("order_id"), "status": "processed"}}
            return buggy

        proof = bridge.run_risk_directed_proof(
            migration_id=m_id,
            contract_id=c_id,
            schema=spec["schema"],
            known_consumers=spec["consumers"],
            policy=spec["policy"],
            predictive_impact_level=spec["impact"],
            is_economic=spec["is_economic"],
            is_security_critical=spec["is_security"],
            dynamic_consumer_uncertainties=spec["uncertain_consumers"],
            after_handler=make_after_handler(spec.get("simulate_bug", False)),
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        print(f"  Result: {proof.result.value} | Gate: {proof.gate_decision.value} | Executed: {proof.scenarios_executed}/{proof.scenarios_ranked} (Skipped {proof.scenarios_skipped}) | Time: {elapsed_ms:.1f}ms")

        all_risk_scores.append({
            "migration_id": m_id,
            "contract_id": c_id,
            "initial_risk": proof.initial_risk.to_dict(),
            "final_risk": proof.final_risk.to_dict(),
            "initial_uncertainty": proof.initial_uncertainty.to_dict(),
            "final_uncertainty": proof.final_uncertainty.to_dict(),
        })

        # Rankings
        rankings = bridge.index.get_rankings(c_id)
        all_rankings.append({
            "contract_id": c_id,
            "migration_id": m_id,
            "policy": spec["policy"].value,
            "rankings": [r.to_dict() for r in rankings] if rankings else [],
        })

        all_coverage.append(proof.coverage.to_dict() if proof.coverage else {})
        all_exploration.append({
            "migration_id": m_id,
            "contract_id": c_id,
            "policy": spec["policy"].value,
            "budget": proof.budget.to_dict(),
            "scenarios_ranked": proof.scenarios_ranked,
            "scenarios_executed": proof.scenarios_executed,
            "scenarios_skipped": proof.scenarios_skipped,
            "early_stopped": proof.early_stopped,
            "early_stop_reason": proof.early_stop_reason,
            "scenario_efficiency": proof.scenario_efficiency,
        })

        for cx in proof.counterexamples:
            all_counterexamples.append(cx.to_dict())
        for scx in proof.shrunk_counterexamples:
            all_counterexamples.append(scx.to_dict())

        verification_ledger.append({
            "migration_id": m_id,
            "contract_id": c_id,
            "policy": spec["policy"].value,
            "proof_result": proof.result.value,
            "gate_decision": proof.gate_decision.value,
            "initial_risk_score": proof.initial_risk.risk_score,
            "final_risk_score": proof.final_risk.risk_score,
            "scenarios_executed": proof.scenarios_executed,
            "scenarios_skipped": proof.scenarios_skipped,
            "coverage_percentage": round(proof.coverage.overall_percentage * 100, 2) if proof.coverage else 0.0,
            "counterexamples_count": len(proof.counterexamples),
            "scenario_efficiency": proof.scenario_efficiency,
            "duration_ms": round(elapsed_ms, 2),
            "proof_hash": proof.proof_hash,
            "timestamp": time.time(),
        })

    with open("docs/phase52_risk_scores.json", "w", encoding="utf-8") as f:
        json.dump(all_risk_scores, f, indent=2)
    with open("docs/phase52_scenario_rankings.json", "w", encoding="utf-8") as f:
        json.dump(all_rankings, f, indent=2)
    with open("docs/phase52_coverage.json", "w", encoding="utf-8") as f:
        json.dump(all_coverage, f, indent=2)
    with open("docs/phase52_exploration.json", "w", encoding="utf-8") as f:
        json.dump(all_exploration, f, indent=2)
    with open("docs/phase52_counterexamples.json", "w", encoding="utf-8") as f:
        json.dump(all_counterexamples, f, indent=2)
    with open("docs/phase52_verification_ledger.json", "w", encoding="utf-8") as f:
        json.dump(verification_ledger, f, indent=2)

    print("\nSuccessfully generated all Phase 52 real corpus artifacts in docs/")


if __name__ == "__main__":
    run_real_corpus_evaluation()
