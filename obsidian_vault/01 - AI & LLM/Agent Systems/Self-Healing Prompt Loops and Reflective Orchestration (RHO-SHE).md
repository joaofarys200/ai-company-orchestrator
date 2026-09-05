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

# 🔄 Orquestracao de Auto Cura Reflexiva RHO SHE e Circuit Breakers

## 1. Pergunta Central
> *Como orquestrar um ciclo fechado de auto cura reflexiva (RHO e SHE) onde um agente de execução (Devon) recebe feedback reflexivo de falhas de compilação ou execução sem entrar em loops infinitos com circuit breakers para LLMs?*

---

## 2. A Arquitetura RHO (Reflective Healing Orchestrator) & SHE (Self-Healing Engine)

```
[ Tarefa de Código / Patch ]
             |
             v
   [ Devon: Geração do Patch ]
             |
             v
 [ Quinn: Execução de Testes / Linters ]
             |
             +---> (Testes Passaram) ----> [ SUCESSO: Commit Atómico ]
             |
             +---> (Falha Detectada)
                     |
                     v
   [ RHO: Extração Semântica do Erro ] (Isola Linha, Exceção, Stacktrace)
                     |
                     v
   [ SHE: Geração de Hipótese & Reflexão ]
     - "Porque falhou?"
     - "Qual a premissa errada?"
     - "Qual a correção mínima necessária?"
                     |
                     v (Reflexão Injetada no Prompt de Reparo)
   [ Devon: Geração de Patch Corretivo ] (Tentativa N + 1 <= 3)
```

---

## 3. Salvaguardas contra Loops Infinitos (Circuit Breakers)
1. **Limite Rígido de Turnos de Cura ($Max\_Attempts = 3$)**: Se o erro persistir após 3 iterações de reflexão, a missão é automaticamente congelada no estado `PAUSED_WAITING_HUMAN`.
2. **Deteção de Oscilação de Código**: Se o patch $N$ reverter o código para um estado idêntico ao patch $N-2$, o motor de reflexão interrompe o ciclo imediatamente.

---

## 4. Related Concepts
- [[Compiler Feedback and Test-Driven Self-Repair]]
- [[Agent Loop Detection and Circuit Breaker]]
- [[Planner-Executor Agent Pattern]]
- [[JARVIS RHO and SHE Self-Healing Architecture]]

## Query Relevance
Orquestração de auto cura reflexiva rho she e circuit breakers para llms.

