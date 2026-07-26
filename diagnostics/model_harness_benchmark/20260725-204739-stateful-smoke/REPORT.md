# ModelHarness Stateful Tool Loop and Project Reasoning Benchmark

## 1. Resumo executivo
- Mode: `smoke`; model: `qwen3.5:9b`; passed repetitions: 2/10.
- Decision: `MODEL_HARNESS_STATEFUL_BENCHMARK_IMPLEMENTED_NOT_VALIDATED`.

## 2. Arquitetura do benchmark
- ModelHarness -> validated decision -> read-only fixture tool -> normalized observation -> ContextBuilder -> next decision.

## 3. Diferencas entre v1 e v2
- v1 measures isolated calls; v2 measures bounded state transitions and stop behavior.

## 4. Cenarios implementados
- 10 scenario definitions across groups A-G.

## 5. Tool registry read-only
- list_files, read_file, search_text, inspect_symbol, query_fixture_index and finish.

## 6. Seguranca da sandbox
- Temporary fixture copies; absolute paths, traversal and symlinks are blocked.

## 7. Stateful execution
- 10 steps; 8 live model calls and 2 deterministic fault-injection steps.
- All 8 live calls returned no output after approximately 300 seconds.

## 8. Context management
- Recorded context range for live calls: 915-2085 chars.

## 9. Progress detection
- Stop reasons: `{"COMPLETED": 1, "REPEATED_TOOL_CALL": 1, "VALIDATION_FAILED": 8}`.

## 10. Recovery exercitada
- Repetitions using recovery: 1.

## 11. Project reasoning
- multi_file_reasoning: `FAILED`.

## 12. Context scaling
- context_scaling: `FAILED`.

## 13. Planeamento curto
- short_horizon_planning: `FAILED`.

## 14. Documento e investigacao
- closed_source_research: `FAILED`; evidence_based_document_generation: `FAILED`.

## 15. Perfil de capacidades

| Capability | Status | Confidence | Passed | Failed |
|---|---|---:|---:|---:|
| closed_source_research | FAILED | 0.000 | 0 | 1 |
| constraint_retention | FAILED | 0.000 | 0 | 1 |
| context_scaling | FAILED | 0.000 | 0 | 1 |
| evidence_based_document_generation | FAILED | 0.000 | 0 | 1 |
| multi_file_reasoning | FAILED | 0.000 | 0 | 2 |
| recovery_after_failure | DEMONSTRATED_PRELIMINARY | 0.333 | 2 | 0 |
| short_horizon_planning | FAILED | 0.000 | 0 | 1 |
| stateful_tool_use | FAILED | 0.000 | 0 | 1 |

## 16. Performance
- Live-call median latency: 300360.5 ms; P95: 300392.2 ms.
- No live completion tokens were returned, so throughput is not measurable.
- Total wall time: 2428.291 seconds.

## 17. Reprodutibilidade
- Exact scenario traces: 0/0.

## 18. Integridade
- Unchanged: `True`; integrity_failed: `False`.

## 19. Testes
- See repository test evidence reported with this run.

## 20. Regressoes
- Infrastructure errors: 0.
- Post-run accounting correction: live failures with null token usage were initially excluded from aggregate model-call metrics. Raw traces were not modified.

## 21. Limitacoes factuais
- Fixtures are synthetic and closed-source.
- Read-only tool execution does not demonstrate productive tools.
- FULL mode was not executed unless explicitly shown by mode.
- Model results apply only to the recorded configuration.
- Eight live provider calls returned no output at the configured 300-second timeout.
- The original run did not persist provider exception types; the runner was corrected afterwards to persist stage, type and message hash.
- STANDARD was not executed because SMOKE failed.

## 22. Proximo passo recomendado
- Review failed scenario evidence before any productive integration.

## 23. Decisao
`MODEL_HARNESS_STATEFUL_BENCHMARK_IMPLEMENTED_NOT_VALIDATED`
