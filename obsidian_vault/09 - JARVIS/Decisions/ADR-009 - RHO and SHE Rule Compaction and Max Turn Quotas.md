---
type: decision
domain: jarvis
difficulty: intermediate
tags:
  - jarvis
  - adr
  - architectural-decision
  - rho
  - she
  - rule-compaction
status: verified
source_type: JARVIS_INTERNAL
confidence: high
freshness: stable
---

# 📋 ADR-009 - RHO and SHE Rule Compaction and Max Turn Quotas

## Status
**Aceite / Em Produção**

## Contexto
Durante ciclos consecutivos de auto-reparo (RHO/SHE), a acumulação de reflexões passadas e tentativas falhadas no prompt do agente faz o tamanho da janela de contexto crescer exponencialmente, degradando a atenção do modelo.

## Problema
Como manter o histórico de lições aprendidas durante uma sessão de codificação sem sobrecarregar a janela de contexto.

## Decisão
Implementar a **Compactação de Regras de Reflexão (Rule Compaction)** com Quota Máxima de 3 Turnos:
1. Limitar a no máximo 3 tentativas de auto-cura consecutivas por passo de missão.
2. Compactar o histórico de erros passados num resumo único de 3 linhas estruturado em: `Falha Anterior | Causa Raiz | Nova Restrição`, descartando stacktraces brutos antigos.

## Consequências
- **Positivas**: Reduz drasticamente o consumo de tokens e mantém o foco atencional do modelo aguçado.
- **Negativas**: Oculta detalhes históricos secundários de tentativas descartadas.

## Tests
- `tests/test_model_harness_rho_she.py`

## Related ADRs
- [[ADR-003 - Reflective Healing Orchestration (RHO) for Model Harness]]
- [[ADR-006 - Context Engineering and AST Fallback Paring]]

## Query Relevance
Como a compactação de regras evita explosão de contexto no RHO e SHE.

