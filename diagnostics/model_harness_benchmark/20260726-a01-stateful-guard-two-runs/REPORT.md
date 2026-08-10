# ModelHarness Stateful Tool Loop and Project Reasoning Benchmark

## 1. Resumo executivo
- Mode: `standard`; model: `qwen3.5:9b`; passed repetitions: 0/2.
- Decision: `MODEL_HARNESS_STATEFUL_CAPABILITIES_PARTIALLY_VALIDATED`.

## 2. Arquitetura do benchmark
- ModelHarness -> validated decision -> read-only fixture tool -> normalized observation -> ContextBuilder -> next decision.

## 3. Diferencas entre v1 e v2
- v1 measures isolated calls; v2 measures bounded state transitions and stop behavior.

## 4. Cenarios implementados
- 1 scenario definitions across groups A-G.

## 5. Tool registry read-only
- list_files, read_file, search_text, inspect_symbol, query_fixture_index and finish.

## 6. Seguranca da sandbox
- Temporary fixture copies; absolute paths, traversal and symlinks are blocked.

## 7. Stateful execution
- 4 steps; 4 real model calls.

## 8. Context management
- Recorded context range: 2044-2193 chars.

## 9. Progress detection
- Stop reasons: `{"VALIDATION_FAILED": 2}`.

## 10. Recovery exercitada
- Repetitions using recovery: 0.

## 11. Project reasoning
- multi_file_reasoning: `NOT_RUN`.

## 12. Context scaling
- context_scaling: `NOT_RUN`.

## 13. Planeamento curto
- short_horizon_planning: `NOT_RUN`.

## 14. Documento e investigacao
- closed_source_research: `NOT_RUN`; evidence_based_document_generation: `NOT_RUN`.

## 15. Perfil de capacidades

| Capability | Status | Confidence | Passed | Failed |
|---|---|---:|---:|---:|
| stateful_tool_use | FAILED | 0.000 | 0 | 2 |

## 16. Performance
- Median latency: 6550.0 ms; P95: 16924.3 ms; mean throughput: 19.013 tokens/s.

## 17. Reprodutibilidade
- Exact scenario traces: 1/1.

## 18. Integridade
- Unchanged: `True`; integrity_failed: `False`.

## 19. Testes
- See repository test evidence reported with this run.

## 20. Regressoes
- Infrastructure errors: 0.

## 21. Limitacoes factuais
- Fixtures are synthetic and closed-source.
- Read-only tool execution does not demonstrate productive tools.
- FULL mode was not executed unless explicitly shown by mode.
- Model results apply only to the recorded configuration.

## 22. Proximo passo recomendado
- Review failed scenario evidence before any productive integration.

## 23. Decisao
`MODEL_HARNESS_STATEFUL_CAPABILITIES_PARTIALLY_VALIDATED`
