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
- Respostas estruturais validas: 132/132 (100.0%)
- Integridade do codigo fonte: inalterada
- Promocao: FAIL
- Decisão: `QWEN_NOT_PROMOTED`
- Baseline válido: `C:/Users/joaor/Desktop/ai-company-orchestrator/diagnostics/model_harness_productive_benchmark/20260730-qwen-5x-definitive/summary.json`

## 5. Cinco execuções de recuperação

| Run | Falha real | Falha persistida | Correção posterior | Reteste | Resultado |
|---:|:---:|:---:|:---:|:---:|:---:|
| 1 | Sim | Sim | Não | Não passou | FAIL |
| 2 | Sim | Sim | Não | Não passou | FAIL |
| 3 | Sim | Sim | Sim | Não passou | FAIL |
| 4 | Sim | Sim | Não | Não passou | FAIL |
| 5 | Sim | Sim | Sim | Não passou | FAIL |

## 6. Evidência por execução

### Run 1

- Run ID: `run-01-c19e535aa132`
- Mission ID: `mission-run-01-c19e535aa132`
- Primeira falha: `node --check src/tasks.js` exit `1`
- Evidência relevante: `C:\Users\joaor\Desktop\ai-company-orchestrator\diagnostics\model_harness_productive_benchmark\20260730-qwen-recovery-5x-definitive-r2\fixtures\S3_RECOVERY_AFTER_REAL_VALIDATION_FAILURE\rep-1\project\src\tasks.js:1 export function normalizeTask(value { ^ SyntaxError: Unexpected token '{' at checkSynt`
- Ação posterior: `read_file`
- Segunda alteração distinta: False
- Reteste: FAIL/ausente
- Estado final: `FAIL`
- Latência: `33664 ms`
- Tokens: entrada `6066`, saída `483`

### Run 2

- Run ID: `run-02-ba44ff308846`
- Mission ID: `mission-run-02-ba44ff308846`
- Primeira falha: `node --check src/tasks.js` exit `1`
- Evidência relevante: `C:\Users\joaor\Desktop\ai-company-orchestrator\diagnostics\model_harness_productive_benchmark\20260730-qwen-recovery-5x-definitive-r2\fixtures\S3_RECOVERY_AFTER_REAL_VALIDATION_FAILURE\rep-2\project\src\tasks.js:1 export function normalizeTask(value { ^ SyntaxError: Unexpected token '{' at checkSynt`
- Ação posterior: `read_file`
- Segunda alteração distinta: False
- Reteste: FAIL/ausente
- Estado final: `FAIL`
- Latência: `33284 ms`
- Tokens: entrada `6066`, saída `483`

### Run 3

- Run ID: `run-03-37ac53563e42`
- Mission ID: `mission-run-03-37ac53563e42`
- Primeira falha: `node --check src/tasks.js` exit `1`
- Evidência relevante: `C:\Users\joaor\Desktop\ai-company-orchestrator\diagnostics\model_harness_productive_benchmark\20260730-qwen-recovery-5x-definitive-r2\fixtures\S3_RECOVERY_AFTER_REAL_VALIDATION_FAILURE\rep-3\project\src\tasks.js:1 export function normalizeTask(value { ^ SyntaxError: Unexpected token '{' at checkSynt`
- Ação posterior: `read_file`
- Segunda alteração distinta: True
- Reteste: FAIL/ausente
- Estado final: `FAIL`
- Latência: `78190 ms`
- Tokens: entrada `15279`, saída `1160`

### Run 4

- Run ID: `run-04-127dbcad16a5`
- Mission ID: `mission-run-04-127dbcad16a5`
- Primeira falha: `node --check src/tasks.js` exit `1`
- Evidência relevante: `C:\Users\joaor\Desktop\ai-company-orchestrator\diagnostics\model_harness_productive_benchmark\20260730-qwen-recovery-5x-definitive-r2\fixtures\S3_RECOVERY_AFTER_REAL_VALIDATION_FAILURE\rep-4\project\src\tasks.js:1 export function normalizeTask(value { ^ SyntaxError: Unexpected token '{' at checkSynt`
- Ação posterior: `read_file`
- Segunda alteração distinta: False
- Reteste: FAIL/ausente
- Estado final: `FAIL`
- Latência: `34074 ms`
- Tokens: entrada `6066`, saída `483`

### Run 5

- Run ID: `run-05-1390457bb470`
- Mission ID: `mission-run-05-1390457bb470`
- Primeira falha: `node --check src/tasks.js` exit `1`
- Evidência relevante: `C:\Users\joaor\Desktop\ai-company-orchestrator\diagnostics\model_harness_productive_benchmark\20260730-qwen-recovery-5x-definitive-r2\fixtures\S3_RECOVERY_AFTER_REAL_VALIDATION_FAILURE\rep-5\project\src\tasks.js:1 export function normalizeTask(value { ^ SyntaxError: Unexpected token '{' at checkSynt`
- Ação posterior: `read_file`
- Segunda alteração distinta: True
- Reteste: FAIL/ausente
- Estado final: `FAIL`
- Latência: `73082 ms`
- Tokens: entrada `15279`, saída `1041`

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
- Tools invalidas: 4
- Repeticoes: 1
- Falhas de schema: 0
- Falhas reais de validação: 9
- Recuperações completas: 0
- Passos medios: 9.4
- Latencia media: 51.278s

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
- invalid_tools: 4
- repeated_calls: 1
- schema_failures: 0
- validation_runs: 19
- failed_validations: 9
- corrections_after_failure: 0
- recovery_regressions_injected: 5
- recovery_failures_persisted: 5
- recovery_successes_persisted: 0
- inconclusive_runs: 0
- false_successes: 0
- total_steps: 132
- total_latency_ms: 674044
- input_tokens: 102206
- output_tokens: 10354

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

## 12. Tentativa de calibração excluída

A execução `20260730-qwen-recovery-5x-definitive` revelou que a sequência fixa recusava uma nova leitura quando o primeiro reteste continuava vermelho. Os cinco resultados dessa tentativa são `INCONCLUSIVE` por interferência do harness e não entram neste cálculo. A bateria `r2` usa uma máquina de estados que permite ciclos adicionais `read_file -> apply_patch -> run_validation` dentro do limite de passos.

## 13. Validação do repositório

- Testes focais de ModelHarness, MissionExecutor, MissionState, CodingSession, benchmark e arquitetura: `60/60`.
- Suite Python completa: `380/380`.
- `pip check`: sem dependências quebradas.
- `npm run lint --prefix frontend`: passou.
- `npm run build --prefix frontend`: passou.
- `git diff --check`: passou.
- Transporte produtivo fora do ModelHarness: nenhum detetado pelo teste arquitetural.

## 14. Decisão final

QWEN_NOT_PROMOTED
