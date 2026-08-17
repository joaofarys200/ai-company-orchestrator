---
type: concept
domain: security
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
difficulty: advanced
tags:
  - security
  - privacy
  - differential-privacy
  - privacy-budget
  - telemetry
prerequisites:
  - "[[Credential Sanitization and Secret Masking]]"
related:
  - "[[Structured Logging and Distributed Trace Context]]"
  - "[[Zero Trust Architecture and Microsegmentation]]"
used_by:
  - "[[JARVIS Security Sandbox and Policy Engine]]"
failure_modes:
  - "[[Lesson - Accidental Secret Leaks in Telemetry Broadcast]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: The Algorithmic Foundations of Differential Privacy (Dwork & Roth, 2014)
    type: PRIMARY_SOURCE
    url: https://www.cis.upenn.edu/~aaroth/Papers/privacybook.pdf
  - title: Local Differential Privacy - Mechanisms and Applications (Apple Privacy Engineering)
    type: PRIMARY_SOURCE
    url: https://www.apple.com/privacy/docs/Differential_Privacy_Overview.pdf
---

# 🛡️ Differential Privacy and Privacy Budgets in Agent Telemetry

## 1. Pergunta Central
> *Como coletar métricas agregadas de execução, contagem de erros e estatísticas de uso de agentes de múltiplos clientes sem permitir que um invasor deduza a presença ou os dados privados de um único utilizador individual?*

---

## 2. A Definição Matemática de $(\epsilon, \delta)$-Privacidade Diferencial
Um algoritmo randomizado $\mathcal{M}$ fornece $(\epsilon, \delta)$-Privacidade Diferencial se, para quaisquer dois conjuntos de dados vizinhos $D_1$ e $D_2$ que diferem em exatamente um registro de utilizador, e para qualquer conjunto de saídas $S \subseteq \text{Range}(\mathcal{M})$:

$$\Pr[\mathcal{M}(D_1) \in S] \le e^{\epsilon} \times \Pr[\mathcal{M}(D_2) \in S] + \delta$$
- $\epsilon$ (**Privacy Budget / Orçamento de Privacidade**): Controla o vazamento máximo de informação permitido. Quanto menor o $\epsilon$, maior o ruído injetado e maior a proteção matemática.
- $\delta$: Probabilidade residual de falha estrita da garantia exponencial.

---

## 3. Mecanismo de Laplace para Métricas Numéricas
Para reportar métricas contínuas (ex: tempo médio de execução de passos), o mecanismo injeta ruído calibrado pela sensibilidade global $\Delta f$:

$$\mathcal{M}(D) = f(D) + \text{Laplace}\left(0, \frac{\Delta f}{\epsilon}\right)$$

---

## 4. Related Concepts
- [[Credential Sanitization and Secret Masking]]
- [[Structured Logging and Distributed Trace Context]]
- [[Zero Trust Architecture and Microsegmentation]]
