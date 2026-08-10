import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.model_harness import (
    ModelResponse,
    ModelResponseStatus,
    ModelUsage,
    ValidationResult,
    ValidationStatus,
)

from scripts.model_harness_productive_benchmark import (
    IsolatedProject,
    MODEL,
    RECOVERY_REGRESSION_TYPE,
    RECOVERY_SCENARIO_ID,
    SCENARIOS,
    classify_recovery_outcome,
    completion_ready,
    expected_next_tool,
    response_schema,
    run_repetition,
    sha256_file,
    source_integrity_snapshot,
    system_prompt,
    validate_decision,
)


class ProductiveModelHarnessBenchmarkTest(unittest.TestCase):
    @staticmethod
    def _recovery_scenario():
        return next(
            scenario
            for scenario in SCENARIOS
            if scenario.scenario_id == RECOVERY_SCENARIO_ID
        )

    @staticmethod
    def _apply_valid_first_change(project):
        project.execute("read_file", {"path": "src/tasks.js"})
        return project.execute("apply_patch", {
            "path": "src/tasks.js",
            "old_text": (
                "  const normalized = normalizeTask(value);\n"
                "  return [...tasks, normalized];"
            ),
            "new_text": (
                "  const normalized = normalizeTask(value);\n"
                "  if (!normalized) {\n"
                "    return tasks;\n"
                "  }\n"
                "  return [...tasks, normalized];"
            ),
        })

    @staticmethod
    def _repair_injected_regression(project):
        project.execute("read_file", {"path": "src/tasks.js"})
        return project.execute("apply_patch", {
            "path": "src/tasks.js",
            "old_text": "export function normalizeTask(value {",
            "new_text": "export function normalizeTask(value) {",
        })

    def test_fixture_applies_minimal_patch_and_runs_real_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            project = IsolatedProject(root, "empty_task")
            project.create()
            project.execute("read_file", {"path": "src/tasks.js"})
            result = project.execute("apply_patch", {
                "path": "src/tasks.js",
                "old_text": (
                    "  const normalized = normalizeTask(value);\n"
                    "  return [...tasks, normalized];"
                ),
                "new_text": (
                    "  const normalized = normalizeTask(value);\n"
                    "  if (!normalized) {\n"
                    "    return tasks;\n"
                    "  }\n"
                    "  return [...tasks, normalized];"
                ),
            })
            validation = project.execute("run_validation", {})
            diff = project.execute("show_diff", {})

            self.assertTrue(result["changed"])
            self.assertTrue(validation["passed"])
            self.assertEqual(
                [item["exit_code"] for item in validation["commands"]],
                [0, 0],
            )
            self.assertEqual(diff["changed_paths"], ["src/tasks.js"])
            self.assertEqual(project.changed_paths(), ["src/tasks.js"])

    def test_failed_validation_can_be_repaired_and_retested(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            project = IsolatedProject(root, "empty_task")
            project.create()
            project.execute("read_file", {"path": "src/tasks.js"})
            project.execute("apply_patch", {
                "path": "src/tasks.js",
                "old_text": "  return [...tasks, normalized];",
                "new_text": "  return (",
            })
            failed = project.execute("run_validation", {})
            reread = project.execute(
                "read_file",
                {"path": "src/tasks.js"},
            )
            project.execute("apply_patch", {
                "path": "src/tasks.js",
                "old_text": "  return (",
                "new_text": (
                    "  if (!normalized) {\n"
                    "    return tasks;\n"
                    "  }\n"
                    "  return [...tasks, normalized];"
                ),
            })
            passed = project.execute("run_validation", {})

            self.assertFalse(failed["passed"])
            self.assertIn("return (", reread["content"])
            self.assertTrue(passed["passed"])
            self.assertTrue(all(
                item["exit_code"] == 0
                for item in passed["commands"]
            ))
            self.assertTrue(project.failed_validation_observed)
            self.assertTrue(project.success_after_failure)

    def test_recovery_regression_produces_real_nonzero_exit_code(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            project = IsolatedProject(
                root,
                "empty_task",
                RECOVERY_REGRESSION_TYPE,
            )
            project.create()
            self._apply_valid_first_change(project)

            failed = project.execute("run_validation", {})

            self.assertFalse(failed["passed"])
            self.assertTrue(any(
                item["exit_code"] != 0
                for item in failed["commands"]
            ))
            self.assertEqual(project.regression_injection_count, 1)
            self.assertEqual(
                project.validation_state,
                "FAILED_VALIDATION",
            )
            self.assertTrue(project.failed_validation_observed)

    def test_recovery_regression_is_injected_once_and_retest_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            project = IsolatedProject(
                root,
                "empty_task",
                RECOVERY_REGRESSION_TYPE,
            )
            project.create()
            self._apply_valid_first_change(project)
            failed = project.execute("run_validation", {})
            self._repair_injected_regression(project)
            passed = project.execute("run_validation", {})

            self.assertFalse(failed["passed"])
            self.assertTrue(passed["passed"])
            self.assertEqual(project.regression_injection_count, 1)
            self.assertEqual(len(project.validation_runs), 2)
            self.assertTrue(project.success_after_failure)
            self.assertTrue(project.materially_distinct_recovery_patch())
            self.assertTrue(project.recovery_contract_satisfied())
            self.assertEqual(project.validation_state, "RECOVERED")

    def test_regression_is_confined_to_temporary_fixture(self):
        repository_before = source_integrity_snapshot()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            canary = Path(temporary) / "outside.txt"
            canary.write_bytes(b"outside fixture\n")
            canary_hash = sha256_file(canary)
            project = IsolatedProject(
                root,
                "empty_task",
                RECOVERY_REGRESSION_TYPE,
            )
            project.create()
            self._apply_valid_first_change(project)
            project.execute("run_validation", {})

            self.assertEqual(sha256_file(canary), canary_hash)
            self.assertEqual(
                project.regression_metadata["path"],
                "src/tasks.js",
            )
        self.assertEqual(
            source_integrity_snapshot(),
            repository_before,
        )

    def test_failed_state_is_persisted_before_recovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = IsolatedProject(
                Path(temporary) / "project",
                "empty_task",
                RECOVERY_REGRESSION_TYPE,
            )
            project.create()
            self._apply_valid_first_change(project)
            project.execute("run_validation", {})
            project.execute("read_file", {"path": "src/tasks.js"})
            self._repair_injected_regression(project)
            project.execute("run_validation", {})

            states = [
                item["state"]
                for item in project.validation_state_history
            ]
            self.assertIn("FAILED_VALIDATION", states)
            self.assertIn("FAILURE_EVIDENCE_READ", states)
            self.assertIn("CORRECTION_APPLIED", states)
            self.assertEqual(states[-1], "RECOVERED")

    def test_finish_is_rejected_while_validation_is_failed(self):
        scenario = self._recovery_scenario()
        with tempfile.TemporaryDirectory() as temporary:
            project = IsolatedProject(
                Path(temporary) / "project",
                scenario.test_mode,
                scenario.regression_mode,
            )
            project.create()
            self._apply_valid_first_change(project)
            project.execute("run_validation", {})
            sequence = list(scenario.required_sequence[:5])
            error = validate_decision(
                {
                    "action": "FINISH",
                    "tool_name": "finish",
                    "arguments": {},
                    "conclusion": "done",
                    "evidence_refs": [],
                },
                scenario,
                project,
                sequence,
            )

            self.assertIn("expected next tool", error)
            self.assertFalse(completion_ready(
                scenario,
                project,
                sequence,
            ))
            self.assertNotIn(
                "finish",
                response_schema(False)["properties"]["tool_name"]["enum"],
            )

    def test_retest_is_required_after_corrective_change(self):
        scenario = self._recovery_scenario()
        with tempfile.TemporaryDirectory() as temporary:
            project = IsolatedProject(
                Path(temporary) / "project",
                scenario.test_mode,
                scenario.regression_mode,
            )
            project.create()
            self._apply_valid_first_change(project)
            project.execute("run_validation", {})
            self._repair_injected_regression(project)
            sequence = list(scenario.required_sequence[:7])

            self.assertFalse(completion_ready(
                scenario,
                project,
                sequence,
            ))
            self.assertIsNone(project.latest_validation_passed)
            self.assertEqual(
                project.validation_state,
                "CORRECTION_APPLIED",
            )

    def test_failed_retest_allows_another_bounded_recovery_cycle(self):
        scenario = self._recovery_scenario()
        with tempfile.TemporaryDirectory() as temporary:
            project = IsolatedProject(
                Path(temporary) / "project",
                scenario.test_mode,
                scenario.regression_mode,
            )
            project.create()
            self._apply_valid_first_change(project)
            project.execute("run_validation", {})
            project.execute("read_file", {"path": "src/tasks.js"})
            project.execute("apply_patch", {
                "path": "src/tasks.js",
                "old_text": "    return tasks;",
                "new_text": "    return [...tasks];",
            })
            second_failure = project.execute("run_validation", {})
            sequence = list(scenario.required_sequence[:8])

            self.assertFalse(second_failure["passed"])
            self.assertEqual(
                expected_next_tool(scenario, project, sequence),
                "read_file",
            )

            project.execute("read_file", {"path": "src/tasks.js"})
            project.execute("apply_patch", {
                "path": "src/tasks.js",
                "old_text": "export function normalizeTask(value {",
                "new_text": "export function normalizeTask(value) {",
            })
            passed = project.execute("run_validation", {})
            project.execute("show_diff", {})
            sequence.extend([
                "read_file",
                "apply_patch",
                "run_validation",
                "show_diff",
            ])

            self.assertTrue(passed["passed"])
            self.assertTrue(completion_ready(
                scenario,
                project,
                sequence,
            ))
            self.assertEqual(
                expected_next_tool(scenario, project, sequence),
                "finish",
            )

    def test_missing_real_failure_is_inconclusive(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = IsolatedProject(
                Path(temporary) / "project",
                "empty_task",
                RECOVERY_REGRESSION_TYPE,
            )
            project.create()
            status, reason = classify_recovery_outcome(project, "FAIL")

            self.assertEqual(status, "INCONCLUSIVE")
            self.assertIn("not injected", reason)

    def test_model_that_ignores_real_failure_receives_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = IsolatedProject(
                Path(temporary) / "project",
                "empty_task",
                RECOVERY_REGRESSION_TYPE,
            )
            project.create()
            self._apply_valid_first_change(project)
            project.execute("run_validation", {})

            status, reason = classify_recovery_outcome(project, "FAIL")

            self.assertEqual(status, "FAIL")
            self.assertIn("did not recover", reason)

    def test_recovery_preserves_unrelated_fixture_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            project = IsolatedProject(
                root,
                "empty_task",
                RECOVERY_REGRESSION_TYPE,
            )
            project.create()
            unrelated_before = sha256_file(root / "README.md")
            self._apply_valid_first_change(project)
            project.execute("run_validation", {})
            self._repair_injected_regression(project)
            project.execute("run_validation", {})

            self.assertEqual(
                sha256_file(root / "README.md"),
                unrelated_before,
            )
            self.assertEqual(project.changed_paths(), ["src/tasks.js"])

    def test_model_prompt_does_not_reveal_controlled_injection(self):
        scenario = self._recovery_scenario()
        visible_text = (
            system_prompt() + " " + scenario.objective
        ).lower()
        for forbidden in (
            "injected regression",
            "intentional failure",
            "deliberately invalid",
            "first validation must fail",
        ):
            self.assertNotIn(forbidden, visible_text)


class ProductiveRecoveryPersistenceTest(
    unittest.IsolatedAsyncioTestCase
):
    async def test_recovery_run_persists_failure_and_recovery_events(self):
        scenario = next(
            item
            for item in SCENARIOS
            if item.scenario_id == RECOVERY_SCENARIO_ID
        )
        decisions = [
            {
                "action": "CALL_TOOL",
                "tool_name": "list_files",
                "arguments": {"path": "."},
                "conclusion": "",
                "evidence_refs": [],
            },
            {
                "action": "CALL_TOOL",
                "tool_name": "inspect_symbol",
                "arguments": {"name": "addTask"},
                "conclusion": "",
                "evidence_refs": [],
            },
            {
                "action": "CALL_TOOL",
                "tool_name": "read_file",
                "arguments": {"path": "src/tasks.js"},
                "conclusion": "",
                "evidence_refs": [],
            },
            {
                "action": "CALL_TOOL",
                "tool_name": "apply_patch",
                "arguments": {
                    "path": "src/tasks.js",
                    "old_text": (
                        "  const normalized = normalizeTask(value);\n"
                        "  return [...tasks, normalized];"
                    ),
                    "new_text": (
                        "  const normalized = normalizeTask(value);\n"
                        "  if (!normalized) {\n"
                        "    return tasks;\n"
                        "  }\n"
                        "  return [...tasks, normalized];"
                    ),
                },
                "conclusion": "",
                "evidence_refs": [],
            },
            {
                "action": "CALL_TOOL",
                "tool_name": "run_validation",
                "arguments": {},
                "conclusion": "",
                "evidence_refs": [],
            },
            {
                "action": "CALL_TOOL",
                "tool_name": "read_file",
                "arguments": {"path": "src/tasks.js"},
                "conclusion": "",
                "evidence_refs": [],
            },
            {
                "action": "CALL_TOOL",
                "tool_name": "apply_patch",
                "arguments": {
                    "path": "src/tasks.js",
                    "old_text": (
                        "export function normalizeTask(value {"
                    ),
                    "new_text": (
                        "export function normalizeTask(value) {"
                    ),
                },
                "conclusion": "",
                "evidence_refs": [],
            },
            {
                "action": "CALL_TOOL",
                "tool_name": "run_validation",
                "arguments": {},
                "conclusion": "",
                "evidence_refs": [],
            },
            {
                "action": "CALL_TOOL",
                "tool_name": "show_diff",
                "arguments": {},
                "conclusion": "",
                "evidence_refs": [],
            },
            {
                "action": "FINISH",
                "tool_name": "finish",
                "arguments": {},
                "conclusion": "Validated correction completed.",
                "evidence_refs": ["project:final-diff"],
            },
        ]
        cursor = 0

        async def scripted_step(**kwargs):
            nonlocal cursor
            decision = decisions[cursor]
            cursor += 1
            raw = json.dumps(decision)
            return (
                ModelResponse(
                    request_id=f"request-{cursor}",
                    status=ModelResponseStatus.SUCCEEDED,
                    raw_text=raw,
                    structured_output=decision,
                    usage=ModelUsage(
                        input_tokens=10,
                        output_tokens=5,
                        total_tokens=15,
                    ),
                    provider="ollama",
                    model=MODEL,
                    latency_ms=1,
                    validation=ValidationResult(
                        status=ValidationStatus.PASSED,
                        structured_output=decision,
                    ),
                ),
                0.001,
            )

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifacts"
            root = output / "fixture" / "project"
            with patch(
                "scripts.model_harness_productive_benchmark."
                "execute_model_step",
                side_effect=scripted_step,
            ):
                result = await run_repetition(
                    scenario,
                    1,
                    root,
                    MODEL,
                    artifact_dir=output,
                )

            log_path = output / "logs" / "run-01.jsonl"
            log_text = log_path.read_text(encoding="utf-8")
            events = [
                json.loads(line)["event"]
                for line in log_text.splitlines()
            ]
            self.assertEqual(result.status, "PASS")
            self.assertTrue(result.recovery["failure_persisted"])
            self.assertTrue(result.recovery["recovery_persisted"])
            self.assertIn("validation_failed", events)
            self.assertIn("validation_recovered", events)
            self.assertIn("run_completed", events)
            self.assertNotIn("raw_response", log_text)
            self.assertTrue(
                result.recovery["outside_fixture_unchanged"]
            )
            self.assertTrue(
                (output / "diffs" / "run-01.patch").is_file()
            )

    def test_finish_is_not_representable_before_completion(self):
        schema = response_schema(False)
        self.assertEqual(
            schema["properties"]["action"]["enum"],
            ["CALL_TOOL"],
        )
        self.assertNotIn(
            "finish",
            schema["properties"]["tool_name"]["enum"],
        )
        self.assertIn(
            "finish",
            response_schema(True)["properties"]["tool_name"]["enum"],
        )
        self.assertIn(
            "FINISH",
            response_schema(True)["properties"]["action"]["enum"],
        )

    def test_sequence_validator_does_not_choose_a_tool_for_model(self):
        scenario = SCENARIOS[0]
        with tempfile.TemporaryDirectory() as temporary:
            project = IsolatedProject(
                Path(temporary) / "project",
                scenario.test_mode,
            )
            project.create()
            error = validate_decision(
                {
                    "action": "CALL_TOOL",
                    "tool_name": "read_file",
                    "arguments": {"path": "src/tasks.js"},
                },
                scenario,
                project,
                [],
            )
        self.assertIn("expected next tool", error)

    def test_finish_requires_supported_conclusion(self):
        scenario = SCENARIOS[0]
        with tempfile.TemporaryDirectory() as temporary:
            project = IsolatedProject(
                Path(temporary) / "project",
                scenario.test_mode,
            )
            project.create()
            project.known_references.add("src/tasks.js:full")
            error = validate_decision(
                {
                    "action": "FINISH",
                    "tool_name": "finish",
                    "arguments": {},
                    "conclusion": "",
                    "evidence_refs": ["src/tasks.js:full"],
                },
                scenario,
                project,
                ["list_files", "inspect_symbol", "read_file"],
            )
        self.assertEqual(
            error,
            "finish requires a non-empty conclusion",
        )


if __name__ == "__main__":
    unittest.main()
