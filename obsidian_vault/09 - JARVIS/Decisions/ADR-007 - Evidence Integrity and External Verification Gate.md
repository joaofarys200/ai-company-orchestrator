---
type: decision
domain: jarvis
difficulty: intermediate
tags:
  - jarvis
  - adr
  - architectural-decision
  - evidence
  - validation-gate
  - economics
status: verified
source_type: JARVIS_INTERNAL
confidence: high
freshness: stable
---

# 📋 ADR-007 - Evidence Integrity and External Verification Gate

## Status
**Aceite / Em Produção**

## Contexto
Agentes de análise de produto e estratégia (Alex) geram relatórios de viabilidade de mercado. Sem uma barreira de verificação, o sistema corre o risco de executar missões de engenharia e deploys baseando-se em premissas simuladas e alucinações.

## Problema
Como garantir que nenhuma missão de escala ou lançamento de produto seja executada sem evidências verificadas no mundo real.

## Decisão
Estabelecer o **External Verification Gate**:
Nenhuma proposta de produto pode transitar do estado `RESEARCH` para `BUILD_AND_DEPLOY` sem que a pontuação de evidência contenha pelo menos um comprovativo de nível `EXTERNAL_VERIFIED` (ex: transação Stripe, webhook assinado ou confirmação por email real).

## Alternativas
1. Confiar no score de confiança gerado pelo próprio LLM (Provado falho devido a viés de adulação / Sycophancy).
2. Exigir aprovação manual humana em 100% dos passos (Reduz severamente a autonomia).

## Trade-offs
Introduz uma barreira rígida que bloqueia missões fictícias, exigindo criação prévia de landing page e smoke test.

## Consequências
- **Positivas**: Elimina alocação de recursos em alucinações comerciais.
- **Negativas**: Exige fluxo em duas fases para projetos de SaaS.

## Security Impact
Protege o sistema contra auto-aprovação fraudulenta de gastos de infraestrutura.

## Tests
- `tests/test_financial_analytics.py`

## Related ADRs
- [[ADR-005 - Economic Evidence Provenance and Synthetic Data Capping]]
- [[ADR-013 - Economic Evidence Provenance and Confidence Capping]]
