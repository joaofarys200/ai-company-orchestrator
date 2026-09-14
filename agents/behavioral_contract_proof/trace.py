"""
JARVIS OS — Phase 50: Behavioral Contract Preservation & Migration Proof
Runtime Trace Collector & Provenance Verification.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional

from agents.behavioral_contract_proof.models import BehavioralStageExecution, RuntimeTrace


def compute_trace_hash(trace: RuntimeTrace) -> str:
    """
    Computes cryptographic SHA-256 hash for a runtime trace.
    Includes input, output, status, stages, events, side effects, and economic effects.
    """
    payload = {
        "source": trace.source,
        "mission_id": trace.mission_id,
        "consumer_id": trace.consumer_id,
        "contract_id": trace.contract_id,
        "operation": trace.operation,
        "input_payload": trace.input_payload,
        "output_payload": trace.output_payload,
        "status_code": trace.status_code,
        "stages": [s.to_dict() for s in trace.stages],
        "side_effects": trace.side_effects,
        "events": trace.events,
        "economic_effects": trace.economic_effects,
        "authorization_state": trace.authorization_state,
        "parent_trace_hash": trace.parent_trace_hash,
        "environment": trace.environment,
        "build_hash": trace.build_hash,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class RuntimeTraceCollector:
    """
    Manages recording and verification of runtime traces.
    """

    def __init__(self) -> None:
        self._traces: Dict[str, RuntimeTrace] = {}

    def record_trace(
        self,
        mission_id: str,
        consumer_id: str,
        contract_id: str,
        operation: str,
        input_payload: Dict[str, Any],
        output_payload: Dict[str, Any],
        status_code: int,
        stages: Optional[List[BehavioralStageExecution]] = None,
        side_effects: Optional[List[Dict[str, Any]]] = None,
        events: Optional[List[Dict[str, Any]]] = None,
        economic_effects: Optional[List[Dict[str, Any]]] = None,
        authorization_state: Optional[Dict[str, Any]] = None,
        parent_trace_hash: Optional[str] = None,
        environment: str = "production",
        build_hash: str = "",
        source: str = "runtime_observation",
        trace_id: Optional[str] = None,
    ) -> RuntimeTrace:
        """Records a new execution trace and assigns its deterministic hash."""
        now = time.time()
        tid = trace_id or f"trace_{int(now * 1000)}_{consumer_id}_{operation}"

        trace = RuntimeTrace(
            trace_id=tid,
            source=source,
            timestamp=now,
            mission_id=mission_id,
            consumer_id=consumer_id,
            contract_id=contract_id,
            operation=operation,
            input_payload=input_payload,
            output_payload=output_payload,
            status_code=status_code,
            stages=stages or [],
            side_effects=side_effects or [],
            events=events or [],
            economic_effects=economic_effects or [],
            authorization_state=authorization_state or {},
            parent_trace_hash=parent_trace_hash,
            environment=environment,
            build_hash=build_hash,
        )
        trace.trace_hash = compute_trace_hash(trace)
        self._traces[tid] = trace
        return trace

    def get_trace(self, trace_id: str) -> Optional[RuntimeTrace]:
        """Retrieves a trace by ID."""
        return self._traces.get(trace_id)

    def list_traces(
        self, contract_id: Optional[str] = None, consumer_id: Optional[str] = None
    ) -> List[RuntimeTrace]:
        """Lists traces with optional filters."""
        results = []
        for t in self._traces.values():
            if contract_id and t.contract_id != contract_id:
                continue
            if consumer_id and t.consumer_id != consumer_id:
                continue
            results.append(t)
        return results

    def verify_trace_integrity(self, trace: RuntimeTrace) -> bool:
        """Checks that trace hash matches recalculated content hash."""
        return trace.trace_hash == compute_trace_hash(trace)

    def clear(self) -> None:
        """Clears memory store."""
        self._traces.clear()
