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

# ðŸ“‹ ADR-013 - Economic Evidence Provenance and Confidence Capping

## Status
**Aceite / Em ProduÃ§Ã£o**

## Contexto
Agentes analistas (Alex) tendem a inflar a viabilidade de modelos de negÃ³cio quando geram personas simuladas e tratam suas respostas elogiosas como prova de traÃ§Ã£o de mercado.

## Problema
Como impor limites matemÃ¡ticos inviolÃ¡veis sobre o fator de confianÃ§a de relatÃ³rios de mercado baseados em dados sintÃ©ticos.

## DecisÃ£o
Implementar um **Teto RÃ­gido de ConfianÃ§a (Confidence Capping)** no cÃ¡lculo de viabilidade econÃ³mica:
1. Toda evidÃªncia categorizada como `SYNTHETIC` tem seu peso limitado a no mÃ¡ximo $w_{\text{synthetic}} = 0.20$.
2. O score final de viabilidade $V \in [0, 1]$ nÃ£o pode ultrapassar $0.35$ a menos que contenha evidÃªncia `EXTERNAL_VERIFIED` ($w_{\text{verified}} \ge 0.80$).

## Consequences
- **Positivas**: Elimina a tomada de decisÃ£o automatizada com base em alucinaÃ§Ã£o econÃ³mica.
- **Negativas**: Exige smoke tests reais antes de aprovar orÃ§amentos de engenharia.

## Tests
- `tests/test_financial_analytics.py`

## Related ADRs
- [[ADR-005 - Economic Evidence Provenance and Synthetic Data Capping]]
- [[ADR-007 - Evidence Integrity and External Verification Gate]]

## Query Relevance
Qual o teto de confiança máximo permitido para personas simuladas e dados sintéticos.

