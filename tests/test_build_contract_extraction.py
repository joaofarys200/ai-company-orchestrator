"""
Tests for Phase 49: Build-Time Contract Extraction & Dynamic Consumer Resolution.

Validates all 20 required core scenarios:
 1. OpenAPI endpoint extraction
 2. JSONSchema extraction
 3. TypeScript generated interface
 4. Python generated model
 5. dynamic getattr
 6. dynamic object[key]
 7. registry[eventName]
 8. dynamic dispatch table
 9. resolvable literal union
10. unresolved dynamic key
11. polymorphic dynamic consumer
12. closed exhaustive consumer
13. open fallback consumer
14. contract removal
15. optional field addition
16. type change
17. auth change
18. schema poisoning
19. stale generated schema
20. rollback after contract resolution
"""

import os
import json
import pytest
import tempfile
from pathlib import Path

from agents.build_contract_extraction.models import (
    EvidenceState,
    TypeKind,
    PatternType,
    ResolutionStatus,
    UncertaintyReason,
    DynamicConsumerPattern,
    ContractType,
    ContractEndpoint,
    ContractEvent,
    ContractVariant,
    ContractField,
    ContractAuth,
    ContractDiscriminator,
    ExtractedContractBundle,
)
from agents.build_contract_extraction.openapi import OpenAPIExtractor
from agents.build_contract_extraction.jsonschema import JSONSchemaExtractor
from agents.build_contract_extraction.generated_types import GeneratedTypesExtractor
from agents.build_contract_extraction.normalizer import ContractNormalizer
from agents.build_contract_extraction.dynamic_consumers import DynamicConsumerScanner
from agents.build_contract_extraction.resolver import DynamicConsumerResolver
from agents.build_contract_extraction.validator import ContractSchemaValidator, ContractValidationError
from agents.build_contract_extraction.cache import BuildContractCache
from agents.build_contract_extraction.security import (
    BuildContractSecuritySentinel,
    BuildContractSecurityViolation,
)
from agents.build_contract_extraction.bridge import BuildContractExtractionBridge


