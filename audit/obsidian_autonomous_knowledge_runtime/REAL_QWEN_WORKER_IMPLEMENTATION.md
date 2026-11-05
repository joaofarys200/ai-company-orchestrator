# 4. REAL QWEN WORKER IMPLEMENTATION

**Status:** IMPLEMENTED | INTEGRATED | UNIT_TESTED | INTEGRATION_TESTED | REAL_QWEN_TESTED | INDEPENDENTLY_VALIDATED  
**Data:** 2026-11-05  
**Modelo:** Ollama local `qwen3.5:9b` (Porta 11434)  
**Boundary:** `ModelExecutionService` via `ModelHarness`

---

## 4.1 Transição do Motor Determinístico para Geração Generativa Real

A versão anterior executava apenas `enrich_note_safely()`, adicionando frontmatter estático e regexes de wikilinks.
A nova implementação executa a função assíncrona `_execute_qwen_knowledge_improvement`:
1. **Verificação de Ambiente:** Acede a `http://127.0.0.1:11434/api/tags` para aferir presença do modelo `qwen3.5:9b`. Se inacessível, bloqueia a execução com `BLOCKED_BY_ENVIRONMENT`.
2. **Montagem de Contexto Real:** Lê a nota completa e até 3 notas contextuais conectadas por wikilinks no cofre.
3. **Prompt Estruturado de Aprofundamento:** Solicita secções de `substantive_addition`, `mechanisms_and_tradeoffs`, `evidence_anchors` e `jarvis_linkage`.
4. **Formato Estruturado JSON:** Execução através de `OutputFormat.JSON` com temperatura 0.2 e tokens delimitados.
5. **Validação de Evidência:** Afirmações factuais sem fonte verificável são sinalizadas como inferência ou aguardam revisão humana (`AWAITING_REVIEW`).

---

## 4.2 Provas de Execução em Tempo Real (Telemetria Real)

Durante a execução da suite de testes:
```
slot   operator(): id 0 | task 296 | restored context checkpoint (n_tokens = 879, size = 50.251 MiB)
slot print_timing: id 0 | task 296 | n_gen = 100, tg = 6.54 t/s
slot print_timing: id 0 | task 296 | n_gen = 281, tg = 6.06 t/s
Geração de 281 tokens concluída em ~46s com modelo local qwen3.5:9b.
```
Zero chamadas para fornecedores cloud externos. Zero custos de API.
