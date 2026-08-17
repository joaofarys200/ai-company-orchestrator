---
type: concept
domain: ai-engineering
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
difficulty: advanced
tags:
  - ai-engineering
  - speculative-decoding
  - model-serving
  - inference-speed
  - draft-models
prerequisites:
  - "[[Model Harness Architecture]]"
  - "[[GPU Kernel Compilation - CUDA, Triton and Memory Bandwidth]]"
related:
  - "[[Model Routing and Fallback Strategies]]"
  - "[[Deterministic vs Stochastic Inference in Coding Pipelines]]"
used_by:
  - "[[JARVIS Model Harness Implementation]]"
failure_modes:
  - "[[Lesson - Unhandled Rate Limits and Context Explosion]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: Fast Inference from Transformers via Speculative Decoding (Leviathan, Kalman, Matias - Google Research, ICML 2023)
    type: PRIMARY_SOURCE
    url: https://arxiv.org/abs/2211.17192
---

# 🚀 Speculative Decoding and Draft-Verification Dynamics

## 1. Pergunta Central
> *Como acelerar a geração autoregressiva de um modelo de linguagem grande (ex: 70B) em $2\times$ a $3\times$ sem alterar rigorosamente a distribuição de probabilidade das saídas geradas?*

---

## 2. Mecanismo em Dois Estágios: Draft & Verify

```
[ Modelo Draft Pequeno (ex: 1B / 4-bit) ] -> Gera K tokens especulativos rapidamente: (t_1, t_2, ..., t_K)
                    |
                    v
[ Modelo Target Grande (ex: 70B / 16-bit) ] -> Executa UM ÚNICO passo paralelo (Compute-Bound) sobre todos os K tokens
                    |
                    v
[ Critério de Aceitação / Rejeição Rejeição Estocástica ]
  - Se P_target(t_i) >= P_draft(t_i) -> Aceita t_i
  - Se P_target(t_i) < P_draft(t_i)  -> Aceita com probabilidade P_target / P_draft; rejeita os subsequentes
```

---

## 3. Dinâmica de Aceitação & Velocidade Efetiva
A aceleração teórica $\alpha$ depende da **Taxa de Aceitação Média ($\gamma$)**:

$$\alpha = \frac{1 - \gamma^{K+1}}{(1 - \gamma)(1 + c \cdot K)}$$
- $c$: Razão de custo computacional entre o modelo draft e o modelo target ($c \ll 1$).
- Em código sintaticamente previsível (Java/Python boilerplate, chaves JSON), a taxa de aceitação frequentemente atinge $\gamma \ge 0.85$, gerando múltiplos tokens por passe de memória do modelo grande.

---

## 4. Related Concepts
- [[GPU Kernel Compilation - CUDA, Triton and Memory Bandwidth]]
- [[Model Routing and Fallback Strategies]]
- [[Deterministic vs Stochastic Inference in Coding Pipelines]]
