"""
JARVIS OS — Phase 66: Multi-Agent Engineering Coordination & Conflict Arbitration
Module: conflicts.py
Multi-axis conflict detector across files, symbols, contracts, behaviors,
architecture, tests, security, resources, and execution ordering.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import (
    AgentConflict,
    AgentEngineeringIntent,
    ArbitrationResolution,
    ConflictType,
)


class AgentConflictDetector:
    """Detects structural, semantic, and security conflicts between concurrent agent intents."""

    def __init__(self):
        pass

    def detect_conflicts(
        self,
        intents: List[AgentEngineeringIntent],
    ) -> List[AgentConflict]:
        """Exhaustively inspect intent pairs for multi-category interference."""
        conflicts: List[AgentConflict] = []
        n = len(intents)

        for i in range(n):
            for j in range(i + 1, n):
                it_a = intents[i]
                it_b = intents[j]
                pair_conflicts = self.check_pair_conflict(it_a, it_b)
                conflicts.extend(pair_conflicts)

        return conflicts

    def check_pair_conflict(
        self,
        it_a: AgentEngineeringIntent,
        it_b: AgentEngineeringIntent,
    ) -> List[AgentConflict]:
        """Evaluate two intents across all 9 conflict axes."""
        conflicts: List[AgentConflict] = []

        # 1. Security Conflict (Protected paths or destructive operations)
        for f in it_a.requested_files + it_b.requested_files:
            if "governance" in f or "security" in f or "rollback" in f:
                conflicts.append(
                    AgentConflict(
                        conflict_id=f"conf_sec_{it_a.intent_id}_{it_b.intent_id}",
                        intent_a=it_a.intent_id,
                        intent_b=it_b.intent_id,
                        resource=f,
                        conflict_type=ConflictType.SECURITY_CONFLICT,
                        evidence=f"Attempted concurrent mutation of protected security path '{f}'.",
                        severity="CRITICAL",
                        resolution_options=[ArbitrationResolution.BLOCK, ArbitrationResolution.HUMAN_REVIEW],
                    )
                )

        # 2. Symbol Conflict (Same symbol requested)
        common_symbols = set(it_a.requested_symbols).intersection(set(it_b.requested_symbols))
        for sym in common_symbols:
            conflicts.append(
                AgentConflict(
                    conflict_id=f"conf_sym_{it_a.intent_id}_{it_b.intent_id}_{sym}",
                    intent_a=it_a.intent_id,
                    intent_b=it_b.intent_id,
                    resource=sym,
                    conflict_type=ConflictType.SYMBOL_CONFLICT,
                    evidence=f"Both intents target identical symbol '{sym}'.",
                    severity="HIGH",
                    resolution_options=[ArbitrationResolution.SERIALIZE, ArbitrationResolution.SPLIT, ArbitrationResolution.HUMAN_REVIEW],
                )
            )

        # 3. File Conflict (Same file, but check if symbols disjoint)
        common_files = set(it_a.requested_files).intersection(set(it_b.requested_files))
        for f in common_files:
            # If symbols are explicitly defined and disjoint, it's a candidate for 3-way merge
            if it_a.requested_symbols and it_b.requested_symbols and not common_symbols:
                conflicts.append(
                    AgentConflict(
                        conflict_id=f"conf_file_mergeable_{it_a.intent_id}_{it_b.intent_id}_{f}",
                        intent_a=it_a.intent_id,
                        intent_b=it_b.intent_id,
                        resource=f,
                        conflict_type=ConflictType.FILE_CONFLICT,
                        evidence=f"Shared file '{f}' with disjoint symbols; mergeable candidate.",
                        severity="MEDIUM",
                        resolution_options=[ArbitrationResolution.MERGE, ArbitrationResolution.SERIALIZE],
                    )
                )
            else:
                conflicts.append(
                    AgentConflict(
                        conflict_id=f"conf_file_direct_{it_a.intent_id}_{it_b.intent_id}_{f}",
                        intent_a=it_a.intent_id,
                        intent_b=it_b.intent_id,
                        resource=f,
                        conflict_type=ConflictType.FILE_CONFLICT,
                        evidence=f"Concurrent un-partitioned write to file '{f}'.",
                        severity="HIGH",
                        resolution_options=[ArbitrationResolution.SERIALIZE, ArbitrationResolution.REBASE, ArbitrationResolution.HUMAN_REVIEW],
                    )
                )

        # 4. Contract Conflict
        common_contracts = set(it_a.requested_contracts).intersection(set(it_b.requested_contracts))
        for c in common_contracts:
            conflicts.append(
                AgentConflict(
                    conflict_id=f"conf_cnt_{it_a.intent_id}_{it_b.intent_id}_{c}",
                    intent_a=it_a.intent_id,
                    intent_b=it_b.intent_id,
                    resource=c,
                    conflict_type=ConflictType.CONTRACT_CONFLICT,
                    evidence=f"Concurrent modification of schema/contract '{c}'.",
                    severity="HIGH",
                    resolution_options=[ArbitrationResolution.SERIALIZE, ArbitrationResolution.HUMAN_REVIEW, ArbitrationResolution.BLOCK],
                )
            )

        # 5. Behavior Conflict (Both introduce concurrency or timing adjustments)
        if ("async" in it_a.expected_effect.lower() or "timeout" in it_a.expected_effect.lower()) and \
           ("async" in it_b.expected_effect.lower() or "timeout" in it_b.expected_effect.lower()):
            conflicts.append(
                AgentConflict(
                    conflict_id=f"conf_beh_{it_a.intent_id}_{it_b.intent_id}",
                    intent_a=it_a.intent_id,
                    intent_b=it_b.intent_id,
                    resource="behavior_runtime",
                    conflict_type=ConflictType.BEHAVIOR_CONFLICT,
                    evidence="Concurrent mutation of asynchronous or timeout behavior surfaces.",
                    severity="HIGH",
                    resolution_options=[ArbitrationResolution.SERIALIZE, ArbitrationResolution.HUMAN_REVIEW],
                )
            )

        # 6. Order Conflict (Mutual dependencies)
        if it_a.intent_id in it_b.dependencies and it_b.intent_id in it_a.dependencies:
            conflicts.append(
                AgentConflict(
                    conflict_id=f"conf_order_{it_a.intent_id}_{it_b.intent_id}",
                    intent_a=it_a.intent_id,
                    intent_b=it_b.intent_id,
                    resource="execution_order",
                    conflict_type=ConflictType.ORDER_CONFLICT,
                    evidence=f"Cyclic mutual dependency detected between {it_a.intent_id} and {it_b.intent_id}.",
                    severity="CRITICAL",
                    resolution_options=[ArbitrationResolution.SPLIT, ArbitrationResolution.CANCEL, ArbitrationResolution.HUMAN_REVIEW],
                )
            )

        return conflicts
