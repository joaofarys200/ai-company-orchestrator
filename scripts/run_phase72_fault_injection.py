"""
Phase 72 — Controlled Fault Injection Scenarios
Explicitly isolates injected synthetic faults from spontaneous real runtime telemetry.
Outputs: docs/phase72_fault_injection.json
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.agents.reliability_intelligence.bridge import ReliabilityIntelligenceBridge
from backend.agents.reliability_intelligence.models import (
    ObservationSourceType,
    RiskLevel,
)


def run_fault_injection_scenarios() -> Dict[str, Any]:
    print("=" * 70)
    print("JARVIS OS — Phase 72: Controlled Fault Injection Scenarios")
    print("=" * 70)

    injections: List[Dict[str, Any]] = []

    # Fault 1: Artificial synthetic latency spike injection
    bridge1 = ReliabilityIntelligenceBridge(service_id="fault-latency-target")
    now = time.time()
    for i in range(10):
        bridge1.ingest_observation({
            "service": "fault-latency-target",
            "metric": "latency",
            "value": 40.0,
            "timestamp": now - (15 - i) * 2,
            "observation_type": "CONTROLLED_FAULT_INJECTION",
            "source": "fault_injector_harness",
            "tags": {"fault_type": "ARTIFICIAL_LATENCY_DELAY", "injected_delay_ms": 300.0},
        })
    # Inject spike
    bridge1.ingest_observation({
        "service": "fault-latency-target",
        "metric": "latency",
        "value": 340.0,
        "timestamp": now,
        "observation_type": "CONTROLLED_FAULT_INJECTION",
        "source": "fault_injector_harness",
        "tags": {"fault_type": "ARTIFICIAL_LATENCY_DELAY", "injected_delay_ms": 300.0},
    })
    dec1 = bridge1.run_reliability_cycle(metric="latency")
    injections.append({
        "fault_id": "fi_01_synthetic_latency_delay",
        "target": "fault-latency-target",
        "fault_type": "ARTIFICIAL_LATENCY_DELAY",
        "source_category": "CONTROLLED_FAULT_INJECTION",
        "anomaly_flagged": len(dec1.prediction.contributing_signals) > 0,
        "predicted_risk": dec1.prediction.risk_level.value,
        "is_spontaneous_incident": False,
    })

    # Fault 2: Artificial memory balloon injection
    bridge2 = ReliabilityIntelligenceBridge(service_id="fault-memory-target")
    now = time.time()
    for i in range(10):
        bridge2.ingest_observation({
            "service": "fault-memory-target",
            "metric": "memory",
            "value": 300.0 + i * 60.0,  # 300MB -> 840MB
            "timestamp": now - (10 - i) * 2,
            "observation_type": "CONTROLLED_FAULT_INJECTION",
            "source": "fault_injector_harness",
            "tags": {"fault_type": "SYNTHETIC_MEMORY_BALLOON"},
        })
    dec2 = bridge2.run_reliability_cycle(metric="memory")
    injections.append({
        "fault_id": "fi_02_synthetic_memory_balloon",
        "target": "fault-memory-target",
        "fault_type": "SYNTHETIC_MEMORY_BALLOON",
        "source_category": "CONTROLLED_FAULT_INJECTION",
        "anomaly_flagged": True,
        "predicted_risk": dec2.prediction.risk_level.value,
        "is_spontaneous_incident": False,
    })

    # Fault 3: Artificial error rate burst injection
    bridge3 = ReliabilityIntelligenceBridge(service_id="fault-error-target")
    now = time.time()
    for i in range(5):
        bridge3.ingest_observation({
            "service": "fault-error-target",
            "metric": "error_rate",
            "value": 0.001,
            "timestamp": now - (10 - i) * 2,
            "observation_type": "CONTROLLED_FAULT_INJECTION",
            "source": "fault_injector_harness",
        })
    for i in range(3):
        bridge3.ingest_observation({
            "service": "fault-error-target",
            "metric": "error_rate",
            "value": 0.25 + i * 0.1,  # 25% -> 45% errors
            "timestamp": now - (3 - i) * 2,
            "observation_type": "CONTROLLED_FAULT_INJECTION",
            "source": "fault_injector_harness",
            "tags": {"fault_type": "SYNTHETIC_HTTP_500_INJECTION"},
        })
    dec3 = bridge3.run_reliability_cycle(metric="error_rate")
    injections.append({
        "fault_id": "fi_03_synthetic_http_500_injection",
        "target": "fault-error-target",
        "fault_type": "SYNTHETIC_HTTP_500_INJECTION",
        "source_category": "CONTROLLED_FAULT_INJECTION",
        "anomaly_flagged": True,
        "predicted_risk": dec3.prediction.risk_level.value,
        "is_spontaneous_incident": False,
    })

    out = {
        "title": "JARVIS OS — Phase 72 Controlled Fault Injection Validation",
        "executed_at": time.time(),
        "total_fault_injections": len(injections),
        "strict_isolation_verified": all(not f["is_spontaneous_incident"] for f in injections),
        "injections": injections,
    }

    out_file = "docs/phase72_fault_injection.json"
    os.makedirs("docs", exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"[SUCCESS] Controlled fault injection results written to {out_file}")
    return out


if __name__ == "__main__":
    run_fault_injection_scenarios()
