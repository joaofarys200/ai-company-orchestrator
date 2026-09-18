"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: patterns.py
Architectural evolution patterns, template refactoring definitions, and Phase 63
cross-project hypothesis bridging.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


ARCHITECTURE_PATTERNS: Dict[str, Dict[str, Any]] = {
    "keep_current": {
        "title": "Keep Current Architecture",
        "description": "Retain existing component boundaries and document known debt.",
        "reversibility": "EASILY_REVERSIBLE",
        "default_complexity": "LOW",
    },
    "modularization": {
        "title": "Subsystem Modularization",
        "description": "Partition monolithic package into independent cohesive submodules.",
        "reversibility": "REVERSIBLE_WITH_MIGRATION",
        "default_complexity": "MEDIUM",
    },
    "boundary_extraction": {
        "title": "Boundary & Interface Extraction",
        "description": "Introduce explicit interface segregation between modules to eliminate cyclic loops.",
        "reversibility": "EASILY_REVERSIBLE",
        "default_complexity": "MEDIUM",
    },
    "dependency_inversion": {
        "title": "Dependency Inversion (DIP)",
        "description": "Decouple callers by depending on abstractions rather than concrete implementations.",
        "reversibility": "REVERSIBLE_WITH_MIGRATION",
        "default_complexity": "MEDIUM",
    },
    "event_driven": {
        "title": "Event-Driven Asynchronous Decoupling",
        "description": "Publish events over an event bus instead of synchronous call cascades.",
        "reversibility": "DIFFICULT_TO_REVERSE",
        "default_complexity": "HIGH",
    },
    "synchronous_api": {
        "title": "Strongly Typed Synchronous API",
        "description": "Expose explicit request-response endpoints with formal contract schemas.",
        "reversibility": "EASILY_REVERSIBLE",
        "default_complexity": "LOW",
    },
    "adapter_layer": {
        "title": "Two-Way Semantic Adapter",
        "description": "Isolate legacy contracts and schema shifts behind an adapting translation layer.",
        "reversibility": "EASILY_REVERSIBLE",
        "default_complexity": "MEDIUM",
    },
    "facade": {
        "title": "Gateway Facade",
        "description": "Unified simplified interface wrapping internal complex multi-component interactions.",
        "reversibility": "EASILY_REVERSIBLE",
        "default_complexity": "LOW",
    },
    "strangler_migration": {
        "title": "Strangler Fig Phased Migration",
        "description": "Incrementally replace legacy code paths under dual-run validation until full cutover.",
        "reversibility": "REVERSIBLE_WITH_MIGRATION",
        "default_complexity": "HIGH",
    },
    "data_boundary": {
        "title": "Data Store Boundary Isolation",
        "description": "Dedicate table or collection ownership to a single service with API-only access for others.",
        "reversibility": "REVERSIBLE_WITH_MIGRATION",
        "default_complexity": "HIGH",
    },
    "cache_boundary": {
        "title": "Read-Through Cache Boundary",
        "description": "Protect database bottlenecks and high fan-in hubs with an invalidation-aware cache layer.",
        "reversibility": "EASILY_REVERSIBLE",
        "default_complexity": "MEDIUM",
    },
    "queue_boundary": {
        "title": "Buffered Work Queue Boundary",
        "description": "Buffer high-frequency bursts via durable asynchronous queues with worker pools.",
        "reversibility": "REVERSIBLE_WITH_MIGRATION",
        "default_complexity": "MEDIUM",
    },
}


def convert_f63_to_architecture_hypothesis(knowledge_item_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforms an external EngineeringKnowledgeItem (Phase 63) into a local
    architecture pattern hypothesis.

    Invariant:
        Never marks external pattern as ARCHITECTURE_APPROVED.
        Must retain source project and knowledge ID for cryptographic audit trail.
    """
    src_proj = knowledge_item_dict.get("source_project_id", "external_repo")
    k_id = knowledge_item_dict.get("knowledge_id", "unknown_k_id")
    pattern_data = knowledge_item_dict.get("pattern", {})

    return {
        "title": pattern_data.get("title", f"Transferred Pattern from {src_proj}"),
        "description": pattern_data.get("description", "Architecture hypothesis adapted from cross-project experience."),
        "source_project": src_proj,
        "knowledge_id": k_id,
        "benefits": pattern_data.get("benefits", ["Observed success in donor repository"]),
        "costs": pattern_data.get("costs", ["Adaptation to local constraints and local verification"]),
        "risks": pattern_data.get("risks", ["Semantic drift between repositories"]),
        "suggested_type": pattern_data.get("architecture_type", "adapter_layer"),
        "transfer_decision": "TRANSFER_AS_HYPOTHESIS",
        "local_evidence": "Awaiting local verification in target workspace",
    }
