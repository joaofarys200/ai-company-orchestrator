---
type: runbook
domain: ai-engineering
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
difficulty: advanced
tags:
  - runbook
  - ai-engineering
  - rho
  - context-saturation
  - troubleshooting
prerequisites:
  - "[[Context Engineering and Compression]]"
  - "[[Self-Healing Prompt Loops and Reflective Orchestration (RHO-SHE)]]"
related:
  - "[[Agent Loop Detection and Circuit Breaker]]"
  - "[[How to Handle Malformed Model Output]]"
used_by:
  - "[[JARVIS Model Harness Implementation]]"
failure_modes:
  - "[[Lesson - Unhandled Rate Limits and Context Explosion]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: JARVIS RHO Diagnostic Protocol
    type: JARVIS_INTERNAL
    url: internal://tests/test_model_harness_rho_she.py
---

# 🛠️ Runbook - How to Recover from RHO Rule Explosion and Saturated Context

## 1. Symptoms
- As respostas do modelo começam a ignorar restrições básicas de formatação JSON.
- A contagem de tokens por turno ultrapassa 85% do limite da janela de contexto (`token_count > 28000`).
- O agente Devon repete a mesma proposta de código em loop sem convergir.

---

## 2. Preconditions
- A missão está ativa no estado `IN_PROGRESS` com múltiplas tentativas de auto-reparo registradas.

---

## 3. Diagnosis
1. Inspecionar o tamanho das mensagens no histórico do agente via log ou telemetria.
2. Contar o número de blocos `<reflection>` acumulados no prompt. Se $N \ge 3$, ocorreu **Explosão de Regras do RHO**.

---

## 4. Commands / Queries
```bash
# Inspecionar contagem de tokens no banco de dados SQLite
sqlite3 database.db "SELECT step_id, tokens_used, cost_estimate_usd FROM steps WHERE status = 'IN_PROGRESS';"
```

---

## 5. Decision Tree
```
[ Contexto > 85% do Budget? ]
         |
         +---> SIM ---> [ Executar Compactação AST & Poda de Histórico ]
         |
         +---> NÃO ---> [ Verificar se Erro é Sintático ou Lógico ]
```

---

## 6. Recovery
1. Invocar o compactador de histórico do `ModelHarness`.
2. Substituir todas as reflexões intermediárias passadas por um resumo atômico de 3 linhas.
3. Reiniciar a chamada do modelo com temperatura calibrada em $T=0.0$.

---

## 7. Verification
Verificar se o próximo turno do modelo consome $< 30\%$ do budget de tokens e retorna JSON válido.

---

## 8. Rollback
Se o modelo falhar novamente após a compactação, transitar o estado da missão para `PAUSED_WAITING_HUMAN`.

---

## 9. Prevention
Aplicar o limitador de turns e poda estrutural por AST (ver [[ADR-009 - RHO and SHE Rule Compaction and Max Turn Quotas]]).

---

## 10. Evidence
- Registro em `telemetry_logs` com categoria `CONTEXT_COMPACTED_SUCCESSFULLY`.
