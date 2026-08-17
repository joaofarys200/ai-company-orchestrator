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

# ðŸ’¹ Economic Evidence Provenance - Real vs Synthetic vs Unverified

## 1. Pergunta Central
> *Como classificar formalmente graus de evidÃªncia de mercado para impedir que agentes analistas (Alex) tomem decisÃµes de investimento baseadas em simulaÃ§Ãµes sintÃ©ticas ou feedback enviesado?*

---

## 2. A Hierarquia Quadripartite de ProveniÃªncia EconÃ´mica

```
[ NÃ­vel 4: EXTERNAL_VERIFIED (ConfianÃ§a: 0.8 - 1.0) ]
  - TransaÃ§Ãµes financeiras reais (Stripe, faturas pagas)
  - Contratos assinados / depÃ³sitos de prÃ©-reserva
  - Eventos de conversÃ£o verificados via webhook criptograficamente assinado

[ NÃ­vel 3: LOCAL_REAL (ConfianÃ§a: 0.6 - 0.8) ]
  - MÃ©tricas de telemetria interna e benchmarks de execuÃ§Ã£o
  - Logs de latÃªncia e consumo de tokens de produÃ§Ã£o

[ NÃ­vel 2: EXTERNAL_UNVERIFIED (ConfianÃ§a: 0.3 - 0.5) ]
  - MenÃ§Ãµes em fÃ³runs, posts no Reddit, enquetes pÃºblicas
  - Respostas verbais de entrevistas sem compromisso financeiro

[ NÃ­vel 1: SYNTHETIC (ConfianÃ§a: 0.0 - 0.2) ]
  - Personas simuladas por LLMs
  - Estimativas heurÃ­sticas e dados gerados por prompting
```

---

## 3. Regra InviolÃ¡vel de GovernanÃ§a
ProjeÃ§Ãµes de receita para missÃµes do JARVIS OS nÃ£o podem utilizar evidÃªncias de NÃ­vel 1 (`SYNTHETIC`) como prova de validaÃ§Ã£o de mercado (ver [[ADR-005 - Economic Evidence Provenance and Synthetic Data Capping]]).

---

## 4. Related Concepts
- [[Distinguishing Real vs Synthetic Market Evidence]]
- [[Market Opportunity Discovery and Scoring Matrix]]
- [[JARVIS EconomicExecutionGateway and Monetization]]

## Query Relevance
Por que projeções de receita não podem usar dados sintéticos como prova de validação.

