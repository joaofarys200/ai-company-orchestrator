"""
JARVIS OS — Phase 44: Formal Semantic Adapter Contracts & Registry

Defines the formal adapters that mediate cross-language and cross-ecosystem relations.
Every adapter has explicit validation rules, schema versioning, and allowed relation types.
Never use magical or name-based translation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from agents.semantic_graph.models import (
    ConfidenceClass,
    SemanticNode,
    SemanticNodeType,
    SemanticRelationType,
    ValidationStatus,
)


@dataclass
class SemanticAdapter:
    """Formal contract specifying how entities from source_ecosystem map to target_ecosystem."""

    adapter_id: str
    source_ecosystem: str
    target_ecosystem: str
    source_node_types: list[SemanticNodeType]
    target_node_types: list[SemanticNodeType]
    supported_relations: list[SemanticRelationType]
    schema_version: str = "1.0.0"
    validation_rules: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "source_ecosystem": self.source_ecosystem,
            "target_ecosystem": self.target_ecosystem,
            "source_node_types": [t.value for t in self.source_node_types],
            "target_node_types": [t.value for t in self.target_node_types],
            "supported_relations": [r.value for r in self.supported_relations],
            "schema_version": self.schema_version,
            "validation_rules": list(self.validation_rules),
            "metadata": self.metadata,
        }

    def validate_connection(
        self,
        source: SemanticNode,
        target: SemanticNode,
        relation: SemanticRelationType,
    ) -> tuple[ValidationStatus, str]:
        """Validates that source, target, and relation conform to this adapter's contractual constraints."""
        # 1. Check node types
        if source.node_type not in self.source_node_types:
            return ValidationStatus.INVALID, f"Source node type '{source.node_type.value}' is not supported by adapter '{self.adapter_id}'"

        if target.node_type not in self.target_node_types:
            return ValidationStatus.INVALID, f"Target node type '{target.node_type.value}' is not supported by adapter '{self.adapter_id}'"

        # 2. Check relation
        if relation not in self.supported_relations:
            return ValidationStatus.INVALID, f"Relation '{relation.value}' is not supported by adapter '{self.adapter_id}'"

        # 3. Check ecosystem matching
        src_eco = (source.ecosystem or "").lower()
        tgt_eco = (target.ecosystem or "").lower()
        adapt_src = self.source_ecosystem.lower()
        adapt_tgt = self.target_ecosystem.lower()

        if adapt_src != "*" and src_eco != "*" and adapt_src != src_eco:
            return ValidationStatus.INVALID, f"Source ecosystem '{src_eco}' does not match adapter requirement '{adapt_src}'"

        if adapt_tgt != "*" and tgt_eco != "*" and adapt_tgt != tgt_eco:
            return ValidationStatus.INVALID, f"Target ecosystem '{tgt_eco}' does not match adapter requirement '{adapt_tgt}'"

        return ValidationStatus.VALID, "Connection conforms to formal adapter contract"


