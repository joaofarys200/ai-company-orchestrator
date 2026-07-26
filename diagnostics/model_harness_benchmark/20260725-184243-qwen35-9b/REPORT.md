# ModelHarness qwen3.5:9b Benchmark

- Version: `model_harness_qwen35_capabilities_v1`
- Model: `qwen3.5:9b`
- Cases passed: 7/8
- Calls passed: 14/16
- Exact-output reproducibility: 8/8 cases
- Workspace integrity unchanged: True

## Cases

| Case | Capability | Passed | Reproducible | Mean ms |
|---|---|---:|---:|---:|
| B01_LOCAL_CHOICE | constraint_based_choice | True | True | 10251 |
| B02_STRUCTURED_EXTRACTION | structured_extraction | True | True | 5386 |
| B03_REFERENCE_DISCIPLINE | reference_discipline | True | True | 2808 |
| B04_BOUNDED_CONTEXT | bounded_context_use | True | True | 2861 |
| B05_CODE_REASONING | code_reasoning | False | True | 4656 |
| B06_NEGATIVE_CONSTRAINTS | negative_constraint_following | True | True | 3799 |
| B07_TOOL_SELECTION | tool_selection | True | True | 3229 |
| B08_INSTRUCTION_HIERARCHY | instruction_hierarchy | True | True | 3987.5 |

## Observed limitations

- `B05_CODE_REASONING`: {"capability": "code_reasoning", "case_id": "B05_CODE_REASONING", "criteria_failures": [{"repetition": 1, "criterion": "empty_guard_present", "evidence": "minimal_fix='return values.reduce((sum, n) => sum + n, 0) / (values.length || 1);'"}, {"repetition": 2, "criterion": "empty_guard_present", "evidence": "minimal_fix='return values.reduce((sum, n) => sum + n, 0) / (values.length || 1);'"}], "validation_failures": []}

## Scope

- Synthetic, read-only prompts.
- No tools executed.
- No MissionState or workspace project mutation.
- No recovery retries.
- Results apply only to the recorded configuration and cases.
