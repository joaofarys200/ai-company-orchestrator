---
type: pattern
domain: ai-engineering
status: verified
source_type: SYNTHESIZED
confidence: high
difficulty: advanced
tags:
  - ai-engineering
  - agent-systems
  - rho
  - she
  - self-healing
  - reflective-orchestration
  - circuit-breakers
prerequisites:
  - "[[Planner-Executor Agent Pattern]]"
  - "[[Compiler Feedback and Test-Driven Self-Repair]]"
related:
  - "[[Agent Loop Detection and Circuit Breaker]]"
  - "[[Model Routing and Fallback Strategies]]"
used_by:
  - "[[JARVIS Model Harness Implementation]]"
failure_modes:
  - "[[Lesson - Unhandled Rate Limits and Context Explosion]]"
implementation:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
sources:
  - title: Reflexion - Language Agents with Verbal Reinforcement Learning (Shinn et al., NeurIPS 2023)
    type: PRIMARY_SOURCE
    url: https://arxiv.org/abs/2303.11366
  - title: JARVIS Reflective Healing Orchestrator (RHO) Test Suite
    type: JARVIS_INTERNAL
    url: internal://tests/test_model_harness_rho_she.py
---

# ðŸ”„ Orquestracao de Auto Cura Reflexiva RHO SHE e Circuit Breakers

## 1. Pergunta Central
> *Como orquestrar um ciclo fechado de auto cura reflexiva (RHO e SHE) onde um agente de execuÃ§Ã£o (Devon) recebe feedback reflexivo de falhas de compilaÃ§Ã£o ou execuÃ§Ã£o sem entrar em loops infinitos com circuit breakers para LLMs?*

---

## 2. A Arquitetura RHO (Reflective Healing Orchestrator) & SHE (Self-Healing Engine)

```
[ Tarefa de CÃ³digo / Patch ]
             |
             v
   [ Devon: GeraÃ§Ã£o do Patch ]
             |
             v
 [ Quinn: ExecuÃ§Ã£o de Testes / Linters ]
             |
             +---> (Testes Passaram) ----> [ SUCESSO: Commit AtÃ³mico ]
             |
             +---> (Falha Detectada)
                     |
                     v
   [ RHO: ExtraÃ§Ã£o SemÃ¢ntica do Erro ] (Isola Linha, ExceÃ§Ã£o, Stacktrace)
                     |
                     v
   [ SHE: GeraÃ§Ã£o de HipÃ³tese & ReflexÃ£o ]
     - "Porque falhou?"
     - "Qual a premissa errada?"
     - "Qual a correÃ§Ã£o mÃ­nima necessÃ¡ria?"
                     |
                     v (ReflexÃ£o Injetada no Prompt de Reparo)
   [ Devon: GeraÃ§Ã£o de Patch Corretivo ] (Tentativa N + 1 <= 3)
```

---

## 3. Salvaguardas contra Loops Infinitos (Circuit Breakers)
1. **Limite RÃ­gido de Turnos de Cura ($Max\_Attempts = 3$)**: Se o erro persistir apÃ³s 3 iteraÃ§Ãµes de reflexÃ£o, a missÃ£o Ã© automaticamente congelada no estado `PAUSED_WAITING_HUMAN`.
2. **DeteÃ§Ã£o de OscilaÃ§Ã£o de CÃ³digo**: Se o patch $N$ reverter o cÃ³digo para um estado idÃªntico ao patch $N-2$, o motor de reflexÃ£o interrompe o ciclo imediatamente.

---

## 4. Related Concepts
- [[Compiler Feedback and Test-Driven Self-Repair]]
- [[Agent Loop Detection and Circuit Breaker]]
- [[Planner-Executor Agent Pattern]]
- [[JARVIS RHO and SHE Self-Healing Architecture]]

## Query Relevance
Orquestração de auto cura reflexiva rho she e circuit breakers para llms.

