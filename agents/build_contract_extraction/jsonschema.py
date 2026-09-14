"""
JARVIS OS — Phase 49: JSON Schema Extractor
Extracts canonical types, events, and discriminators from standalone JSON Schema definitions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agents.build_contract_extraction.models import (
    ArtifactProvenance,
    ContractDiscriminator,
    ContractEvent,
    ContractField,
    ContractType,
    ContractVariant,
    SourceType,
    TypeKind,
)
from agents.build_contract_extraction.provenance import ProvenanceTracker


class JSONSchemaExtractor:
    """
    Extracts deterministic canonical contracts from JSON Schema files.
    Ideal for event-driven architectures, queue message schemas, and DTO definitions.
    """

    @classmethod
    def validate_schema(cls, schema: dict[str, Any]) -> None:
        """Validates JSON Schema minimal structure."""
        if not isinstance(schema, dict):
            raise ValueError("JSON Schema must be a dictionary.")
        if "type" not in schema and "oneOf" not in schema and "anyOf" not in schema and "$schema" not in schema:
            raise ValueError("Invalid JSON Schema: missing 'type', 'oneOf', 'anyOf', or '$schema'.")

    @classmethod
    def extract_from_dict(
        cls,
        schema: dict[str, Any],
        schema_name: str,
        artifact_path: str = "schema.json",
        is_event: bool = False,
    ) -> Tuple[ContractType, Optional[ContractEvent]]:
        """Extracts a canonical ContractType and optional ContractEvent from a JSON Schema dictionary."""
        cls.validate_schema(schema)

        prov = ProvenanceTracker.create_provenance(
            source_type=SourceType.JSONSCHEMA,
            artifact_path=artifact_path,
            json_pointer="#",
            content=schema,
        )

        kind = TypeKind.OBJECT
        if "enum" in schema:
            kind = TypeKind.ENUM
        elif "oneOf" in schema or "anyOf" in schema:
            kind = TypeKind.UNION
        elif schema.get("type") == "array":
            kind = TypeKind.ARRAY
        elif schema.get("type") in ("string", "integer", "number", "boolean"):
            kind = TypeKind.SCALAR

        properties: dict[str, ContractField] = {}
        props_dict = schema.get("properties", {})
        required_list = schema.get("required", [])

        for field_name, field_def in props_dict.items():
            f_type = field_def.get("type", "string") if isinstance(field_def, dict) else "string"
            is_req = field_name in required_list
            f_prov = ProvenanceTracker.create_provenance(
                source_type=SourceType.JSONSCHEMA,
                artifact_path=artifact_path,
                json_pointer=f"#/properties/{field_name}",
                content=field_def,
            )
            properties[field_name] = ContractField(
                field_name=field_name,
                field_type=f_type,
                required=is_req,
                nullable=field_def.get("nullable", False) if isinstance(field_def, dict) else False,
                default_value=field_def.get("default", None) if isinstance(field_def, dict) else None,
                description=field_def.get("description", "") if isinstance(field_def, dict) else "",
                provenance=f_prov,
            )

        # Discriminators & Polymorphic variants
        variants: list[ContractVariant] = []
        discriminator: Optional[ContractDiscriminator] = None

        disc_def = schema.get("discriminator")
        if isinstance(disc_def, dict):
            discriminator = ContractDiscriminator(
                field=disc_def.get("propertyName", "type"),
                location="BODY",
                mapping=disc_def.get("mapping", {}),
            )

        union_items = schema.get("oneOf") or schema.get("anyOf") or []
        for idx, item_def in enumerate(union_items):
            if isinstance(item_def, dict):
                v_title = item_def.get("title", f"{schema_name}_var_{idx}")
                variants.append(ContractVariant(
                    variant_id=f"var_{schema_name}_{v_title}",
                    discriminator_value=v_title,
                    schema=item_def,
                    required_fields=item_def.get("required", []),
                    forbidden_fields=[],
                    provenance=prov,
                ))

        contract_type = ContractType(
            type_id=f"type_{schema_name}",
            name=schema_name,
            kind=kind,
            properties=properties,
            variants=variants,
            discriminator=discriminator,
            enum_values=schema.get("enum", []),
            language="agnostic",
            provenance=prov,
        )

        contract_event: Optional[ContractEvent] = None
        if is_event or "event" in schema_name.lower():
            disc_val = schema.get("title", schema_name)
            contract_event = ContractEvent(
                event_id=f"evt_{schema_name}",
                topic_or_type=schema_name,
                discriminator_value=disc_val,
                payload_schema=schema,
                version="1.0.0",
                provenance=prov,
            )

        return contract_type, contract_event

    @classmethod
    def extract_from_file(
        cls,
        file_path: str | Path,
        schema_name: Optional[str] = None,
        is_event: bool = False,
    ) -> Tuple[ContractType, Optional[ContractEvent]]:
        """Loads and extracts a JSON Schema from a file."""
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"JSON Schema file not found: {p}")

        content = p.read_text(encoding="utf-8")
        schema = json.loads(content)
        name = schema_name or p.stem
        return cls.extract_from_dict(schema, schema_name=name, artifact_path=str(p), is_event=is_event)
