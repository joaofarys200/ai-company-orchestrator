# Stateful Tool Sequence Semantic Diagnostic

- Scenario: `A01_FIND_RELEVANT_FILE` only.
- Model: `qwen3.5:9b`.
- Semantic Context Builder: not integrated.
- Tool execution: temporary read-only FixtureSandbox only.

| Variant | Strict 2/2 | Recovered 2/2 | Calls | Early FINISH | Repeats | Timeouts |
|---|---:|---:|---:|---:|---:|---:|
| S04_CONDITIONED_SCHEMA | yes | yes | 8 | 0 | 0 | 0 |

- Decision: `STATEFUL_TOOL_SEQUENCE_SEMANTICS_VALIDATED`.
- Conclusion: The contract-conditioned transition schema was the first sufficient mechanism.
- Integrity unchanged: `True`.

The diagnostic never executes productive tools. S04 represents the single legal transition and public reference contract in the JSON schema. S05 reports one concrete rejection and next obligation without executing it.
