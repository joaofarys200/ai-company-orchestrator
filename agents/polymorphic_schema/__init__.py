"""
JARVIS OS — Phase 47: Polymorphic Schema Semantics & Contract Compatibility Package
"""

from agents.polymorphic_schema.models import (
    PolymorphicSchemaKind,
    VariantStatus,
    DiscriminatorLocation,
    DiscriminatorType,
    VariantDiffType,
    CompatibilityVerdict,
    ConsumerVariantStance,
    DiscriminatorDefinition,
    SchemaVariant,
    ErrorVariant,
    PolymorphicSchema,
    VariantDiff,
    SchemaCompatibilityMatrix,
    ConsumerVariantImpact,
    PolymorphicDriftReport,
)
from agents.polymorphic_schema.discriminator import DiscriminatorEngine
from agents.polymorphic_schema.detector import PolymorphicDetector
from agents.polymorphic_schema.compatibility import PolymorphicCompatibilityEngine
from agents.polymorphic_schema.diff import PolymorphicDiffEngine
from agents.polymorphic_schema.consumers import PolymorphicConsumerAnalyzer
from agents.polymorphic_schema.security import PolymorphicSecuritySentinel
from agents.polymorphic_schema.bridge import PolymorphicGovernanceBridge

__all__ = [
    "PolymorphicSchemaKind",
    "VariantStatus",
    "DiscriminatorLocation",
    "DiscriminatorType",
    "VariantDiffType",
    "CompatibilityVerdict",
    "ConsumerVariantStance",
    "DiscriminatorDefinition",
    "SchemaVariant",
    "ErrorVariant",
    "PolymorphicSchema",
    "VariantDiff",
    "SchemaCompatibilityMatrix",
    "ConsumerVariantImpact",
    "PolymorphicDriftReport",
    "DiscriminatorEngine",
    "PolymorphicDetector",
    "PolymorphicCompatibilityEngine",
    "PolymorphicDiffEngine",
    "PolymorphicConsumerAnalyzer",
    "PolymorphicSecuritySentinel",
    "PolymorphicGovernanceBridge",
]
