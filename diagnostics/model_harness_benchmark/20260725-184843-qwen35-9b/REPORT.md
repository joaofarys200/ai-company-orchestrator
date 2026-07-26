# ModelHarness qwen3.5:9b Benchmark

- Version: `model_harness_qwen35_capabilities_v1`
- Model: `qwen3.5:9b`
- Cases passed: 8/8
- Calls passed: 16/16
- Exact-output reproducibility: 8/8 cases
- Workspace integrity unchanged: True

## Cases

| Case | Capability | Passed | Reproducible | Mean ms |
|---|---|---:|---:|---:|
| B01_LOCAL_CHOICE | constraint_based_choice | True | True | 7474 |
| B02_STRUCTURED_EXTRACTION | structured_extraction | True | True | 4383.5 |
| B03_REFERENCE_DISCIPLINE | reference_discipline | True | True | 2564.5 |
| B04_BOUNDED_CONTEXT | bounded_context_use | True | True | 2425.5 |
| B05_CODE_REASONING | code_reasoning | True | True | 3851.5 |
| B06_NEGATIVE_CONSTRAINTS | negative_constraint_following | True | True | 3112.5 |
| B07_TOOL_SELECTION | tool_selection | True | True | 2791 |
| B08_INSTRUCTION_HIERARCHY | instruction_hierarchy | True | True | 3423.5 |

## Observed limitations

- None within this bounded synthetic benchmark. This does not demonstrate general capability.

## Scope

- Synthetic, read-only prompts.
- No tools executed.
- No MissionState or workspace project mutation.
- No recovery retries.
- Results apply only to the recorded configuration and cases.
