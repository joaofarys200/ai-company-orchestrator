# Qwen3.5 9B Productive ModelHarness Benchmark

## 1. Problema do cenário anterior

O cenário anterior pedia ao modelo que introduzisse deliberadamente uma falha sintática. O Qwen aplicou uma solução válida à primeira tentativa nas cinco execuções.

O antigo resultado 0/5 é inconclusivo para recuperação: nenhuma validação realmente falhou, portanto o ciclo de diagnóstico e reteste nunca foi exercitado.

## 2. Novo desenho

A missão é uma alteração normal em `addTask`. Depois da primeira alteração real do modelo e imediatamente antes da primeira validação, o controlador altera apenas a cópia temporária de `src/tasks.js`:

- Original: `export function normalizeTask(value) {`
- Regressão: `export function normalizeTask(value {`

O comando real `node --check src/tasks.js` deve devolver código diferente de zero. A injeção ocorre uma única vez e os seus metadados nunca entram no estado apresentado ao modelo.

## 3. Garantias de isolamento

- Diretório temporário novo por run.
- Paths resolvidos e confinados à fixture.
- Snapshot SHA-256 do código produtivo antes e depois de cada run.
- Hash independente do ficheiro `README.md` não relacionado.
- Sem rede, dependências ou tools fora da fixture.
- Decisões obtidas pelo ModelHarness e provider Ollama produtivos.

## 4. Resumo executivo

- Modelo: `qwen3.5:9b`
- Missoes completas: 15/20 (75.0%)
- Respostas estruturais validas: 130/130 (100.0%)
- Integridade do codigo fonte: inalterada
- Promocao: FAIL
- Decisão: `QWEN_NOT_PROMOTED`
- Baseline válido: `C:/Users/joaor/Desktop/ai-company-orchestrator/diagnostics/model_harness_productive_benchmark/20260730-qwen-5x-definitive/summary.json`

## 5. Cinco execuções de recuperação

| Run | Falha real | Falha persistida | Correção posterior | Reteste | Resultado |
|---:|:---:|:---:|:---:|:---:|:---:|
| 1 | Sim | Sim | Sim | Não passou | FAIL |
| 2 | Sim | Sim | Sim | Não passou | FAIL |
| 3 | Sim | Sim | Sim | Não passou | FAIL |
| 4 | Sim | Sim | Sim | Não passou | FAIL |
| 5 | Sim | Sim | Sim | Não passou | FAIL |

## 6. Evidência por execução

### Run 1

- Run ID: `run-01-099a07d87085`
- Mission ID: `mission-run-01-099a07d87085`
- Primeira falha: `node --check src/tasks.js` exit `1`
- Evidência relevante: `C:\Users\joaor\Desktop\ai-company-orchestrator\diagnostics\model_harness_productive_benchmark\20260730-qwen-recovery-5x-definitive\fixtures\S3_RECOVERY_AFTER_REAL_VALIDATION_FAILURE\rep-1\project\src\tasks.js:1 export function normalizeTask(value { ^ SyntaxError: Unexpected token '{' at checkSyntax `
- Ação posterior: `read_file`
- Segunda alteração distinta: True
- Reteste: FAIL/ausente
- Estado final: `FAIL`
- Latência: `59851 ms`
- Tokens: entrada `9118`, saída `704`

### Run 2

- Run ID: `run-02-0aefdb50231b`
- Mission ID: `mission-run-02-0aefdb50231b`
- Primeira falha: `node --check src/tasks.js` exit `1`
- Evidência relevante: `C:\Users\joaor\Desktop\ai-company-orchestrator\diagnostics\model_harness_productive_benchmark\20260730-qwen-recovery-5x-definitive\fixtures\S3_RECOVERY_AFTER_REAL_VALIDATION_FAILURE\rep-2\project\src\tasks.js:1 export function normalizeTask(value { ^ SyntaxError: Unexpected token '{' at checkSyntax `
- Ação posterior: `read_file`
- Segunda alteração distinta: True
- Reteste: FAIL/ausente
- Estado final: `FAIL`
- Latência: `47760 ms`
- Tokens: entrada `9118`, saída `704`

### Run 3

- Run ID: `run-03-1b1fe4eba3b2`
- Mission ID: `mission-run-03-1b1fe4eba3b2`
- Primeira falha: `node --check src/tasks.js` exit `1`
- Evidência relevante: `C:\Users\joaor\Desktop\ai-company-orchestrator\diagnostics\model_harness_productive_benchmark\20260730-qwen-recovery-5x-definitive\fixtures\S3_RECOVERY_AFTER_REAL_VALIDATION_FAILURE\rep-3\project\src\tasks.js:1 export function normalizeTask(value { ^ SyntaxError: Unexpected token '{' at checkSyntax `
- Ação posterior: `read_file`
- Segunda alteração distinta: True
- Reteste: FAIL/ausente
- Estado final: `FAIL`
- Latência: `47913 ms`
- Tokens: entrada `9118`, saída `703`

