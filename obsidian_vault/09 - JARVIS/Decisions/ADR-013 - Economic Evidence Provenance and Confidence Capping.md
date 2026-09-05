---
type: decision
domain: jarvis
difficulty: intermediate
tags:
  - jarvis
  - adr
  - architectural-decision
  - economics
  - evidence
  - provenance
status: verified
source_type: JARVIS_INTERNAL
confidence: high
freshness: stable
---

# 📋 ADR-013 - Economic Evidence Provenance and Confidence Capping

## Status
**Aceite / Em Produção**

## Contexto
Agentes analistas (Alex) tendem a inflar a viabilidade de modelos de negócio quando geram personas simuladas e tratam suas respostas elogiosas como prova de tração de mercado.

## Problema
Como impor limites matemáticos invioláveis sobre o fator de confiança de relatórios de mercado baseados em dados sintéticos.

## Decisão
Implementar um **Teto Rígido de Confiança (Confidence Capping)** no cálculo de viabilidade económica:
1. Toda evidência categorizada como `SYNTHETIC` tem seu peso limitado a no máximo $w_{\text{synthetic}} = 0.20$.
2. O score final de viabilidade $V \in [0, 1]$ não pode ultrapassar $0.35$ a menos que contenha evidência `EXTERNAL_VERIFIED` ($w_{\text{verified}} \ge 0.80$).

## Consequences
- **Positivas**: Elimina a tomada de decisão automatizada com base em alucinação económica.
- **Negativas**: Exige smoke tests reais antes de aprovar orçamentos de engenharia.

## Tests
- `tests/test_financial_analytics.py`

## Related ADRs
- [[ADR-005 - Economic Evidence Provenance and Synthetic Data Capping]]
- [[ADR-007 - Evidence Integrity and External Verification Gate]]

## Query Relevance
Qual o teto de confiança máximo permitido para personas simuladas e dados sintéticos.

