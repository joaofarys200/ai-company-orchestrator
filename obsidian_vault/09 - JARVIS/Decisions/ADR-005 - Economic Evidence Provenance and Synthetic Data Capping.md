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
---

# 📋 ADR-005 - Economic Evidence Provenance and Synthetic Data Capping

## Status
**Aceite / Em Produção**

## Contexto
Agentes de análise económica (Alex) tendem a alucinar viabilidade de produtos ao aceitar dados sintéticos de personas simuladas como se fossem validações empíricas de mercado, gerando relatórios de oportunidade com falso otimismo (ver [[Lesson - Synthetic Evidence Hallucination in Market Validation]]).

## Decisão
Implementar uma **Classificação Quadripartite de Evidência** no motor económico:
1. `SYNTHETIC`: Dados gerados por LLM ou simulação (Fator de Confiança fixo em máx $0.2$).
2. `LOCAL_REAL`: Dados locais de testes unitários ou benchmarks em hardware.
3. `EXTERNAL_UNVERIFIED`: Menções em fóruns ou redes sociais sem comprovativo transacional.
4. `EXTERNAL_VERIFIED`: Transações Stripe auditadas, depósitos ou lista de espera verificada com emails reais (Fator de Confiança $\ge 0.7$).

## Consequências
- **Positivas**: Eliminação de investimentos de engenharia em ideias baseadas em alucinação sintética; disciplina epistêmica.
- **Negativas**: Exige testes empíricos reais (landing pages, smoke tests) antes da aprovação de planos de escala.

## Related Components
- [[JARVIS EconomicExecutionGateway and Monetization]]
- [[JARVIS EvidenceGateway and Market Verification Gate]]
- [[Distinguishing Real vs Synthetic Market Evidence]]
