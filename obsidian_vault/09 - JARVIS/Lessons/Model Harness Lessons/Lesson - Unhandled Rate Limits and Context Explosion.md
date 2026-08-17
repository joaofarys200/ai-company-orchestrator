---
type: lesson
domain: jarvis
source: production
severity: high
component: model-harness
status: verified
source_type: JARVIS_INTERNAL
confidence: high
tags:
  - jarvis
  - lesson
  - model-harness
  - post-mortem
  - rate-limits
prerequisites:
  - "[[Model Harness Architecture]]"
  - "[[Context Engineering and Compression]]"
related:
  - "[[Model Routing and Fallback Strategies]]"
  - "[[Anti-Pattern - Unbounded Context Accumulation]]"
  - "[[How to Handle Malformed Model Output]]"
used_by:
  - "[[JARVIS Model Harness Implementation]]"
failure_modes:
  - "[[Agent Loop Detection and Circuit Breaker]]"
implementation:
  - "[[JARVIS System Architecture]]"
sources:
  - title: JARVIS Incident Report - Incident INC-2026-08-01
    type: JARVIS_INTERNAL
    url: internal://incidents/INC-2026-08-01
---

# 📝 Lesson - Unhandled Rate Limits and Context Explosion

## 1. Failure
Durante uma missão de refatoração multi-ficheiro, o agente Devon recebeu sucessivos erros `HTTP 429 Too Many Requests` do provedor de nuvem. O loop ingênuo de retry anexou a mensagem de erro inteira com stacktrace em cada tentativa consecutiva dentro do array de `messages`, fazendo o prompt crescer de 12k tokens para mais de 120k tokens em 4 iterações. Quando a cota foi restabelecida, a janela de contexto saturada excedeu o orçamento de tokens (`max_tokens_budget`), causando aborto fatal da missão.

---

## 2. Root Cause
1. **Falta de Podagem de Erros Transitórios**: O histórico de conversação mantinha erros de rede transitórios (`429`, `503`) como se fossem turnos semânticos do diálogo.
2. **Ausência de Backoff Exponencial com Jitter no Nível do Harness**: As retentativas foram disparadas com intervalos fixos de 1 segundo, violando o tempo de espera informado pelo cabeçalho `Retry-After`.

---

## 3. Why Existing Protection Failed
O `ModelHarness` possuía um contador de retentativas simples (`max_retries = 5`), mas não limitava o tamanho do buffer acumulado nem filtrava payloads de erro de transporte antes da injeção no contexto do próximo turno.

---

## 4. Corrective Action
1. **Filtro de Histórico no Harness**: Erros de transporte HTTP (`429`, `503`, timeouts) são tratados no nível do driver de rede e **NUNCA são anexados ao histórico de mensagens** do agente.
2. **Implementação de Jitter com Header Inspection**: Leitura explícita do cabeçalho `Retry-After` com fallback para backoff exponencial truncado:
   $$T_{\text{wait}} = \min(30.0, 2.0^{\text{attempt}}) + \text{uniform}(0.1, 1.0)$$
3. **Limite Rígido de Context Budget**: O harness valida `len(tokens) < budget` antes de emitir a requisição, podando turnos antigos se necessário via [[Context Engineering and Compression]].

---

## 5. Generalizable Principle
> *Erros de transporte e indisponibilidade de infraestrutura são ruído efêmero e não devem poluir a memória semântica do agente cognitivo.*

---

## 6. Related Concepts
- [[Model Harness Architecture]]
- [[Context Engineering and Compression]]
- [[Model Routing and Fallback Strategies]]
- [[Anti-Pattern - Unbounded Context Accumulation]]

---

## 7. Tests Added
- `tests/test_model_harness_resilience.py::test_rate_limit_does_not_expand_context`
- `tests/test_model_harness_resilience.py::test_exponential_backoff_respects_retry_after`
