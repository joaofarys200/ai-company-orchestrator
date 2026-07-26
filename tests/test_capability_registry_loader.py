from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.capability_registry import (
    BenchmarkEvidenceKind,
    BenchmarkHashMismatchError,
    BenchmarkLoader,
    CapabilityId,
    CapabilityStatus,
    ModelProfileBuilder,
    default_capability_catalog,
)
from tests.capability_registry_fixtures import (
    MODEL_NAME,
    create_bounded_run,
    create_provider_diagnostic,
    create_stateful_run,
    write_json,
)


class BenchmarkLoaderTest(unittest.TestCase):
    def test_loads_bounded_aliases_metadata_and_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            create_bounded_run(root, declared_artifact_hash=True)

            result = BenchmarkLoader(root).load()[0]

            self.assertEqual(result.model_name, MODEL_NAME)
            self.assertEqual(result.provider, "ollama")
            self.assertEqual(result.architecture, "qwen35")
            self.assertEqual(result.parameter_count, 9653104368)
            self.assertEqual(result.quantization, "Q4_K_M")
            self.assertEqual(result.context_length, 262144)
            self.assertTrue(result.evidence.declared_hash_verified)
            self.assertTrue(result.evidence.report_artifact.endswith("REPORT.md"))
            self.assertEqual(len(result.evidence.report_sha256), 64)
            self.assertEqual(len(result.evidence.artifact_hashes), 3)
            self.assertTrue(
                all(
                    len(value) == 64
                    for value in result.evidence.artifact_hashes.values()
                )
            )
            statuses = {
                item.capability_id: item.status
                for item in result.capabilities
            }
            self.assertEqual(
                statuses[CapabilityId.LOCALIZED_CODE_REASONING],
                CapabilityStatus.DEMONSTRATED_PRELIMINARY,
            )
            self.assertEqual(
                statuses[CapabilityId.TOOL_SELECTION_WITHOUT_EXECUTION],
                CapabilityStatus.DEMONSTRATED_PRELIMINARY,
            )

    def test_loads_stateful_status_without_promotion(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            create_stateful_run(root)

            result = BenchmarkLoader(root).load()[0]

            statuses = {
                item.capability_id: item.status
                for item in result.capabilities
            }
            self.assertEqual(
                statuses[CapabilityId.STATEFUL_TOOL_USE],
                CapabilityStatus.FAILED,
            )
            self.assertEqual(
                statuses[CapabilityId.RECOVERY_AFTER_FAILURE],
                CapabilityStatus.DEMONSTRATED_PRELIMINARY,
            )
            self.assertTrue(result.evidence.declared_hash_verified)

    def test_provider_diagnostic_is_history_not_capability_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            create_provider_diagnostic(root)

            result = BenchmarkLoader(root).load()[0]

            self.assertEqual(
                result.evidence.kind,
                BenchmarkEvidenceKind.PROVIDER_DIAGNOSTIC,
            )
            self.assertEqual(result.capabilities, ())
            self.assertEqual(
                result.evidence.decision,
                "MODEL_HARNESS_STATEFUL_PROVIDER_PATH_DIAGNOSED",
            )

    def test_configuration_hash_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = create_stateful_run(root)
            profile_path = run_dir / "capability_profile.json"
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            profile["configuration_hash"] = "f" * 64
            write_json(profile_path, profile)

            with self.assertRaises(BenchmarkHashMismatchError):
                BenchmarkLoader(root).load()

    def test_declared_artifact_hash_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = create_bounded_run(
                root,
                declared_artifact_hash=True,
            )
            manifest_path = run_dir / "manifest.json"
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            manifest["artifact_hashes"]["summary.json"] = "0" * 64
            write_json(manifest_path, manifest)

            with self.assertRaises(BenchmarkHashMismatchError):
                BenchmarkLoader(root).load()

    def test_profile_uses_latest_evidence_and_keeps_history(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            create_bounded_run(
                root,
                run_name="older",
                completed_at="2026-01-01T10:00:00+00:00",
                code_passed=False,
            )
            create_bounded_run(
                root,
                run_name="newer",
                completed_at="2026-01-02T10:00:00+00:00",
                code_passed=True,
            )
            results = BenchmarkLoader(root).load()

            profile = ModelProfileBuilder(
                default_capability_catalog()
            ).build(results)[0]
            capability = profile.capability(
                CapabilityId.LOCALIZED_CODE_REASONING
            )

            self.assertIsNotNone(capability)
            self.assertEqual(
                capability.status,
                CapabilityStatus.DEMONSTRATED_PRELIMINARY,
            )
            self.assertEqual(len(capability.evidence), 2)

    def test_advertised_features_are_not_promoted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            create_bounded_run(root)
            results = BenchmarkLoader(root).load()

            profile = ModelProfileBuilder(
                default_capability_catalog()
            ).build(results)[0]

            self.assertIn("vision", profile.advertised_features)
            self.assertIsNone(profile.capability(CapabilityId.VISION))
            self.assertIsNone(profile.capability(CapabilityId.THINKING))


if __name__ == "__main__":
    unittest.main()
