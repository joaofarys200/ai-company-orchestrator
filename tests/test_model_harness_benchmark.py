import tempfile
import unittest
from pathlib import Path

from scripts.model_harness_benchmark import (
    SYNTHETIC_SECRET,
    _assert_output_location,
    benchmark_cases,
    evaluate,
)


class ModelHarnessBenchmarkDefinitionTest(unittest.TestCase):
    def test_cases_are_unique_synthetic_and_side_effect_free(self):
        cases = benchmark_cases()

        self.assertEqual(len(cases), 8)
        self.assertEqual(
            len({item.case_id for item in cases}),
            len(cases),
        )
        for case in cases:
            self.assertTrue(case.schema)
            self.assertTrue(case.system_prompt)
            self.assertTrue(case.user_prompt)
            self.assertNotIn("workspace/projects", case.user_prompt)
            self.assertNotIn("MissionState", case.user_prompt)

    def test_output_is_restricted_to_diagnostics_area(self):
        allowed = Path(
            "diagnostics",
            "model_harness_benchmark",
            "test-run",
        )
        _assert_output_location(allowed)

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError):
                _assert_output_location(Path(temp_dir))

    def test_security_evaluator_requires_refusal_without_secret(self):
        passed = evaluate(
            "instruction_hierarchy",
            {"refused": True, "reason": "Cannot disclose it."},
            '{"refused":true,"reason":"Cannot disclose it."}',
        )
        failed = evaluate(
            "instruction_hierarchy",
            {"refused": True, "reason": SYNTHETIC_SECRET},
            SYNTHETIC_SECRET,
        )

        self.assertTrue(all(item["passed"] for item in passed))
        self.assertFalse(all(item["passed"] for item in failed))

    def test_code_evaluator_accepts_equivalent_empty_array_guards(self):
        explicit = evaluate(
            "code_reasoning",
            {
                "bug_code": "EMPTY_COLLECTION_DIVISION",
                "minimal_fix": (
                    "if (values.length === 0) return 0; "
                    "return values.reduce((sum, n) => sum + n, 0) "
                    "/ values.length;"
                ),
            },
            "",
        )
        fallback = evaluate(
            "code_reasoning",
            {
                "bug_code": "EMPTY_COLLECTION_DIVISION",
                "minimal_fix": (
                    "return values.reduce((sum, n) => sum + n, 0) "
                    "/ (values.length || 1);"
                ),
            },
            "",
        )

        self.assertTrue(all(item["passed"] for item in explicit))
        self.assertTrue(all(item["passed"] for item in fallback))


if __name__ == "__main__":
    unittest.main()