class SemanticAdapterRegistry:
    """Registry managing official adapters for cross-language bridges."""

    def __init__(self) -> None:
        self._adapters: dict[str, SemanticAdapter] = {}
        self._register_default_adapters()

    def register_adapter(self, adapter: SemanticAdapter) -> None:
        self._adapters[adapter.adapter_id] = adapter

    def get_adapter(self, adapter_id: str) -> Optional[SemanticAdapter]:
        return self._adapters.get(adapter_id)

    def list_adapters(self) -> list[SemanticAdapter]:
        return list(self._adapters.values())

    def resolve_adapter(
        self,
        source: SemanticNode,
        target: SemanticNode,
        relation: SemanticRelationType,
    ) -> tuple[Optional[SemanticAdapter], ValidationStatus, str]:
        """Finds the formal adapter that matches the given node pair and relation."""
        src_eco = (source.ecosystem or "agnostic").lower()
        tgt_eco = (target.ecosystem or "agnostic").lower()

        candidate_adapters: list[SemanticAdapter] = []
        for adapter in self._adapters.values():
            # Check source type & relation support
            if source.node_type in adapter.source_node_types and target.node_type in adapter.target_node_types:
                if relation in adapter.supported_relations:
                    # Check ecosystem compatibility
                    src_match = adapter.source_ecosystem in ("*", src_eco)
                    tgt_match = adapter.target_ecosystem in ("*", tgt_eco)
                    if src_match and tgt_match:
                        candidate_adapters.append(adapter)

        if not candidate_adapters:
            # Check if an ecosystem pair exists without registered adapter
            return None, ValidationStatus.UNCERTAIN, f"No formal adapter exists between '{src_eco}' and '{tgt_eco}' for '{relation.value}'"

        # Validate with the first matching specific adapter
        best_adapter = candidate_adapters[0]
        status, reason = best_adapter.validate_connection(source, target, relation)
        return best_adapter, status, reason

    def _register_default_adapters(self) -> None:
        """Installs the default suite of formal adapters covering standard full-stack ecosystems."""

        # 1. Requirement -> Architecture Component
        self.register_adapter(
            SemanticAdapter(
                adapter_id="REQUIREMENT_TO_ARCHITECTURE",
                source_ecosystem="agnostic",
                target_ecosystem="agnostic",
                source_node_types=[SemanticNodeType.REQUIREMENT, SemanticNodeType.CONSTRAINT],
                target_node_types=[SemanticNodeType.ARCHITECTURE_COMPONENT],
                supported_relations=[SemanticRelationType.IMPLEMENTS, SemanticRelationType.REQUIRES],
                schema_version="1.0.0",
                validation_rules=["Requirement must state functional capability", "Architecture component must be language-neutral"],
            )
        )

        # 2. Architecture Component -> Frontend / Backend Implementation
        self.register_adapter(
            SemanticAdapter(
                adapter_id="ARCHITECTURE_TO_IMPLEMENTATION",
                source_ecosystem="agnostic",
                target_ecosystem="*",
                source_node_types=[SemanticNodeType.ARCHITECTURE_COMPONENT],
                target_node_types=[SemanticNodeType.FRONTEND_COMPONENT, SemanticNodeType.BACKEND_SERVICE],
                supported_relations=[SemanticRelationType.IMPLEMENTS, SemanticRelationType.EXPOSES],
                schema_version="1.0.0",
                validation_rules=["Architecture component defines capability boundary"],
            )
        )

        # 3. TypeScript / React Frontend -> API Contract
        self.register_adapter(
            SemanticAdapter(
                adapter_id="TS_FRONTEND_TO_API",
                source_ecosystem="react",
                target_ecosystem="openapi",
                source_node_types=[SemanticNodeType.FRONTEND_COMPONENT],
                target_node_types=[SemanticNodeType.API_CONTRACT, SemanticNodeType.API_ENDPOINT],
                supported_relations=[SemanticRelationType.CONSUMES, SemanticRelationType.CALLS],
                schema_version="1.0.0",
                validation_rules=["Frontend component consumes route/method defined in API contract", "Type definitions match schema shape"],
            )
        )
        self.register_adapter(
            SemanticAdapter(
                adapter_id="VUE_FRONTEND_TO_API",
                source_ecosystem="vue",
                target_ecosystem="openapi",
                source_node_types=[SemanticNodeType.FRONTEND_COMPONENT],
                target_node_types=[SemanticNodeType.API_CONTRACT, SemanticNodeType.API_ENDPOINT],
                supported_relations=[SemanticRelationType.CONSUMES, SemanticRelationType.CALLS],
                schema_version="1.0.0",
                validation_rules=["Vue component consumes route/method defined in API contract"],
            )
        )
        self.register_adapter(
            SemanticAdapter(
                adapter_id="GENERIC_TS_TO_API",
                source_ecosystem="typescript",
                target_ecosystem="openapi",
                source_node_types=[SemanticNodeType.FRONTEND_COMPONENT],
                target_node_types=[SemanticNodeType.API_CONTRACT, SemanticNodeType.API_ENDPOINT],
                supported_relations=[SemanticRelationType.CONSUMES, SemanticRelationType.CALLS],
                schema_version="1.0.0",
                validation_rules=["Generic TypeScript caller consumes API contract"],
            )
        )

        # 4. API Contract -> Backend Service (FastAPI / Django / Node / Express / Java)
        self.register_adapter(
            SemanticAdapter(
                adapter_id="API_TO_FASTAPI_BACKEND",
                source_ecosystem="openapi",
                target_ecosystem="fastapi",
                source_node_types=[SemanticNodeType.API_CONTRACT, SemanticNodeType.API_ENDPOINT],
                target_node_types=[SemanticNodeType.BACKEND_SERVICE],
                supported_relations=[SemanticRelationType.SERVES, SemanticRelationType.IMPLEMENTS],
                schema_version="1.0.0",
                validation_rules=["FastAPI router implements OpenAPI route and payload"],
            )
        )
        self.register_adapter(
            SemanticAdapter(
                adapter_id="API_TO_DJANGO_BACKEND",
                source_ecosystem="openapi",
                target_ecosystem="django",
                source_node_types=[SemanticNodeType.API_CONTRACT, SemanticNodeType.API_ENDPOINT],
                target_node_types=[SemanticNodeType.BACKEND_SERVICE],
                supported_relations=[SemanticRelationType.SERVES, SemanticRelationType.IMPLEMENTS],
                schema_version="1.0.0",
                validation_rules=["Django view / DRF viewset handles API route"],
            )
        )
        self.register_adapter(
            SemanticAdapter(
                adapter_id="API_TO_NODE_BACKEND",
                source_ecosystem="openapi",
                target_ecosystem="node",
                source_node_types=[SemanticNodeType.API_CONTRACT, SemanticNodeType.API_ENDPOINT],
                target_node_types=[SemanticNodeType.BACKEND_SERVICE],
                supported_relations=[SemanticRelationType.SERVES, SemanticRelationType.IMPLEMENTS],
                schema_version="1.0.0",
                validation_rules=["Node.js handler serves OpenAPI contract"],
            )
        )
        self.register_adapter(
            SemanticAdapter(
                adapter_id="API_TO_EXPRESS_BACKEND",
                source_ecosystem="openapi",
                target_ecosystem="express",
                source_node_types=[SemanticNodeType.API_CONTRACT, SemanticNodeType.API_ENDPOINT],
                target_node_types=[SemanticNodeType.BACKEND_SERVICE],
                supported_relations=[SemanticRelationType.SERVES, SemanticRelationType.IMPLEMENTS],
                schema_version="1.0.0",
                validation_rules=["Express route serves OpenAPI contract"],
            )
        )
        self.register_adapter(
            SemanticAdapter(
                adapter_id="API_TO_JAVA_BACKEND",
                source_ecosystem="openapi",
                target_ecosystem="java",
                source_node_types=[SemanticNodeType.API_CONTRACT, SemanticNodeType.API_ENDPOINT],
                target_node_types=[SemanticNodeType.BACKEND_SERVICE],
                supported_relations=[SemanticRelationType.SERVES, SemanticRelationType.IMPLEMENTS],
                schema_version="1.0.0",
                validation_rules=["Java Spring/JAX-RS controller implements contract"],
            )
        )
        self.register_adapter(
            SemanticAdapter(
                adapter_id="API_TO_PYTHON_GENERIC",
                source_ecosystem="openapi",
                target_ecosystem="python",
                source_node_types=[SemanticNodeType.API_CONTRACT, SemanticNodeType.API_ENDPOINT],
                target_node_types=[SemanticNodeType.BACKEND_SERVICE],
                supported_relations=[SemanticRelationType.SERVES, SemanticRelationType.IMPLEMENTS],
                schema_version="1.0.0",
                validation_rules=["Python service handles API contract"],
            )
        )

        # 5. Backend Service -> Persistence & Data Models
        self.register_adapter(
            SemanticAdapter(
                adapter_id="BACKEND_TO_PERSISTENCE",
                source_ecosystem="*",
                target_ecosystem="sql",
                source_node_types=[SemanticNodeType.BACKEND_SERVICE],
                target_node_types=[SemanticNodeType.PERSISTENCE_OPERATION, SemanticNodeType.DATA_MODEL],
                supported_relations=[SemanticRelationType.PERSISTS, SemanticRelationType.CALLS],
                schema_version="1.0.0",
                validation_rules=["Backend repository executes query/ORM against data model"],
            )
        )
        self.register_adapter(
            SemanticAdapter(
                adapter_id="PERSISTENCE_TO_MODEL",
                source_ecosystem="sql",
                target_ecosystem="sql",
                source_node_types=[SemanticNodeType.PERSISTENCE_OPERATION],
                target_node_types=[SemanticNodeType.DATA_MODEL],
                supported_relations=[SemanticRelationType.PERSISTS, SemanticRelationType.DEPENDS_ON],
                schema_version="1.0.0",
                validation_rules=["Operation operates on specific schema table/entity"],
            )
        )

        # 6. Testing -> Target Components
        self.register_adapter(
            SemanticAdapter(
                adapter_id="TEST_TO_TARGET",
                source_ecosystem="*",
                target_ecosystem="*",
                source_node_types=[SemanticNodeType.TEST],
                target_node_types=[
                    SemanticNodeType.FRONTEND_COMPONENT,
                    SemanticNodeType.BACKEND_SERVICE,
                    SemanticNodeType.API_CONTRACT,
                    SemanticNodeType.API_ENDPOINT,
                    SemanticNodeType.DATA_MODEL,
                ],
                supported_relations=[SemanticRelationType.VALIDATES, SemanticRelationType.TESTS],
                schema_version="1.0.0",
                validation_rules=["Test suite asserts behavior or contract compliance"],
            )
        )

        # 7. Browser Automation -> Frontend Component
        self.register_adapter(
            SemanticAdapter(
                adapter_id="BROWSER_TO_FRONTEND",
                source_ecosystem="playwright",
                target_ecosystem="*",
                source_node_types=[SemanticNodeType.BROWSER_SCENARIO],
                target_node_types=[SemanticNodeType.FRONTEND_COMPONENT, SemanticNodeType.REQUIREMENT],
                supported_relations=[SemanticRelationType.VALIDATES, SemanticRelationType.PROVES],
                schema_version="1.0.0",
                validation_rules=["Browser QA verifies rendered UI and user interaction"],
            )
        )
