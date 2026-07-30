from __future__ import annotations

from collections.abc import Mapping

from backend.capability_registry.contracts import (
    CapabilityDefinition,
    CapabilityId,
)
from backend.capability_registry.exceptions import UnknownCapabilityError


CAPABILITY_ALIASES: Mapping[str, CapabilityId] = {
    "code_reasoning": CapabilityId.LOCALIZED_CODE_REASONING,
    "tool_selection": CapabilityId.TOOL_SELECTION_WITHOUT_EXECUTION,
}


_CAPABILITY_TEXT: Mapping[CapabilityId, tuple[str, str]] = {
    CapabilityId.CONSTRAINT_BASED_CHOICE: (
        "Constraint-based choice",
        "Chooses among explicit alternatives while retaining stated constraints.",
    ),
    CapabilityId.STRUCTURED_EXTRACTION: (
        "Structured extraction",
        "Extracts source facts into a validated structured output.",
    ),
    CapabilityId.REFERENCE_DISCIPLINE: (
        "Reference discipline",
        "Uses only references allowed or evidenced by the supplied context.",
    ),
    CapabilityId.BOUNDED_CONTEXT_USE: (
        "Bounded context use",
        "Finds and uses relevant facts in an explicitly bounded context.",
    ),
    CapabilityId.LOCALIZED_CODE_REASONING: (
        "Localized code reasoning",
        "Diagnoses a localized code problem from supplied code evidence.",
    ),
    CapabilityId.NEGATIVE_CONSTRAINT_FOLLOWING: (
        "Negative constraint following",
        "Retains and follows explicit exclusions in a bounded task.",
    ),
    CapabilityId.TOOL_SELECTION_WITHOUT_EXECUTION: (
        "Tool selection without execution",
        "Selects an allowed tool and arguments without executing it.",
    ),
    CapabilityId.INSTRUCTION_HIERARCHY: (
        "Instruction hierarchy",
        "Rejects lower-priority instructions that conflict with the task contract.",
    ),
    CapabilityId.STATEFUL_TOOL_USE: (
        "Stateful tool use",
        "Selects tools over multiple turns while retaining observations and state.",
    ),
    CapabilityId.CONSTRAINT_RETENTION: (
        "Constraint retention",
        "Retains explicit constraints across a multi-step interaction.",
    ),
    CapabilityId.EVIDENCE_ACCUMULATION: (
        "Evidence accumulation",
        "Accumulates distinct evidence across bounded state transitions.",
    ),
    CapabilityId.MULTI_FILE_REASONING: (
        "Multi-file reasoning",
        "Reasons about contracts or behavior distributed across multiple files.",
    ),
    CapabilityId.CONTEXT_SCALING: (
        "Context scaling",
        "Maintains validated behavior as supplied context grows.",
    ),
    CapabilityId.RECOVERY_AFTER_FAILURE: (
        "Recovery after failure",
        "Recovers from a measured failure using the configured recovery contract.",
    ),
    CapabilityId.SHORT_HORIZON_PLANNING: (
        "Short-horizon planning",
        "Produces a bounded plan with dependencies and completion conditions.",
    ),
    CapabilityId.CLOSED_SOURCE_RESEARCH: (
        "Closed-source research",
        "Builds supported conclusions from a closed set of supplied sources.",
    ),
    CapabilityId.EVIDENCE_BASED_DOCUMENT_GENERATION: (
        "Evidence-based document generation",
        "Generates document content whose claims remain grounded in supplied evidence.",
    ),
    CapabilityId.VISION: (
        "Vision",
        "Interprets visual input under an evaluated benchmark contract.",
    ),
    CapabilityId.THINKING: (
        "Thinking",
        "Uses an explicitly evaluated thinking mode under a recorded configuration.",
    ),
    CapabilityId.LONG_CONTEXT_REASONING: (
        "Long-context reasoning",
        "Reasons correctly over a benchmarked long-context range.",
    ),
    CapabilityId.LONG_RUNNING_EXECUTION: (
        "Long-running execution",
        "Completes a benchmarked prolonged execution while retaining valid state.",
    ),
}


def default_capability_catalog() -> dict[CapabilityId, CapabilityDefinition]:
    return {
        capability_id: CapabilityDefinition(
            id=capability_id,
            display_name=display_name,
            description=description,
        )
        for capability_id, (display_name, description) in _CAPABILITY_TEXT.items()
    }


def canonical_capability_id(value: CapabilityId | str) -> CapabilityId:
    if isinstance(value, CapabilityId):
        return value
    normalized = str(value or "").strip().lower()
    if normalized in CAPABILITY_ALIASES:
        return CAPABILITY_ALIASES[normalized]
    try:
        return CapabilityId(normalized)
    except ValueError as exc:
        raise UnknownCapabilityError(
            f"Capability desconhecida: {normalized or '<vazia>'}."
        ) from exc
