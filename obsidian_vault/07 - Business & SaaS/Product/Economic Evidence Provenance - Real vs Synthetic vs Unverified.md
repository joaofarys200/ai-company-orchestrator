---
type: concept
domain: business-economics
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: advanced
tags:
  - business
  - economics
  - evidence-provenance
  - validation
  - alex
prerequisites:
  - "[[Distinguishing Real vs Synthetic Market Evidence]]"
related:
  - "[[Market Opportunity Discovery and Scoring Matrix]]"
  - "[[SaaS Unit Economics - CAC, LTV and Magic Number]]"
used_by:
  - "[[JARVIS EconomicExecutionGateway and Monetization]]"
failure_modes:
  - "[[Lesson - Synthetic Evidence Hallucination in Market Validation]]"
implementation:
  - "[[JARVIS Economic Engine and Metric Verification]]"
sources:
  - title: The Lean Startup - Validated Learning (Eric Ries)
    type: PRIMARY_SOURCE
    url: https://theleanstartup.com/
---

# 💹 Economic Evidence Provenance - Real vs Synthetic vs Unverified

## 1. Pergunta Central
> *Como classificar formalmente graus de evidência de mercado para impedir que agentes analistas (Alex) tomem decisões de investimento baseadas em simulações sintéticas ou feedback enviesado?*

---

## 2. A Hierarquia Quadripartite de Proveniência EconÃ´mica

```
[ Nível 4: EXTERNAL_VERIFIED (Confiança: 0.8 - 1.0) ]
  - Transações financeiras reais (Stripe, faturas pagas)
  - Contratos assinados / depósitos de pré-reserva
  - Eventos de conversão verificados via webhook criptograficamente assinado

[ Nível 3: LOCAL_REAL (Confiança: 0.6 - 0.8) ]
  - Métricas de telemetria interna e benchmarks de execução
  - Logs de latência e consumo de tokens de produção

[ Nível 2: EXTERNAL_UNVERIFIED (Confiança: 0.3 - 0.5) ]
  - Menções em fóruns, posts no Reddit, enquetes públicas
  - Respostas verbais de entrevistas sem compromisso financeiro

[ Nível 1: SYNTHETIC (Confiança: 0.0 - 0.2) ]
  - Personas simuladas por LLMs
  - Estimativas heurísticas e dados gerados por prompting
```

---

## 3. Regra Inviolável de Governança
Projeções de receita para missões do JARVIS OS não podem utilizar evidências de Nível 1 (`SYNTHETIC`) como prova de validação de mercado (ver [[ADR-005 - Economic Evidence Provenance and Synthetic Data Capping]]).

---

## 4. Related Concepts
- [[Distinguishing Real vs Synthetic Market Evidence]]
- [[Market Opportunity Discovery and Scoring Matrix]]
- [[JARVIS EconomicExecutionGateway and Monetization]]

## Query Relevance
Por que projeções de receita não podem usar dados sintéticos como prova de validação.

