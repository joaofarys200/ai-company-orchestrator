"""
JARVIS OS — Phase 51: Behavioral Proof Coverage & Scenario Exploration
Deterministic Scenario Mutator with strict categorical separation and sandbox guards.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

from agents.behavioral_proof_exploration.models import (
    BehavioralScenario,
    ExplorationStrategy,
    MutationCategory,
)


class UnsafeEconomicMutationError(Exception):
    """Raised when an economic mutation attempts to target a non-sandbox environment."""
    pass


class ScenarioMutator:
    """
    Deterministic Mutation Engine.
    Applies categorized mutations to payloads and scenarios.
    Guarantees that economic mutations are strictly confined to sandbox/read-only mode.
    """

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed

    def mutate_field_removal(self, payload: Dict[str, Any], field_name: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Remove a field from payload (SCHEMA category)."""
        mutated = copy.deepcopy(payload)
        if field_name in mutated:
            del mutated[field_name]
        return mutated, {"category": MutationCategory.SCHEMA.value, "type": "field_removal", "target": field_name}

    def mutate_field_addition(self, payload: Dict[str, Any], field_name: str, value: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Add an unexpected field to payload (SCHEMA category)."""
        mutated = copy.deepcopy(payload)
        mutated[field_name] = value
        return mutated, {"category": MutationCategory.SCHEMA.value, "type": "field_addition", "target": field_name, "value": value}

    def mutate_type_substitution(self, payload: Dict[str, Any], field_name: str, substitute_val: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Substitute field value with an incompatible type (DATA category)."""
        mutated = copy.deepcopy(payload)
        mutated[field_name] = substitute_val
        return mutated, {"category": MutationCategory.DATA.value, "type": "type_substitution", "target": field_name, "value": substitute_val}

    def mutate_null_injection(self, payload: Dict[str, Any], field_name: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Inject null into a field (DATA category)."""
        mutated = copy.deepcopy(payload)
        mutated[field_name] = None
        return mutated, {"category": MutationCategory.DATA.value, "type": "null_injection", "target": field_name}

    def mutate_boundary_expansion(self, payload: Dict[str, Any], field_name: str, boundary_val: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Expand field to boundary limit (DATA category)."""
        mutated = copy.deepcopy(payload)
        mutated[field_name] = boundary_val
        return mutated, {"category": MutationCategory.DATA.value, "type": "boundary_expansion", "target": field_name, "value": boundary_val}

    def mutate_enum_substitution(self, payload: Dict[str, Any], field_name: str, enum_val: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Substitute enum value (SCHEMA category)."""
        mutated = copy.deepcopy(payload)
        mutated[field_name] = enum_val
        return mutated, {"category": MutationCategory.SCHEMA.value, "type": "enum_substitution", "target": field_name, "value": enum_val}

    def mutate_variant_substitution(self, payload: Dict[str, Any], variant_name: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Substitute polymorphic variant (SCHEMA category)."""
        mutated = copy.deepcopy(payload)
        mutated["type"] = variant_name
        mutated["variant"] = variant_name
        return mutated, {"category": MutationCategory.SCHEMA.value, "type": "variant_substitution", "variant": variant_name}

    def mutate_event_reorder(self, events: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Reorder list of events (FLOW category)."""
        mutated = list(reversed(events))
        return mutated, {"category": MutationCategory.FLOW.value, "type": "event_reorder"}

    def mutate_event_duplication(self, events: List[Dict[str, Any]], index: int = 0) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Duplicate an event at given index (FLOW category)."""
        mutated = copy.deepcopy(events)
        if mutated and 0 <= index < len(mutated):
            mutated.insert(index, copy.deepcopy(mutated[index]))
        return mutated, {"category": MutationCategory.FLOW.value, "type": "event_duplication", "index": index}

    def mutate_retry(self, payload: Dict[str, Any], idempotency_key: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Inject retry metadata with idempotency key (FLOW category)."""
        mutated = copy.deepcopy(payload)
        mutated["idempotency_key"] = idempotency_key
        mutated["is_retry"] = True
        return mutated, {"category": MutationCategory.FLOW.value, "type": "retry", "idempotency_key": idempotency_key}

    def mutate_timeout(self, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Simulate request timeout (TIMING category)."""
        mutated = copy.deepcopy(payload)
        mutated["__simulate_timeout__"] = True
        return mutated, {"category": MutationCategory.TIMING.value, "type": "timeout"}

    def mutate_authorization_state_change(self, payload: Dict[str, Any], auth_role: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Change caller authorization state/role (AUTH category)."""
        mutated = copy.deepcopy(payload)
        mutated["__caller_role__"] = auth_role
        return mutated, {"category": MutationCategory.AUTH.value, "type": "authorization_state_change", "role": auth_role}

    def mutate_economic_amount(
        self,
        payload: Dict[str, Any],
        new_amount: float,
        environment: str = "sandbox",
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Mutate monetary amount (ECONOMIC category).
        Enforces sandbox-only rule to prevent real economic loss.
        """
        if environment not in ("sandbox", "mock", "test"):
            raise UnsafeEconomicMutationError(
                f"Economic mutations are strictly prohibited in environment '{environment}'. Only sandbox allowed."
            )
        mutated = copy.deepcopy(payload)
        mutated["amount"] = new_amount
        return mutated, {
            "category": MutationCategory.ECONOMIC.value,
            "type": "amount_change",
            "new_amount": new_amount,
            "sandbox": True,
        }

    def mutate_economic_currency(
        self,
        payload: Dict[str, Any],
        new_currency: str,
        environment: str = "sandbox",
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Mutate currency code (ECONOMIC category).
        Enforces sandbox-only rule.
        """
        if environment not in ("sandbox", "mock", "test"):
            raise UnsafeEconomicMutationError(
                f"Economic mutations are strictly prohibited in environment '{environment}'. Only sandbox allowed."
            )
        mutated = copy.deepcopy(payload)
        mutated["currency"] = new_currency
        return mutated, {
            "category": MutationCategory.ECONOMIC.value,
            "type": "currency_change",
            "new_currency": new_currency,
            "sandbox": True,
        }
