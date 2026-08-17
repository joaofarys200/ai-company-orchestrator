---
type: concept
domain: business-economics
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: intermediate
tags:
  - business
  - market-validation
  - real-evidence
  - synthetic-evidence
  - product-validation
  - alex
prerequisites:
  - "[[Market Opportunity Discovery and Scoring Matrix]]"
related:
  - "[[Economic Evidence Provenance - Real vs Synthetic vs Unverified]]"
  - "[[SaaS Unit Economics - CAC, LTV and Magic Number]]"
used_by:
  - "[[JARVIS EconomicExecutionGateway and Monetization]]"
failure_modes:
  - "[[Lesson - Synthetic Evidence Hallucination in Market Validation]]"
implementation:
  - "[[JARVIS Economic Engine and Metric Verification]]"
sources:
  - title: The Mom Test - How to talk to customers & learn if your business is a good idea (Rob Fitzpatrick)
    type: PRIMARY_SOURCE
    url: https://www.momtestbook.com/
---

# 🔬 Como Distinguir Evidencia de Mercado Real de Dados Sinteticos

## 1. Pergunta Central
> *Como agentes autónomos de estratégia e produto (Alex) distinguem intenção real de compra de dados sintéticos gerados por LLMs e por que dados sintéticos não possuem valor de validação económica?*

---

## 2. A Ilusão do Feedback Sintético
Modelos de linguagem treinados com Reinforcement Learning from Human Feedback (**RLHF**) sofrem de um forte viés de adulação e concordância (*Sycophancy*). Quando um agente pede a um LLM para simular um cliente empresarial, a persona simulada quase sempre expressa entusiasmo desproporcional.

---

## 3. Tabela Comparativa de Evidência

| Tipo de Evidência | Origem dos Dados | Nível de Validade Preditiva | Ação no Motor Económico do JARVIS |
|---|---|---|---|
| **EVIDÊNCIA REAL DE MERCADO** | Transações Stripe, depósitos de reserva, conversões de cliques com orçamento real | **Alta (90-100%)** | Permite aprovação de missão e alocação de engenharia |
| **EVIDÊNCIA SINTÉTICA** | Personas geradas por LLMs, respostas simuladas em enquetes | **NULA (0%)** | Classificada como mera hipótese; limita confiança a máx $0.2$ |

---

## 4. Related Concepts
- [[Economic Evidence Provenance - Real vs Synthetic vs Unverified]]
- [[Market Opportunity Discovery and Scoring Matrix]]
- [[Lesson - Synthetic Evidence Hallucination in Market Validation]]
- [[ADR-005 - Economic Evidence Provenance and Synthetic Data Capping]]
