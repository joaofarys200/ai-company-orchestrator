# ModelHarness qwen3.5:9b Benchmark

- Version: `model_harness_qwen35_capabilities_v1`
- Model: `qwen3.5:9b`
- Cases passed: 1/1
- Calls passed: 1/1
- Exact-output reproducibility: 1/1 cases
- Workspace integrity unchanged: True

## Cases

| Case | Capability | Passed | Reproducible | Mean ms |
|---|---|---:|---:|---:|
| B07_TOOL_SELECTION | tool_selection | True | True | 14009 |

## Observed limitations

- None within this bounded synthetic benchmark. This does not demonstrate general capability.

## Scope

- Synthetic, read-only prompts.
- No tools executed.
- No MissionState or workspace project mutation.
- No recovery retries.
- Results apply only to the recorded configuration and cases.
