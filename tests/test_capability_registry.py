from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from backend.capability_registry import (
    Capability,
    CapabilityId,
    CapabilityRegistry,
    CapabilityRegistryNotLoadedError,
    CapabilityStatus,
    CompatibilityRegistry,
    CompatibilityTarget,
    DeterministicCapabilitySelector,
    REGISTRY_VERSION,
    SelectionReason,
    UnknownCapabilityError,
    default_capability_catalog,
)
from tests.capability_registry_fixtures import (
    MODEL_NAME,
    create_bounded_run,
    create_provider_diagnostic,
    create_stateful_run,
)


class CapabilityRegistryTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        create_bounded_run(self.root, declared_artifact_hash=True)
        create_stateful_run(self.root)
        create_provider_diagnostic(self.root)
        self.registry = CapabilityRegistry(self.root)
        self.snapshot = self.registry.load()

    def tearDown(self):
        self.temporary.cleanup()

    def test_catalog_contains_every_v1_capability(self):
        catalog = default_capability_catalog()

        self.assertEqual(set(catalog), set(CapabilityId))
        self.assertGreaterEqual(len(catalog), 20)

    def test_aliases_are_explicit_and_unknown_ids_are_rejected(self):
        code = self.registry.get_capability("code_reasoning")
        tool = self.registry.get_capability("tool_selection")

        self.assertEqual(code.id, CapabilityId.LOCALIZED_CODE_REASONING)
        self.assertEqual(
            tool.id,
            CapabilityId.TOOL_SELECTION_WITHOUT_EXECUTION,
        )
        with self.assertRaises(UnknownCapabilityError):
            self.registry.get_capability("probably_supported")

    def test_api_requires_explicit_load(self):
        registry = CapabilityRegistry(self.root)

        with self.assertRaises(CapabilityRegistryNotLoadedError):
            registry.list_models()

    def test_model_profile_is_factual_and_complete(self):
        profile = self.registry.get_model(MODEL_NAME)

        self.assertEqual(profile.provider, "ollama")
        self.assertEqual(profile.architecture, "qwen35")
        self.assertEqual(profile.parameter_count, 9653104368)
        self.assertEqual(profile.quantization, "Q4_K_M")
        self.assertEqual(profile.context_length, 262144)
        self.assertEqual(len(profile.benchmarks), 3)
        self.assertIn("vision", profile.advertised_features)

    def test_supports_is_fail_closed(self):
        demonstrated = self.registry.supports(
            MODEL_NAME,
            CapabilityId.STRUCTURED_EXTRACTION,
        )
        failed = self.registry.supports(
            MODEL_NAME,
            CapabilityId.STATEFUL_TOOL_USE,
        )
        absent = self.registry.supports(
            MODEL_NAME,
            CapabilityId.VISION,
        )
        unknown_model = self.registry.supports(
            "missing:model",
            CapabilityId.STRUCTURED_EXTRACTION,
        )

        self.assertTrue(demonstrated.supported)
        self.assertEqual(
            demonstrated.status,
            CapabilityStatus.DEMONSTRATED_PRELIMINARY,
        )
        self.assertFalse(failed.supported)
        self.assertEqual(failed.status, CapabilityStatus.FAILED)
        self.assertFalse(absent.supported)
        self.assertEqual(
            absent.reason,
            SelectionReason.NO_BENCHMARK_EVIDENCE,
        )
        self.assertFalse(unknown_model.supported)
        self.assertEqual(
            unknown_model.reason,
            SelectionReason.MODEL_NOT_FOUND,
        )

    def test_every_non_demonstrated_status_is_fail_closed(self):
        profile = self.registry.get_model(MODEL_NAME)
        source = profile.capability(CapabilityId.STRUCTURED_EXTRACTION)
        for status in (
            CapabilityStatus.UNKNOWN,
            CapabilityStatus.NOT_DEMONSTRATED,
            CapabilityStatus.FAILED,
            CapabilityStatus.UNSUPPORTED,
        ):
            capability = replace(source, status=status)
            altered_profile = replace(
                profile,
                capabilities=tuple(
                    capability
                    if item.id is capability.id
                    else item
                    for item in profile.capabilities
                ),
            )
            selector = DeterministicCapabilitySelector(
                {MODEL_NAME: altered_profile},
                CompatibilityRegistry(),
            )

            decision = selector.supports(
                MODEL_NAME,
                CapabilityId.STRUCTURED_EXTRACTION,
            )

            self.assertFalse(decision.supported, status.value)

    def test_capability_contract_requires_benchmark_evidence(self):
        definition = self.registry.get_capability(
            CapabilityId.VISION
        )

        with self.assertRaises(ValueError):
            Capability(
                id=definition.id,
                display_name=definition.display_name,
                description=definition.description,
                status=CapabilityStatus.UNKNOWN,
                confidence=0.0,
                limitations=(),
                requirements=(),
                evidence=(),
                configurations=(),
                last_verified="",
            )

    def test_configuration_filter_is_exact(self):
        profile = self.registry.get_model(MODEL_NAME)
        capability = profile.capability(CapabilityId.STRUCTURED_EXTRACTION)
        known_hash = capability.configurations[0].configuration_hash

        self.assertTrue(
            self.registry.supports(
                MODEL_NAME,
                CapabilityId.STRUCTURED_EXTRACTION,
                configuration_hash=known_hash,
            ).supported
        )
        rejected = self.registry.supports(
            MODEL_NAME,
            CapabilityId.STRUCTURED_EXTRACTION,
            configuration_hash="f" * 64,
        )
        self.assertFalse(rejected.supported)
        self.assertEqual(
            rejected.reason,
            SelectionReason.CONFIGURATION_NOT_TESTED,
        )

    def test_compatibility_rules_are_explicit(self):
        research = self.registry.requires(
            CompatibilityTarget.RESEARCH_EXECUTOR
        )
        tool = self.registry.compatible_with(
            MODEL_NAME,
            CompatibilityTarget.TOOL_EXECUTOR,
        )

        self.assertEqual(
            tuple(item.capability_id for item in research),
            (
                CapabilityId.STRUCTURED_EXTRACTION,
                CapabilityId.REFERENCE_DISCIPLINE,
                CapabilityId.BOUNDED_CONTEXT_USE,
            ),
        )
        self.assertFalse(tool.compatible)
        self.assertEqual(
            tool.decisions[0].capability_id,
            CapabilityId.STATEFUL_TOOL_USE,
        )

    def test_selection_is_deterministic_and_not_ranked(self):
        selected = self.registry.select_models(
            [CapabilityId.STRUCTURED_EXTRACTION]
        )
        rejected = self.registry.select_models(
            [CapabilityId.STATEFUL_TOOL_USE]
        )

        self.assertEqual(selected.selected_models, (MODEL_NAME,))
        self.assertEqual(selected.rejected_models, ())
        self.assertEqual(rejected.selected_models, ())
        self.assertEqual(rejected.rejected_models, (MODEL_NAME,))

    def test_snapshot_is_reproducible_and_hash_valid(self):
        with tempfile.TemporaryDirectory() as output_dir:
            first_path = Path(output_dir) / "first.json"
            second_path = Path(output_dir) / "second.json"
            first = self.registry.export_snapshot(first_path)
            second = self.registry.export_snapshot(second_path)

            self.assertEqual(first, second)
            self.assertEqual(first_path.read_bytes(), second_path.read_bytes())
            self.assertEqual(
                first.content_sha256,
                first.computed_content_sha256(),
            )
            self.assertTrue(
                first.snapshot_version.startswith(REGISTRY_VERSION)
            )
            parsed = json.loads(first_path.read_text(encoding="utf-8"))
            self.assertEqual(
                parsed["content_sha256"],
                first.content_sha256,
            )

    def test_reload_keeps_snapshot_identity(self):
        original = self.snapshot
        reloaded = self.registry.reload()

        self.assertEqual(original.snapshot_version, reloaded.snapshot_version)
        self.assertEqual(original.content_sha256, reloaded.content_sha256)

    def test_validator_detects_snapshot_tampering(self):
        tampered = replace(self.snapshot, content_sha256="f" * 64)

        result = self.registry.validator.validate(
            catalog=self.registry.catalog,
            profiles=self.registry.list_models(),
            rules=self.registry.compatibility.rules(),
            snapshot=tampered,
        )

        self.assertFalse(result.valid)
        self.assertIn(
            "SNAPSHOT_HASH_MISMATCH",
            {item.code for item in result.issues},
        )

    def test_telemetry_contains_no_prompts(self):
        self.registry.supports(
            MODEL_NAME,
            CapabilityId.STRUCTURED_EXTRACTION,
        )

        serialized = json.dumps(
            self.registry.telemetry.snapshot(),
            sort_keys=True,
        ).lower()
        self.assertNotIn("system_prompt", serialized)
        self.assertNotIn("user_prompt", serialized)


class RealCapabilityRegistryArtifactsTest(unittest.TestCase):
    def test_current_repository_artifacts_load_without_ollama(self):
        repo_root = Path(__file__).resolve().parents[1]
        registry = CapabilityRegistry(repo_root / "diagnostics")

        snapshot = registry.load()
        profile = registry.get_model("qwen3.5:9b")

        self.assertEqual(len(snapshot.models), 1)
        self.assertGreaterEqual(len(profile.benchmarks), 3)
        self.assertEqual(
            profile.capability(
                CapabilityId.STATEFUL_TOOL_USE
            ).status,
            CapabilityStatus.FAILED,
        )
        self.assertFalse(
            registry.supports(
                "qwen3.5:9b",
                CapabilityId.VISION,
            ).supported
        )
        self.assertTrue(registry.validate().valid)


if __name__ == "__main__":
    unittest.main()
