"""
JARVIS OS — Phase 47: Polymorphic Consumer Impact Analyzer
Evaluates downstream consumer stance (already tolerates, explicitly rejects, ignores, uncertain)
when polymorphic schema variants are added, removed, or modified.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from agents.contract_governance.consumers import ContractConsumerRegistry
from agents.polymorphic_schema.models import (
    ConsumerVariantImpact,
    ConsumerVariantStance,
    PolymorphicSchema,
    SchemaVariant,
)
from agents.semantic_graph.graph import CrossLanguageSemanticGraph


class PolymorphicConsumerAnalyzer:
    """Discovers downstream consumers and assesses their tolerance for polymorphic variants."""

    def __init__(
        self,
        consumer_registry: Optional[ContractConsumerRegistry] = None,
        semantic_graph: Optional[CrossLanguageSemanticGraph] = None,
    ) -> None:
        self.consumer_registry = consumer_registry or ContractConsumerRegistry()
        self.semantic_graph = semantic_graph

    @classmethod
    def assess_consumer_impact(
        cls,
        consumer_metadata: Dict[str, Any],
        polymorphic_schema: PolymorphicSchema,
        new_variant: SchemaVariant,
    ) -> ConsumerVariantImpact:
        """Assesses an individual consumer metadata dict against a new variant."""
        c_id = str(consumer_metadata.get("consumer_id", "consumer"))
        consumed = set(consumer_metadata.get("consumed_fields", []))
        common = set(polymorphic_schema.common_fields)
        strict = bool(consumer_metadata.get("strict_types", False))
        target_filter = str(consumer_metadata.get("target_filter", ""))

        # 1. Filtered out / ignored
        if target_filter:
            disc_val = str(new_variant.discriminator_value or "")
            clean_filter = target_filter.replace(".*", "")
            if not disc_val.startswith(clean_filter):
                return ConsumerVariantImpact(
                    consumer_id=c_id,
                    consumer_type="SERVICE",
                    variant_id=new_variant.variant_id,
                    stance=ConsumerVariantStance.IGNORES,
                    explanation=f"Consumer filters by {target_filter}; ignores variant {disc_val}",
                )

        # 2. Consumes only common fields
        if consumed and consumed.issubset(common):
            return ConsumerVariantImpact(
                consumer_id=c_id,
                consumer_type="SERVICE",
                variant_id=new_variant.variant_id,
                stance=ConsumerVariantStance.ALREADY_TOLERATES,
                explanation="Consumer consumes only common fields; immune to variant specifics.",
            )

        # 3. Strict types without supporting this variant
        supp = consumer_metadata.get("supported_discriminators", [])
        if strict and supp:
            if new_variant.discriminator_value not in supp:
                return ConsumerVariantImpact(
                    consumer_id=c_id,
                    consumer_type="SERVICE",
                    variant_id=new_variant.variant_id,
                    stance=ConsumerVariantStance.EXPLICITLY_REJECTS,
                    explanation="Consumer requires strict discriminator matching; lacks handler for new variant.",
                )

        return ConsumerVariantImpact(
            consumer_id=c_id,
            consumer_type="SERVICE",
            variant_id=new_variant.variant_id,
            stance=ConsumerVariantStance.UNCERTAIN,
            explanation="Consumer tolerance cannot be determined without deeper AST analysis.",
        )

    def analyze_variant_impact(
        self,
        contract_id: str,
        variant: SchemaVariant,
        polymorphic_schema: PolymorphicSchema,
        action: str = "VARIANT_ADDED",
    ) -> List[ConsumerVariantImpact]:
        """Assesses downstream consumers for a given polymorphic variant."""
        impacts: List[ConsumerVariantImpact] = []

        # 1. Get base consumers from registry
        registered_consumers = self.consumer_registry.get_consumers(contract_id)

        common_keys = set(polymorphic_schema.common_fields)
        variant_keys = set(variant.schema.get("properties", variant.schema).keys()) - common_keys

        for c in registered_consumers:
            c_desc = c.description.lower()

            # Rule 1: Consumer only touches common fields => IGNORES variant specifics
            if "common_fields_only" in c_desc or not variant_keys:
                stance = ConsumerVariantStance.IGNORES
                exp = f"Consumer '{c.consumer_id}' consumes only common fields; immune to variant-specific changes."
            
            # Rule 2: Explicit rejection / hardcoded discriminators
            elif "strict_enum" in c_desc or "no_fallback" in c_desc:
                stance = ConsumerVariantStance.EXPLICITLY_REJECTS
                exp = f"Consumer '{c.consumer_id}' explicitly matches a closed set of variants and lacks fallback."
            
            # Rule 3: Tolerant consumer (e.g. open TypeScript union or default branch)
            elif "pattern_matching" in c_desc or "exhaustive_switch" in c_desc or "tolerant" in c_desc:
                stance = ConsumerVariantStance.ALREADY_TOLERATES
                exp = f"Consumer '{c.consumer_id}' has pattern matching with default handling for new variants."

            # Rule 4: Otherwise, if variant was removed => EXPLICITLY_REJECTS / Breaks
            elif action == "VARIANT_REMOVED":
                stance = ConsumerVariantStance.EXPLICITLY_REJECTS
                exp = f"Consumer '{c.consumer_id}' expected variant '{variant.variant_id}' which was removed."

            # Default: UNCERTAIN until AST inspection
            else:
                stance = ConsumerVariantStance.UNCERTAIN
                exp = f"Consumer '{c.consumer_id}' depends on endpoint; variant compatibility requires AST review."

            impacts.append(
                ConsumerVariantImpact(
                    consumer_id=c.consumer_id,
                    consumer_type=c.consumer_type,
                    variant_id=variant.variant_id,
                    stance=stance,
                    explanation=exp,
                    evidence_refs=[],
                )
            )

        return impacts
