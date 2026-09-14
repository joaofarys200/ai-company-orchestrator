"""
JARVIS OS — Phase 49: OpenAPI Contract Extractor
Extracts canonical endpoints, schemas, polymorphic discriminators, and auth from OpenAPI specs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agents.build_contract_extraction.models import (
    ArtifactProvenance,
    ContractAuth,
    ContractDiscriminator,
    ContractEndpoint,
    ContractField,
    ContractType,
    ContractVariant,
    ContractVersion,
    SourceType,
    TypeKind,
)
from agents.build_contract_extraction.provenance import ProvenanceTracker


class OpenAPIExtractor:
    """
    Extracts deterministic canonical contracts from OpenAPI 3.0/3.1 specs.
    Strictly validates schema before ingestion; invalid specs raise explicit errors.
    """

    @classmethod
    def validate_spec(cls, spec: dict[str, Any]) -> None:
        """Validates minimum structural validity of an OpenAPI specification."""
        if not isinstance(spec, dict):
            raise ValueError("OpenAPI specification must be a dictionary.")
        if "openapi" not in spec and "swagger" not in spec:
            raise ValueError("Invalid OpenAPI specification: missing 'openapi' or 'swagger' version tag.")
        if "paths" not in spec:
            raise ValueError("Invalid OpenAPI specification: missing 'paths' section.")

    @classmethod
    def extract_from_dict(
        cls,
        spec: dict[str, Any],
        artifact_path: str = "openapi.json",
    ) -> Tuple[dict[str, ContractEndpoint], dict[str, ContractType], dict[str, ContractVersion]]:
        """
        Extracts endpoints, types, and version metadata from a validated OpenAPI specification dictionary.
        """
        cls.validate_spec(spec)

        endpoints: dict[str, ContractEndpoint] = {}
        types: dict[str, ContractType] = {}
        versions: dict[str, ContractVersion] = {}

        version_str = spec.get("info", {}).get("version", "1.0.0")
        spec_hash = ProvenanceTracker.compute_content_hash(spec)

        # 1. Extract Components / Schemas -> Canonical ContractTypes
        schemas = spec.get("components", {}).get("schemas", {})
        for schema_name, schema_def in schemas.items():
            t = cls._extract_type(
                type_name=schema_name,
                schema_def=schema_def,
                artifact_path=artifact_path,
                pointer=f"#/components/schemas/{schema_name}",
            )
            types[t.type_id] = t

        # 2. Extract Paths & Methods -> Canonical ContractEndpoints
        paths = spec.get("paths", {})
        for path_str, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method_str, op_item in path_item.items():
                if method_str.lower() not in ("get", "post", "put", "patch", "delete", "options", "head"):
                    continue
                if not isinstance(op_item, dict):
                    continue

                endpoint = cls._extract_endpoint(
                    path=path_str,
                    method=method_str,
                    op=op_item,
                    version=version_str,
                    artifact_path=artifact_path,
                    pointer=f"#/paths/{path_str}/{method_str}",
                )
                endpoints[endpoint.endpoint_id] = endpoint

                # Track version node
                v_node = ContractVersion(
                    contract_id=endpoint.endpoint_id,
                    version=version_str,
                    content_hash=ProvenanceTracker.compute_content_hash(op_item),
                    status="VALIDATED",
                    source_type=SourceType.GENERATED_OPENAPI,
                )
                versions[endpoint.endpoint_id] = v_node

        return endpoints, types, versions

    @classmethod
    def extract_from_file(
        cls,
        file_path: str | Path,
    ) -> Tuple[dict[str, ContractEndpoint], dict[str, ContractType], dict[str, ContractVersion]]:
        """Loads a JSON or YAML OpenAPI file and extracts canonical contracts."""
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"OpenAPI file does not exist: {p}")

        content = p.read_text(encoding="utf-8")
        try:
            spec = json.loads(content)
        except json.JSONDecodeError:
            try:
                import yaml  # type: ignore
                spec = yaml.safe_load(content)
            except Exception as e:
                raise ValueError(f"Failed to parse OpenAPI file as JSON or YAML: {e}")

        return cls.extract_from_dict(spec, artifact_path=str(p))

    @classmethod
    def _extract_type(
        cls,
        type_name: str,
        schema_def: dict[str, Any],
        artifact_path: str,
        pointer: str,
    ) -> ContractType:
        """Translates an OpenAPI schema definition into a canonical ContractType."""
        prov = ProvenanceTracker.create_provenance(
            source_type=SourceType.GENERATED_OPENAPI,
            artifact_path=artifact_path,
            json_pointer=pointer,
            content=schema_def,
        )

        kind = TypeKind.OBJECT
        if "enum" in schema_def:
            kind = TypeKind.ENUM
        elif "oneOf" in schema_def or "anyOf" in schema_def:
            kind = TypeKind.UNION
        elif schema_def.get("type") == "array":
            kind = TypeKind.ARRAY
        elif schema_def.get("type") in ("string", "integer", "number", "boolean"):
            kind = TypeKind.SCALAR

        properties: dict[str, ContractField] = {}
        props_dict = schema_def.get("properties", {})
        required_list = schema_def.get("required", [])

        for field_name, field_def in props_dict.items():
            f_type = field_def.get("type", "string") if isinstance(field_def, dict) else "string"
            if "$ref" in field_def:
                f_type = field_def["$ref"].split("/")[-1]
            is_req = field_name in required_list
            f_prov = ProvenanceTracker.create_provenance(
                source_type=SourceType.GENERATED_OPENAPI,
                artifact_path=artifact_path,
                json_pointer=f"{pointer}/properties/{field_name}",
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

        # Polymorphic variants and discriminators
        variants: list[ContractVariant] = []
        discriminator: Optional[ContractDiscriminator] = None

        disc_dict = schema_def.get("discriminator")
        if isinstance(disc_dict, dict):
            disc_field = disc_dict.get("propertyName", "type")
            disc_mapping = disc_dict.get("mapping", {})
            discriminator = ContractDiscriminator(
                field=disc_field,
                location="BODY",
                mapping=disc_mapping,
            )

        union_items = schema_def.get("oneOf") or schema_def.get("anyOf") or []
        for idx, item_def in enumerate(union_items):
            if isinstance(item_def, dict):
                v_name = item_def.get("title", f"{type_name}_variant_{idx}")
                ref_target = item_def.get("$ref", "").split("/")[-1]
                if ref_target:
                    v_name = ref_target
                variants.append(ContractVariant(
                    variant_id=f"var_{type_name}_{v_name}",
                    discriminator_value=v_name,
                    schema=item_def,
                    required_fields=item_def.get("required", []),
                    forbidden_fields=[],
                    provenance=prov,
                ))

        return ContractType(
            type_id=f"type_{type_name}",
            name=type_name,
            kind=kind,
            properties=properties,
            variants=variants,
            discriminator=discriminator,
            enum_values=schema_def.get("enum", []),
            language="agnostic",
            provenance=prov,
        )

    @classmethod
    def _extract_endpoint(
        cls,
        path: str,
        method: str,
        op: dict[str, Any],
        version: str,
        artifact_path: str,
        pointer: str,
    ) -> ContractEndpoint:
        """Translates an OpenAPI operation item into a canonical ContractEndpoint."""
        prov = ProvenanceTracker.create_provenance(
            source_type=SourceType.GENERATED_OPENAPI,
            artifact_path=artifact_path,
            json_pointer=pointer,
            content=op,
        )

        op_id = op.get("operationId")
        clean_path = path.replace("/", "_").strip("_")
        endpoint_id = op_id or f"{method.lower()}_{clean_path}"

        # Request schema
        req_body = op.get("requestBody", {})
        req_schema = None
        if isinstance(req_body, dict):
            content_dict = req_body.get("content", {}).get("application/json", {})
            req_schema = content_dict.get("schema")

        # Response schema (priority: 200, 201, default)
        responses = op.get("responses", {})
        resp_schema = None
        for code in ("200", "201", "default"):
            if code in responses and isinstance(responses[code], dict):
                content_dict = responses[code].get("content", {}).get("application/json", {})
                if "schema" in content_dict:
                    resp_schema = content_dict["schema"]
                    break

        # Auth
        security = op.get("security", [])
        requires_auth = len(security) > 0
        auth_scheme = "Bearer" if requires_auth else "None"
        auth = ContractAuth(requires_auth=requires_auth, auth_scheme=auth_scheme)

        return ContractEndpoint(
            endpoint_id=endpoint_id,
            path=path,
            method=method.upper(),
            request_schema=req_schema,
            response_schema=resp_schema,
            parameters=op.get("parameters", []),
            auth=auth,
            version=version,
            provenance=prov,
        )
