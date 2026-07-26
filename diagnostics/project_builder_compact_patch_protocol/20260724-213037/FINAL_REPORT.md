# ProjectBuilder Compact Typed Patch Protocol Report

## 1. Resumo executivo
Decisao final: `QWEN_9B_PROTOCOL_SELECTION_UNRELIABLE`.
O baseline manual terminou em `MANUAL_COMPACT_PATCH_PASSED` com 8 operacoes e 1 alteracao virtual.
A experiencia e offline/diagnostica: nao houve escrita num projeto, materializacao, preview, npm, WP1 ou WP2.

## 2. Escopo e fontes
Foram reutilizados o prototipo typed, a auditoria de content operations, a auditoria de qualidade do plano e o flight recorder indicados pelo protocolo.
Namespace de erros: `MISSING_REQUESTED_COMPONENTS, MISSING_COMPONENT_MAPPING, DECLARED_COMPONENT_WITHOUT_ARTIFACTS, PERSISTENCE_NOT_IMPLEMENTED, MISSING_HEALTH_ROUTE`.
Paths permitidos: `index.html, package.json, server.js, test.js`.

## 3. Contrato compacto
Resposta: `error_resolutions` e `operations`. Cada erro unico aparece exatamente uma vez; cada referencia aponta para uma operacao existente.
Operacoes fechadas: `set_components`, `set_component_files`, `set_preview_strategy`, `apply_code_transform`.
Nao ha campos de conteudo livre, replace_file_content, replace_text, criacao de ficheiros, JSON Patch ou codigo fornecido pelo modelo.

## 4. Catalogo de transforms
`ADD_JSON_FILE_PERSISTENCE` e o unico transform com alteracao de conteudo. E restrito a server.js, exige SHA-256 inicial e produz node:fs, caminho JSON deterministico, leitura/escrita duravel, missing-file handling, preservando node:http e /health.
Os transforms de preservacao sao fechados e nao introduzem alteracoes.

## 5. Baseline manual
O baseline cobriu os cinco erros unicos, mapeou persistence para server.js e aplicou somente o transform deterministico registado.
Validadores reais: `True`.

## 6. Execucao K1-K4
Todas as chamadas usaram qwen3.5:9b, num_ctx=8192, temperature=0, top_p=0.8, think=false, structured output, stream=false.
Nao foram usados retries, autorepair ou uma terceira chamada.

| Caso | done | done_reason | JSON | schema | apply | validators | erros |
|---|---:|---|---:|---:|---:|---:|---|
| K1 | True | stop | True | True | False | False | [{'code': 'HASH_MISMATCH', 'message': 'Transform hash does not match original content', 'details': {'path': 'server.js', 'expected': 'a1b2c3d4e5f67890abcdef1234567890fedcba9876543210abcdef1234567890', 'actual': '5bdbf49b0e707cf43da23ffb5d642e9ed97f8e98e103a8a0c9a69e6ccca9bd31'}}] |
| K2 | True | stop | True | True | False | False | [{'code': 'HASH_MISMATCH', 'message': 'Transform hash does not match original content', 'details': {'path': 'server.js', 'expected': 'a1b2c3d4e5f67890abcdef1234567890fedcba9876543210abcdef1234567890', 'actual': '5bdbf49b0e707cf43da23ffb5d642e9ed97f8e98e103a8a0c9a69e6ccca9bd31'}}] |
| K3 | True | stop | True | True | False | False | [{'code': 'HASH_MISMATCH', 'message': 'Transform hash does not match original content', 'details': {'path': 'server.js', 'expected': 'a1b2c3d4e5f67890abcdef1234567890fedcba9876543210abcdef1234567890', 'actual': '5bdbf49b0e707cf43da23ffb5d642e9ed97f8e98e103a8a0c9a69e6ccca9bd31'}}] |
| K4 | True | stop | True | True | False | False | [{'code': 'HASH_MISMATCH', 'message': 'Transform hash does not match original content', 'details': {'path': 'server.js', 'expected': 'a1b2c3d4e5f67890abcdef1234567890fedcba9876543210abcdef1234567890', 'actual': '5bdbf49b0e707cf43da23ffb5d642e9ed97f8e98e103a8a0c9a69e6ccca9bd31'}}] |

## 7. Determinismo e variacao controlada
K1/K2 raw response SHA-256 igual: `True`.
K3 manteve a semantica do schema e alterou apenas a ordem documental do catalogo.
K4 teve catalogo de operacoes minimo: `True`. O prompt efetivamente registado nesta execucao manteve a documentacao dos transforms de preservacao: catalogo de transforms minimo = `False`. O runner foi corrigido para remover essa documentacao em futuras execucoes; nao foi feita uma quinta chamada.

## 8. Atomicidade virtual
A validacao ocorre antes da mutacao. A composicao usa uma copia virtual profunda; qualquer falha devolve rollback virtual e nunca grava artefactos no workspace/projects.

## 9. Validacao
Os 32 testes unitarios do protocolo passaram antes das chamadas ao modelo. Cada resposta completa foi sujeita ao schema, cobertura, compatibilidade semantica, transform e validadores reais do prototipo anterior.

## 10. Artefactos produzidos
O diretorio contem prompts, schemas, payloads, envelopes brutos, metrics, respostas normalizadas, assessments, apply results, hashes das fontes e este relatorio.

## 11. Seguranca
Nenhum conteudo de source code foi aceite do modelo. Nenhum path fora do namespace foi aceito. Nenhum ficheiro foi criado pelo protocolo. Nenhuma API produtiva foi alterada.

## 12. Limites do resultado
Este prototipo valida uma fixture virtual especifica e nao prova integracao produtiva. O resultado do modelo mede selecao de operacoes compactas, nao capacidade geral de programacao.

## 13. Criterio de viabilidade
Passaria apenas com baseline manual, testes, pelo menos 3/4 casos completos, K1/K2 completos, respostas nao truncadas e validadores reais aprovados.
Neste run: 0/4 casos completos; K1/K2: `False`; todas completas: `True`.

## 14. Alteracoes produtivas
Nenhuma. Nao foram alterados agents/orchestrator, ProjectBuilder, MissionExecutor, requester, validadores, modelos, .env ou configuracao.

## 15. Reproducibilidade
Executar os 32 testes locais e o runner deste diretorio reproduz o protocolo. A experiencia de modelo e deliberadamente limitada a quatro chamadas sequenciais ao endpoint Ollama.

## 16. Comparacao consolidada
O primeiro prototipo typed permitia representar operacoes mas o modelo tinha falhas de cobertura e selecao. Este segundo prototipo reduz a linguagem a operacoes enumeradas e transforms registados, eliminando payload de codigo livre. A decisao acima deve ser lida em conjunto com os artefactos por caso.
