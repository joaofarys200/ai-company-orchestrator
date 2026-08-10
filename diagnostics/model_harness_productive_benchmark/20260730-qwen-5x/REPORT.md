# Qwen3.5 9B Productive ModelHarness Benchmark

- Modelo: `qwen3.5:9b`
- Missoes completas: 15/20 (75.0%)
- Respostas estruturais validas: 120/120 (100.0%)
- Integridade do codigo fonte: inalterada
- Promocao: FAIL

## Cenarios

### S1_INSPECTION - Inspecao read-only

- Conclusao: 5/5 (100.0%)
- Finish prematuro: 0
- Tools invalidas: 0
- Repeticoes: 0
- Falhas de schema: 0
- Passos medios: 4.0
- Latencia media: 15.557s

### S2_SIMPLE_EDIT - Alteracao simples validada

- Conclusao: 5/5 (100.0%)
- Finish prematuro: 0
- Tools invalidas: 0
- Repeticoes: 0
- Falhas de schema: 0
- Passos medios: 7.0
- Latencia media: 28.875s

### S3_VALIDATION_FAILURE - Falha, correcao e reteste

- Conclusao: 0/5 (0.0%)
- Finish prematuro: 0
- Tools invalidas: 5
- Repeticoes: 0
- Falhas de schema: 0
- Passos medios: 6.0
- Latencia media: 27.732s

### S4_STATEFUL_DISCIPLINE - Disciplina stateful

- Conclusao: 5/5 (100.0%)
- Finish prematuro: 0
- Tools invalidas: 0
- Repeticoes: 0
- Falhas de schema: 0
- Passos medios: 7.0
- Latencia media: 29.788s

## Metricas Globais

- premature_finish: 0
- invalid_tools: 5
- repeated_calls: 0
- schema_failures: 0
- validation_runs: 15
- failed_validations: 0
- corrections_after_failure: 0
- false_successes: 0
- total_steps: 120
- total_latency_ms: 507419
- input_tokens: 72612
- output_tokens: 7266

## Criterios de Promocao

- completion_rate_at_least_80: False
- all_responses_structurally_valid: True
- zero_false_successes: True
- zero_incomplete_successes: True
- source_integrity_unchanged: True
- promoted: False
