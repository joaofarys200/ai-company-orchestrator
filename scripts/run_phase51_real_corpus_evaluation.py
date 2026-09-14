"""
JARVIS OS — Phase 51: Behavioral Proof Coverage & Scenario Exploration
Real Corpus Evaluation: Evaluates authentic contracts across the JARVIS OS repository.
Generates:
- docs/phase51_scenarios.json
- docs/phase51_coverage.json
- docs/phase51_counterexamples.json
- docs/phase51_proofs.json
- docs/phase51_verification_ledger.json
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.behavioral_proof_exploration.bridge import BehavioralProofExplorationBridge
from agents.behavioral_proof_exploration.models import (
    CoverageThresholdPolicy,
    ExplorationBudget,
    ProofResult,
)


def run_real_corpus_evaluation() -> None:
    print("=== JARVIS OS Phase 51: Real Corpus Evaluation ===")

    bridge = BehavioralProofExplorationBridge()

    # Real contracts from JARVIS OS codebase
    corpus_contracts = [
        {
            "migration_id": "mig_real_01_list_missions",
            "contract_id": "listMissionsEndpoint",
            "before_version": "v1.9.0",
            "after_version": "v2.0.0",
            "schema": {
                "type": "object",
                "required": ["limit", "offset"],
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    "offset": {"type": "integer", "minimum": 0},
                    "status_filter": {"type": "string", "enum": ["ACTIVE", "PAUSED", "COMPLETED", "FAILED"]},
                    "include_traces": {"type": "boolean"},
                },
            },
            "consumers": ["frontend-mission-control", "cli-agent-runner", "audit-service"],
            "policy": CoverageThresholdPolicy.STANDARD,
            "is_economic": False,
            "polymorphic_variants": ["STANDARD_QUERY", "PAGINATED_STREAM"],
            "uncertain_consumers": [],
        },
        {
            "migration_id": "mig_real_02_payment_clearing",
            "contract_id": "economicDisbursementContract",
            "before_version": "v3.1.0",
            "after_version": "v3.2.0",
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
            "policy": CoverageThresholdPolicy.STRICT,
            "is_economic": True,
            "polymorphic_variants": ["INSTANT", "BATCH"],
            "uncertain_consumers": [],
        },
        {
            "migration_id": "mig_real_03_auth_jwt_sentinel",
            "contract_id": "securityAuthSentinelVerify",
            "before_version": "v2.5.0",
            "after_version": "v2.6.0",
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
            "policy": CoverageThresholdPolicy.STRICT,
            "is_economic": False,
            "uncertain_consumers": [],
        },
        {
            "migration_id": "mig_real_04_dynamic_unresolved",
            "contract_id": "runtimeDynamicPluginConsumer",
            "before_version": "v1.0.0",
            "after_version": "v1.1.0",
            "schema": {
                "type": "object",
                "required": ["plugin_id"],
                "properties": {
                    "plugin_id": {"type": "string"},
                    "config_payload": {"type": "object"},
                },
            },
            "consumers": ["plugin-loader"],
            "policy": CoverageThresholdPolicy.STANDARD,
            "is_economic": False,
            "uncertain_consumers": ["UNCERTAIN_EXTERNAL_PLUGIN_RUNNER"],
        },
        {
            "migration_id": "mig_real_05_breaking_discount",
            "contract_id": "orderCalculationContract",
            "before_version": "v1.2.0",
            "after_version": "v2.0.0",
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
            "policy": CoverageThresholdPolicy.STANDARD,
            "is_economic": False,
            "uncertain_consumers": [],
            # Inject subtle bug in after_handler triggering a real counterexample
            "simulate_bug": True,
        },
    ]

    all_scenarios_data = []
    all_coverage_data = []
    all_counterexamples_data = []
    all_proofs_data = []
    verification_ledger = []

    os.makedirs("docs", exist_ok=True)

    for spec in corpus_contracts:
        m_id = spec["migration_id"]
        c_id = spec["contract_id"]
        print(f"\nEvaluating Real Contract: {c_id} ({m_id})...")

        t_start = time.perf_counter()

        def make_after_handler(has_bug: bool):
            if not has_bug:
                return None
            def buggy(payload: dict) -> dict:
                # Bug: when discount_rate < 0, after version throws 422 instead of clamping to 0
                dr = payload.get("discount_rate")
                if dr is not None and isinstance(dr, (int, float)) and dr < 0:
                    return {"status_code": 422, "output": {"error": "UNPROCESSABLE_ENTITY"}}
                return {"status_code": 200, "output": {"id": payload.get("order_id"), "status": "processed"}}
            return buggy

        proof = bridge.run_exploration_proof(
            migration_id=m_id,
            contract_id=c_id,
            before_version=spec["before_version"],
            after_version=spec["after_version"],
            schema=spec["schema"],
            known_consumers=spec["consumers"],
            coverage_policy=spec["policy"],
            is_economic=spec["is_economic"],
            polymorphic_variants=spec.get("polymorphic_variants"),
            dynamic_consumer_uncertainties=spec.get("uncertain_consumers"),
            after_handler=make_after_handler(spec.get("simulate_bug", False)),
            budget=ExplorationBudget(max_scenarios=50),
        )

        elapsed_ms = (time.perf_counter() - t_start) * 1000.0

        print(f"  Result: {proof.result.value} | Gate: {proof.gate_decision.value} | Coverage: {proof.coverage.overall_percentage*100:.1f}% | Time: {elapsed_ms:.1f}ms")

        # Record into datasets
        proof_dict = proof.to_dict()
        all_proofs_data.append(proof_dict)
        all_coverage_data.append(proof.coverage.to_dict())

        # Collect scenarios
        scens = bridge.index.list_scenarios(contract_id=c_id) if hasattr(bridge.index, "list_scenarios") else []
        for s in scens:
            all_scenarios_data.append(s.to_dict())

        # Collect counterexamples
        for cx in proof.counterexamples:
            all_counterexamples_data.append(cx.to_dict())
        for scx in proof.shrunk_counterexamples:
            all_counterexamples_data.append(scx.to_dict())

        verification_ledger.append({
            "migration_id": m_id,
            "contract_id": c_id,
            "scope_id": proof.scope.scope_id,
            "proof_result": proof.result.value,
            "gate_decision": proof.gate_decision.value,
            "coverage_percentage": round(proof.coverage.overall_percentage * 100, 2),
            "counterexamples_count": len(proof.counterexamples),
            "shrunk_counterexamples_count": len(proof.shrunk_counterexamples),
            "latency_ms": round(elapsed_ms, 2),
            "proof_hash": proof.proof_hash,
            "timestamp": time.time(),
        })

    # Save artifacts
    with open("docs/phase51_scenarios.json", "w", encoding="utf-8") as f:
        json.dump(all_scenarios_data, f, indent=2)
    with open("docs/phase51_coverage.json", "w", encoding="utf-8") as f:
        json.dump(all_coverage_data, f, indent=2)
    with open("docs/phase51_counterexamples.json", "w", encoding="utf-8") as f:
        json.dump(all_counterexamples_data, f, indent=2)
    with open("docs/phase51_proofs.json", "w", encoding="utf-8") as f:
        json.dump(all_proofs_data, f, indent=2)
    with open("docs/phase51_verification_ledger.json", "w", encoding="utf-8") as f:
        json.dump(verification_ledger, f, indent=2)

    print("\nSuccessfully generated all Phase 51 evaluation artifacts in docs/")


if __name__ == "__main__":
    run_real_corpus_evaluation()
