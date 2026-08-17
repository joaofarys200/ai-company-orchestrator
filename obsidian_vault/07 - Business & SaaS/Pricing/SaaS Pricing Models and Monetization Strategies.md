---
type: concept
domain: business-economics
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: intermediate
tags:
  - business
  - saas
  - pricing
  - monetization
  - willingness-to-pay
  - models
prerequisites:
  - "[[SaaS Unit Economics - CAC, LTV and Magic Number]]"
related:
  - "[[Churn Rate Analysis and Cohort Retention Curves]]"
  - "[[Economic Evidence Provenance - Real vs Synthetic vs Unverified]]"
used_by:
  - "[[JARVIS EconomicExecutionGateway and Monetization]]"
failure_modes:
  - "[[Lesson - Synthetic Evidence Hallucination in Market Validation]]"
implementation:
  - "[[JARVIS Economic Engine and Metric Verification]]"
sources:
  - title: Monetizing Innovation - How Smart Companies Design the Product Around the Price (Ramanujam & Tacke)
    type: PRIMARY_SOURCE
    url: https://www.simon-kucher.com/en/our-books/monetizing-innovation
---

# 🏷️ Modelos de Precificacao SaaS Monetizacao e Willingness to Pay

## 1. Pergunta Central
> *Quais são os principais modelos de precificação SaaS (por assento, por uso de tokens, escalonado ou híbrido) e como mensurar a disposição a pagar (Willingness to Pay) sem quebrar as margens unitárias?*

---

## 2. Comparativo de Modelos de Precificação SaaS

| Modelo de Pricing | Mecanismo de Cobrança | Vantagens | Desvantagens / Risco para IA |
|---|---|---|---|
| **Per-Seat (Por Usuário)** | Taxa mensal fixa por usuário ativo | Receita altamente previsível | Não escala com consumo de tokens de GPU |
| **Usage-Based (Por Consumo)** | Cobrança por token, GB ou invocação de API | Alinhamento perfeito com custos de inferência | Menor previsibilidade de receita para o cliente |
| **Tiered Hybrid (Híbrido)** | Mensalidade base inclui cota de tokens + overage | Previsibilidade de base + upside de expansão | Maior complexidade de billing |

---

## 3. Mensuração da Disposição a Pagar (Van Westendorp PSM)
O método de Sensibilidade de Preço de Van Westendorp avalia 4 perguntas de pesquisa empírica para encontrar o ponto de preço ótimo ($P_{\text{opt}}$) e a faixa aceitável de preço.

---

## 4. Related Concepts
- [[SaaS Unit Economics - CAC, LTV and Magic Number]]
- [[Economic Evidence Provenance - Real vs Synthetic vs Unverified]]
- [[Churn Rate Analysis and Cohort Retention Curves]]
