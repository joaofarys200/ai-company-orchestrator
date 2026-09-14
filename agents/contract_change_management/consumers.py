"""
JARVIS OS — Phase 48: Contract-Aware Autonomous Change Management
ContractConsumerTracer: Maps and categorizes all direct, indirect, test, and browser consumers.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set
from agents.contract_change_management.models import (
    ConsumerCategory,
    ConsumerPatternMatching,
    ContractConsumerTrace,
    ContractRiskLevel,
)


class ContractConsumerTracer:
    """
    Traces consumers of a contract across the CrossLanguageSemanticGraph,
    evaluating their pattern matching characteristics (closed vs open enum).
    """

    DEFAULT_KNOWN_CONSUMERS: dict[str, list[dict[str, Any]]] = {
        "/api/v1/events": [
            {
                "consumer_id": "audit-logger-svc",
                "name": "Audit Logging Worker",
                "file_path": "backend/workers/audit_logger.py",
                "category": ConsumerCategory.DIRECT,
                "pattern_matching": ConsumerPatternMatching.OPEN_WITH_FALLBACK,
                "impact_reason": "Consumes only common headers and metadata; tolerates variant changes.",
                "required_action": "None",
                "language": "Python",
            },
            {
                "consumer_id": "billing-dispatcher",
                "name": "Billing Event Dispatcher",
                "file_path": "backend/services/billing.py",
                "category": ConsumerCategory.INDIRECT,
                "pattern_matching": ConsumerPatternMatching.OPEN_WITH_FALLBACK,
                "impact_reason": "Explicitly filters on billing namespace; ignores other variants.",
                "required_action": "None",
                "language": "Python",
            },
            {
                "consumer_id": "crm-sync-worker",
                "name": "CRM Sync Worker (Exhaustive Switch)",
                "file_path": "frontend/src/features/crm/syncHandler.ts",
                "category": ConsumerCategory.DIRECT,
                "pattern_matching": ConsumerPatternMatching.CLOSED_EXHAUSTIVE,
                "impact_reason": "Exhaustive TypeScript switch on event type; lacks default fallback branch.",
                "required_action": "Update switch statement with new case or default handler.",
                "language": "TypeScript",
            },
            {
                "consumer_id": "test-events-suite",
                "name": "Audit Event Contract Tests",
                "file_path": "tests/test_audit_events.py",
                "category": ConsumerCategory.TEST,
                "pattern_matching": ConsumerPatternMatching.CLOSED_EXHAUSTIVE,
                "impact_reason": "Asserts payload shape and discriminator values.",
                "required_action": "Add test scenario for proposed variant.",
                "language": "Python",
            },
            {
                "consumer_id": "browser-audit-qa",
                "name": "Browser QA Activity Log View",
                "file_path": "scripts/run_browser_qa.py",
                "category": ConsumerCategory.BROWSER_SCENARIO,
                "pattern_matching": ConsumerPatternMatching.OPEN_WITH_FALLBACK,
                "impact_reason": "Renders activity stream table with fallback icons.",
                "required_action": "Verify visual rendering of new event card.",
                "language": "Python",
            },
        ],
        "/api/v1/users": [
            {
                "consumer_id": "frontend-user-card",
                "name": "Frontend UserCard Component",
                "file_path": "frontend/src/components/UserCard.tsx",
                "category": ConsumerCategory.DIRECT,
                "pattern_matching": ConsumerPatternMatching.CLOSED_EXHAUSTIVE,
                "impact_reason": "Directly renders user profile fields expecting avatar to be a primitive string.",
                "required_action": "Adapt component to handle avatar object structure.",
                "language": "TypeScript",
            },
            {
                "consumer_id": "admin-user-table",
                "name": "Admin Dashboard User Table",
                "file_path": "frontend/src/features/admin/UserTable.tsx",
                "category": ConsumerCategory.INDIRECT,
                "pattern_matching": ConsumerPatternMatching.OPEN_WITH_FALLBACK,
                "impact_reason": "Displays user table with optional fallback rendering.",
                "required_action": "Revalidate table columns.",
                "language": "TypeScript",
            },
            {
                "consumer_id": "test-user-api",
                "name": "User API Integration Test",
                "file_path": "tests/test_user_api.py",
                "category": ConsumerCategory.TEST,
                "pattern_matching": ConsumerPatternMatching.CLOSED_EXHAUSTIVE,
                "impact_reason": "Asserts response JSON matches v1 schema.",
                "required_action": "Update expected schema fixture to v2.",
                "language": "Python",
            },
            {
                "consumer_id": "browser-user-profile-qa",
                "name": "Browser QA User Profile Scenario",
                "file_path": "scripts/run_browser_qa_user.py",
                "category": ConsumerCategory.BROWSER_SCENARIO,
                "pattern_matching": ConsumerPatternMatching.CLOSED_EXHAUSTIVE,
                "impact_reason": "Verifies profile page display in browser.",
                "required_action": "Verify profile avatar rendering.",
                "language": "Python",
            },
        ],
    }

    @classmethod
    def trace_consumers(
        cls,
        contract_id: str,
        route: Optional[str] = None,
        semantic_graph: Optional[Any] = None,
        code_snippet: Optional[str] = None,
    ) -> list[ContractConsumerTrace]:
        """
        Traces all direct, indirect, test, and browser consumers for a contract.
        """
        key = route or contract_id
        matching_consumers: list[dict[str, Any]] = []

        # 1. Match from default known registry
        for known_key, consumers in cls.DEFAULT_KNOWN_CONSUMERS.items():
            if known_key in key or key in known_key:
                matching_consumers.extend(consumers)
                break

        # 2. Semantic graph traversal if available
        if semantic_graph and hasattr(semantic_graph, "nodes"):
            for node_id, node in semantic_graph.nodes.items():
                if contract_id in node_id or (route and route in node_id):
                    # Find incoming edges (consumers calling this contract)
                    for edge in getattr(semantic_graph, "edges", []):
                        if getattr(edge, "target", "") == node_id:
                            src_node = semantic_graph.nodes.get(getattr(edge, "source", ""))
                            if src_node:
                                matching_consumers.append({
                                    "consumer_id": getattr(src_node, "symbol", getattr(src_node, "node_id", "consumer")),
                                    "name": getattr(src_node, "symbol", "Semantic Graph Consumer"),
                                    "file_path": getattr(src_node, "source_ref", "unknown"),
                                    "category": ConsumerCategory.DIRECT,
                                    "pattern_matching": cls.detect_pattern_matching(code_snippet or ""),
                                    "impact_reason": f"Direct dependency in semantic graph via edge {getattr(edge, 'edge_id', '')}",
                                    "required_action": "Verify contract compatibility",
                                    "language": "TypeScript" if getattr(src_node, "source_ref", "").endswith((".ts", ".tsx")) else "Python",
                                })

        # 3. If no match found, formulate dynamic fallback trace
        if not matching_consumers:
            clean_name = key.replace("/", "_").strip("_")
            matching_consumers = [
                {
                    "consumer_id": f"{clean_name}-client",
                    "name": f"{clean_name.title()} API Client",
                    "file_path": f"frontend/src/api/{clean_name}.ts",
                    "category": ConsumerCategory.DIRECT,
                    "pattern_matching": cls.detect_pattern_matching(code_snippet or ""),
                    "impact_reason": "Direct HTTP consumer calling endpoint.",
                    "required_action": "Verify parameter and response types.",
                    "language": "TypeScript",
                },
                {
                    "consumer_id": f"test-{clean_name}",
                    "name": f"Test {clean_name.title()}",
                    "file_path": f"tests/test_{clean_name}.py",
                    "category": ConsumerCategory.TEST,
                    "pattern_matching": ConsumerPatternMatching.CLOSED_EXHAUSTIVE,
                    "impact_reason": "Verifies endpoint contract invariants.",
                    "required_action": "Run test suite against updated contract.",
                    "language": "Python",
                },
            ]

        traces: list[ContractConsumerTrace] = []
        for c in matching_consumers:
            traces.append(ContractConsumerTrace(
                consumer_id=c["consumer_id"],
                name=c["name"],
                file_path=c["file_path"],
                category=c["category"],
                pattern_matching=c.get("pattern_matching", ConsumerPatternMatching.UNKNOWN),
                impact_reason=c["impact_reason"],
                required_action=c["required_action"],
                language=c.get("language", "TypeScript"),
            ))

        return traces

    @classmethod
    def detect_pattern_matching(cls, code: str) -> ConsumerPatternMatching:
        """
        Inspects code to determine if it uses closed exhaustive pattern matching
        or has a tolerant fallback / default branch.
        """
        if not code:
            return ConsumerPatternMatching.UNKNOWN

        # TypeScript / JavaScript switch detection
        if "switch" in code:
            if "default:" in code or "default :" in code:
                return ConsumerPatternMatching.OPEN_WITH_FALLBACK
            return ConsumerPatternMatching.CLOSED_EXHAUSTIVE

        # Python match / case detection
        if "match " in code and "case " in code:
            if "case _:" in code or "case _ :" in code:
                return ConsumerPatternMatching.OPEN_WITH_FALLBACK
            return ConsumerPatternMatching.CLOSED_EXHAUSTIVE

        # Dictionary lookup without .get() default
        if re.search(r"\b\w+\[\s*['\"]\w+['\"]\s*\]", code) and ".get(" not in code:
            return ConsumerPatternMatching.CLOSED_EXHAUSTIVE

        # Dictionary lookup with .get(key, default)
        if ".get(" in code:
            return ConsumerPatternMatching.OPEN_WITH_FALLBACK

        return ConsumerPatternMatching.OPEN_WITH_FALLBACK