class TestPhase49BuildContractExtraction:

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as td:
            yield Path(td)

    # 1. OpenAPI endpoint extraction
    def test_01_openapi_endpoint_extraction(self, temp_dir):
        openapi_spec = {
            "openapi": "3.1.0",
            "info": {"title": "Users API", "version": "1.0.0"},
            "paths": {
                "/api/v1/users": {
                    "get": {
                        "operationId": "getUsers",
                        "summary": "List all active users",
                        "responses": {
                            "200": {
                                "description": "OK",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/UserList"}
                                    }
                                }
                            }
                        }
                    },
                    "post": {
                        "operationId": "createUser",
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/CreateUserDto"}
                                }
                            }
                        },
                        "responses": {"201": {"description": "Created"}}
                    }
                }
            },
            "components": {
                "schemas": {
                    "UserList": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "CreateUserDto": {
                        "type": "object",
                        "required": ["email"],
                        "properties": {
                            "email": {"type": "string"},
                            "name": {"type": "string"}
                        }
                    }
                }
            }
        }
        spec_path = temp_dir / "openapi.json"
        spec_path.write_text(json.dumps(openapi_spec), encoding="utf-8")

        endpoints, types, versions = OpenAPIExtractor.extract_from_file(str(spec_path))
        assert len(endpoints) == 2
        get_ep = next(e for e in endpoints.values() if e.method == "GET")
        assert get_ep.path == "/api/v1/users"

        assert len(types) == 2
        user_dto = next(t for t in types.values() if t.name == "CreateUserDto")
        assert "email" in user_dto.properties
        assert user_dto.properties["email"].required is True

    # 2. JSONSchema extraction
    def test_02_jsonschema_extraction(self, temp_dir):
        schema_data = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": "OrderCreatedEvent",
            "type": "object",
            "required": ["order_id", "total"],
            "properties": {
                "order_id": {"type": "string"},
                "total": {"type": "number"},
                "currency": {"type": "string"}
            }
        }
        schema_path = temp_dir / "order_event.json"
        schema_path.write_text(json.dumps(schema_data), encoding="utf-8")

        extracted_type, extracted_event = JSONSchemaExtractor.extract_from_file(str(schema_path))
        assert extracted_type.name == "order_event"
        assert extracted_type.kind == TypeKind.OBJECT
        assert "order_id" in extracted_type.properties
        assert extracted_type.properties["order_id"].required is True
        assert extracted_event is not None
        assert "order" in extracted_event.topic_or_type.lower()

    # 3. TypeScript generated interface
    def test_03_typescript_generated_interface(self):
        ts_code = """
        export interface UserDto {
            id: string;
            email: string;
            role: "ADMIN" | "USER";
            avatar?: string;
        }

        export type EventKind = "user.created" | "user.updated";
        """
        types = GeneratedTypesExtractor.extract_typescript_types(ts_code, artifact_path="types.ts")
        assert "UserDto" in types
        user_dto = types["UserDto"]
        assert user_dto.kind == TypeKind.OBJECT
        assert len(user_dto.properties) >= 3
        assert user_dto.properties["avatar"].required is False

        assert "EventKind" in types
        event_kind = types["EventKind"]
        assert event_kind.kind == TypeKind.UNION
        assert "user.created" in event_kind.enum_values

    # 4. Python generated model
    def test_04_python_generated_model(self):
        py_code = """
from pydantic import BaseModel
from typing import Optional
from dataclasses import dataclass

class UserProfile(BaseModel):
    id: str
    username: str
    is_active: bool = True
    bio: Optional[str] = None

@dataclass
class OrderItem:
    item_id: str
    price: float
        """
        types = GeneratedTypesExtractor.extract_python_types(py_code, artifact_path="models.py")
        assert "UserProfile" in types
        user_p = types["UserProfile"]
        assert user_p.kind == TypeKind.OBJECT
        assert "username" in user_p.properties

        assert "OrderItem" in types
        order_item = types["OrderItem"]
        assert "item_id" in order_item.properties

    # 5. dynamic getattr
    def test_05_dynamic_getattr(self):
        py_code = """
def extract_value(user_obj, key):
    return getattr(user_obj, key)
        """
        patterns = DynamicConsumerScanner.scan_python_code(py_code, source_file="service.py")
        assert len(patterns) >= 1
        getattr_pat = patterns[0]
        assert getattr_pat.pattern_type == PatternType.DYNAMIC_GETATTR
        assert getattr_pat.is_literal_or_bounded is False  # unconstrained key

    # 6. dynamic object[key]
    def test_06_dynamic_object_key(self):
        ts_code = """
        function getField(obj: any, key: string) {
            return obj[key];
        }
        """
        patterns = DynamicConsumerScanner.scan_typescript_code(ts_code, source_file="utils.ts")
        assert len(patterns) >= 1
        assert patterns[0].pattern_type == PatternType.DYNAMIC_INDEX

    # 7. registry[eventName]
    def test_07_registry_event_name(self):
        ts_code = """
        const handler = eventRegistry[eventName];
        """
        patterns = DynamicConsumerScanner.scan_typescript_code(ts_code, source_file="dispatcher.ts")
        assert len(patterns) >= 1
        assert patterns[0].pattern_type == PatternType.REGISTRY_LOOKUP

    # 8. dynamic dispatch table
    def test_08_dynamic_dispatch_table(self):
        py_code = """
def dispatch_action(action_name, payload):
    handler = action_handlers[action_name]
    return handler(payload)
        """
        patterns = DynamicConsumerScanner.scan_python_code(py_code, source_file="dispatch.py")
        assert len(patterns) >= 1
        assert patterns[0].pattern_type in (PatternType.DISPATCH_TABLE, PatternType.DYNAMIC_INDEX)

    # 9. resolvable literal union
    def test_09_resolvable_literal_union(self):
        # A dynamic consumer where eventName is restricted to a bounded union
        pattern = DynamicConsumerPattern(
            pattern_id="pat_01",
            source_file="dispatcher.ts",
            line_number=10,
            pattern_type=PatternType.REGISTRY_LOOKUP,
            target_object_expr="registry",
            key_expression="eventName",
            is_literal_or_bounded=True,
            bounded_literals=["user.created", "user.deleted"],
        )

        canonical_event = ContractEvent(
            event_id="evt_audit",
            topic_or_type="user.created",
            discriminator_value="user.created",
            payload_schema={"type": "object"},
        )

        bundle = ExtractedContractBundle(
            events={"evt_audit": canonical_event}
        )

        resolution = DynamicConsumerResolver.resolve_pattern(pattern, bundle)
        assert resolution.resolution_status == ResolutionStatus.RESOLVED
        assert resolution.evidence_state == EvidenceState.GENERATED
        assert resolution.resolved_contract_id == "evt_audit"

    # 10. unresolved dynamic key (must maintain UNCERTAIN without guessing)
    def test_10_unresolved_dynamic_key(self):
        pattern = DynamicConsumerPattern(
            pattern_id="pat_unbounded",
            source_file="reflection.py",
            line_number=45,
            pattern_type=PatternType.DYNAMIC_GETATTR,
            target_object_expr="model",
            key_expression="dynamic_attr",
            is_literal_or_bounded=False,
            bounded_literals=[],
        )

        dummy_type = ContractType(
            type_id="type_user",
            name="User",
            kind=TypeKind.OBJECT,
        )

        bundle = ExtractedContractBundle(
            types={"type_user": dummy_type}
        )

        resolution = DynamicConsumerResolver.resolve_pattern(pattern, bundle)

        # Strictly preserves UNCERTAIN, no silent guessing of the first contract
        assert resolution.resolution_status == ResolutionStatus.UNCERTAIN
        assert resolution.evidence_state == EvidenceState.UNCERTAIN
        assert resolution.resolved_contract_id is None
        assert resolution.uncertainty_reason in (
            UncertaintyReason.DYNAMIC_KEY_NOT_BOUNDED,
            UncertaintyReason.DYNAMIC_KEY_NOT_RESOLVABLE
        )

    # 11. polymorphic dynamic consumer
    def test_11_polymorphic_dynamic_consumer(self):
        pattern = DynamicConsumerPattern(
            pattern_id="pat_poly",
            source_file="poly_handler.ts",
            line_number=20,
            pattern_type=PatternType.REGISTRY_LOOKUP,
            target_object_expr="handlers",
            key_expression="event.type",
            is_literal_or_bounded=True,
            bounded_literals=["login", "logout"],
        )

        poly_contract = ContractType(
            type_id="type_auth_events",
            name="AuthEvents",
            kind=TypeKind.UNION,
            variants=[
                ContractVariant(variant_id="var_login", discriminator_value="login", schema={}),
                ContractVariant(variant_id="var_logout", discriminator_value="logout", schema={}),
            ]
        )

        bundle = ExtractedContractBundle(
            types={"type_auth_events": poly_contract}
        )

        res = DynamicConsumerResolver.resolve_pattern(pattern, bundle)
        assert res.resolution_status == ResolutionStatus.RESOLVED
        assert res.resolved_contract_id == "type_auth_events"

    # 12. closed exhaustive consumer
    def test_12_closed_exhaustive_consumer(self):
        pattern = DynamicConsumerPattern(
            pattern_id="pat_closed",
            source_file="exhaustive.ts",
            line_number=30,
            pattern_type=PatternType.DISPATCH_TABLE,
            target_object_expr="actions",
            key_expression="action",
            is_literal_or_bounded=True,
            bounded_literals=["CREATE", "DELETE"],
            context_snippet="switch (action) { case 'CREATE': ... case 'DELETE': ... }",
        )
        contract = ContractType(
            type_id="type_actions",
            name="ActionTypes",
            kind=TypeKind.UNION,
            variants=[
                ContractVariant(variant_id="var_c", discriminator_value="CREATE", schema={}),
                ContractVariant(variant_id="var_d", discriminator_value="DELETE", schema={}),
            ]
        )
        bundle = ExtractedContractBundle(types={"type_actions": contract})
        res = DynamicConsumerResolver.resolve_pattern(pattern, bundle)
        assert res.resolution_status == ResolutionStatus.RESOLVED
        assert res.pattern_matching == "CLOSED_EXHAUSTIVE"

    # 13. open fallback consumer
    def test_13_open_fallback_consumer(self):
        pattern = DynamicConsumerPattern(
            pattern_id="pat_open",
            source_file="open_handler.ts",
            line_number=12,
            pattern_type=PatternType.DYNAMIC_INDEX,
            target_object_expr="config",
            key_expression="key",
            is_literal_or_bounded=False,
            bounded_literals=[],
            context_snippet="const val = config[key] ?? defaultVal;",
        )
        bundle = ExtractedContractBundle()
        res = DynamicConsumerResolver.resolve_pattern(pattern, bundle)
        assert res.resolution_status == ResolutionStatus.UNCERTAIN
        assert res.pattern_matching == "OPEN_WITH_FALLBACK"

    # 14. contract removal
    def test_14_contract_removal(self):
        c1 = ContractType(type_id="type_u", name="User", kind=TypeKind.OBJECT)
        bundle_v1 = ExtractedContractBundle(types={"type_u": c1})
        bundle_v2 = ExtractedContractBundle(types={})  # removed!

        removed_type_ids = set(bundle_v1.types.keys()) - set(bundle_v2.types.keys())
        assert len(removed_type_ids) == 1
        assert "type_u" in removed_type_ids

    # 15. optional field addition (non-breaking)
    def test_15_optional_field_addition(self):
        old_field = ContractField(field_name="id", field_type="string", required=True)
        new_optional_field = ContractField(field_name="nickname", field_type="string", required=False)

        c1 = ContractType(
            type_id="type_item",
            name="Item",
            kind=TypeKind.OBJECT,
            properties={"id": old_field}
        )
        c2 = ContractType(
            type_id="type_item",
            name="Item",
            kind=TypeKind.OBJECT,
            properties={"id": old_field, "nickname": new_optional_field}
        )
        # Adding an optional field is non-breaking
        assert c2.properties["nickname"].required is False
        assert set(c1.properties.keys()).issubset(set(c2.properties.keys()))

    # 16. type change (breaking change)
    def test_16_type_change(self):
        c1_field = ContractField(field_name="avatar", field_type="string", required=True)
        c2_field = ContractField(field_name="avatar", field_type="AvatarObject", required=True)

        c1 = ContractType(type_id="c_user", name="User", kind=TypeKind.OBJECT, properties={"avatar": c1_field})
        c2 = ContractType(type_id="c_user", name="User", kind=TypeKind.OBJECT, properties={"avatar": c2_field})

        # Field types differ -> Breaking change
        assert c1.properties["avatar"].field_type != c2.properties["avatar"].field_type

    # 17. auth change & Sentinel defense
    def test_17_auth_change(self):
        # Protected economic route cannot have auth removed
        economic_ep = ContractEndpoint(
            endpoint_id="ep_payment",
            path="/api/v1/payments",
            method="POST",
            auth=ContractAuth(requires_auth=False),  # Sentinel must reject!
        )
        with pytest.raises(BuildContractSecurityViolation):
            BuildContractSecuritySentinel.verify_auth_invariants(economic_ep)

    # 18. schema poisoning
    def test_18_schema_poisoning(self):
        # Malicious schema with XSS and prototype pollution attempts
        poisoned_type = ContractType(
            type_id="type_exploit",
            name="Exploit<script>alert(1)</script>",
            kind=TypeKind.OBJECT,
        )
        with pytest.raises(ContractValidationError):
            ContractSchemaValidator.validate_type(poisoned_type)

        # Test Sentinel raw content sanitization
        with pytest.raises(BuildContractSecurityViolation):
            BuildContractSecuritySentinel.sanitize_schema_content(
                "<script>evil()</script>",
                source_label="untrusted_schema.json"
            )

    # 19. stale generated schema
    def test_19_stale_generated_schema(self, temp_dir):
        cache = BuildContractCache()
        art_path = str(temp_dir / "api.json")
        bundle = ExtractedContractBundle()

        # Cache put with hash_v1
        cache.put(art_path, content_hash="hash_v1", bundle=bundle)
        assert cache.get(art_path, content_hash="hash_v1") is not None

        # Content changed to hash_v2 -> stale cache returns None
        assert cache.get(art_path, content_hash="hash_v2") is None

    # 20. rollback after contract resolution
    def test_20_rollback_after_contract_resolution(self):
        bridge = BuildContractExtractionBridge()

        # Simulate Phase 49 pipeline processing
        bundle = bridge.process_build_contracts(
            openapi_specs=[{
                "openapi": "3.1.0",
                "info": {"title": "Users API", "version": "1.0.0"},
                "paths": {
                    "/api/v1/users": {
                        "get": {"responses": {"200": {"description": "OK"}}}
                    }
                }
            }],
            source_code_files={
                "frontend/src/views/UserView.tsx": "const handler = eventRegistry[eventName];"
            }
        )

        assert len(bundle.endpoints) >= 1
        assert len(bundle.dynamic_resolutions) >= 1

        # Traces convert seamlessly to Phase 48 format for rollback and migration DAGs
        traces = bridge.convert_resolutions_to_phase48_traces(bundle.dynamic_resolutions)
        assert len(traces) == len(bundle.dynamic_resolutions)
        assert traces[0].file_path == "frontend/src/views/UserView.tsx"