### Run 4

- Run ID: `run-04-8e172ad032b2`
- Mission ID: `mission-run-04-8e172ad032b2`
- Primeira falha: `node --check src/tasks.js` exit `1`
- Evidência relevante: `C:\Users\joaor\Desktop\ai-company-orchestrator\diagnostics\model_harness_productive_benchmark\20260730-qwen-recovery-5x-definitive\fixtures\S3_RECOVERY_AFTER_REAL_VALIDATION_FAILURE\rep-4\project\src\tasks.js:1 export function normalizeTask(value { ^ SyntaxError: Unexpected token '{' at checkSyntax `
- Ação posterior: `read_file`
- Segunda alteração distinta: True
- Reteste: FAIL/ausente
- Estado final: `FAIL`
- Latência: `47719 ms`
- Tokens: entrada `9118`, saída `704`

### Run 5

- Run ID: `run-05-73cd85ab8b61`
- Mission ID: `mission-run-05-73cd85ab8b61`
- Primeira falha: `node --check src/tasks.js` exit `1`
- Evidência relevante: `C:\Users\joaor\Desktop\ai-company-orchestrator\diagnostics\model_harness_productive_benchmark\20260730-qwen-recovery-5x-definitive\fixtures\S3_RECOVERY_AFTER_REAL_VALIDATION_FAILURE\rep-5\project\src\tasks.js:1 export function normalizeTask(value { ^ SyntaxError: Unexpected token '{' at checkSyntax `
- Ação posterior: `read_file`
- Segunda alteração distinta: True
- Reteste: FAIL/ausente
- Estado final: `FAIL`
- Latência: `46791 ms`
- Tokens: entrada `9118`, saída `704`

## 7. Cenários e resultado global recalculado

### S1_INSPECTION - Inspecao read-only

- Conclusao: 5/5 (100.0%)
- Finish prematuro: 0
- Tools invalidas: 0
- Repeticoes: 0
- Falhas de schema: 0
- Falhas reais de validação: 0
- Recuperações completas: 0
- Passos medios: 4.0
- Latencia media: 22.673s

### S2_SIMPLE_EDIT - Alteracao simples validada

- Conclusao: 5/5 (100.0%)
- Finish prematuro: 0
- Tools invalidas: 0
- Repeticoes: 0
- Falhas de schema: 0
- Falhas reais de validação: 0
- Recuperações completas: 0
- Passos medios: 7.0
- Latencia media: 33.466s

### S3_RECOVERY_AFTER_REAL_VALIDATION_FAILURE - Recuperacao apos falha real de validacao

- Conclusao: 0/5 (0.0%)
- Finish prematuro: 0
- Tools invalidas: 5
- Repeticoes: 0
- Falhas de schema: 0
- Falhas reais de validação: 10
- Recuperações completas: 0
- Passos medios: 9.0
- Latencia media: 50.755s

### S4_STATEFUL_DISCIPLINE - Disciplina stateful

- Conclusao: 5/5 (100.0%)
- Finish prematuro: 0
- Tools invalidas: 0
- Repeticoes: 0
- Falhas de schema: 0
- Falhas reais de validação: 0
- Recuperações completas: 0
- Passos medios: 6.0
- Latencia media: 28.528s

## 8. Métricas globais

- premature_finish: 0
- invalid_tools: 5
- repeated_calls: 0
- schema_failures: 0
- validation_runs: 20
- failed_validations: 10
- corrections_after_failure: 0
- recovery_regressions_injected: 5
- recovery_failures_persisted: 5
- recovery_successes_persisted: 0
- inconclusive_runs: 0
- false_successes: 0
- total_steps: 130
- total_latency_ms: 671784
- input_tokens: 99040
- output_tokens: 10223

## 9. Comandos de validação executados

- `node --check src/tasks.js`
- `node tests/tasks.test.js`

## 10. Critérios de promoção

- completion_rate_at_least_80: False
- recovery_at_least_4_of_5: False
- all_responses_structurally_valid: True
- zero_false_successes: True
- zero_incomplete_successes: True
- zero_finish_accepted_with_failed_validation: True
- all_real_failures_persisted: True
- all_successes_have_passing_retest: True
- zero_inconclusive_runs: True
- outside_fixtures_unchanged: True
- source_integrity_unchanged: True
- promoted: False

## 11. Limitações restantes

- Este cenário mede a fronteira stateful do ModelHarness com tools isoladas; não afirma que a execução atravessou o MissionExecutor ou a CodingSession produtivos.
- A regressão é específica da fixture JavaScript controlada.
- A amostra contém cinco execuções com parâmetros idênticos.

## 12. Decisão final

QWEN_NOT_PROMOTED
