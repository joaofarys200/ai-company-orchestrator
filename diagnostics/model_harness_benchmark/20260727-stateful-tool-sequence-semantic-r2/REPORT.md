# Stateful Tool Sequence Semantic Diagnostic

- Scenario: `A01_FIND_RELEVANT_FILE` only.
- Model: `qwen3.5:9b`.
- Semantic Context Builder: not integrated.
- Tool execution: temporary read-only FixtureSandbox only.

| Variant | Strict 2/2 | Recovered 2/2 | Calls | Early FINISH | Repeats | Timeouts |
|---|---:|---:|---:|---:|---:|---:|
| S01_CURRENT | no | no | 4 | 2 | 0 | 0 |
| S02_EXPLICIT_STATE | no | no | 4 | 2 | 0 | 0 |
| S03_PREVALIDATION | no | no | 4 | 2 | 0 | 0 |
| S04_CONDITIONED_SCHEMA | no | no | 4 | 0 | 0 | 0 |
| S05_SEMANTIC_RETRY | no | no | 6 | 4 | 0 | 0 |

- Decision: `STATEFUL_TOOL_SEQUENCE_SEMANTICS_NOT_VALIDATED`.
- Conclusion: No tested representation produced the required sequence twice.
- Integrity unchanged: `True`.

The diagnostic never selects a tool for the model. S04 only removes FINISH from the legal schema while obligations remain. S05 reports one concrete rejection and next obligation without executing it.
