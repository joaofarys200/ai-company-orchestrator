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

# ðŸ“‹ ADR-009 - RHO and SHE Rule Compaction and Max Turn Quotas

## Status
**Aceite / Em ProduÃ§Ã£o**

## Contexto
Durante ciclos consecutivos de auto-reparo (RHO/SHE), a acumulaÃ§Ã£o de reflexÃµes passadas e tentativas falhadas no prompt do agente faz o tamanho da janela de contexto crescer exponencialmente, degradando a atenÃ§Ã£o do modelo.

## Problema
Como manter o histÃ³rico de liÃ§Ãµes aprendidas durante uma sessÃ£o de codificaÃ§Ã£o sem sobrecarregar a janela de contexto.

## DecisÃ£o
Implementar a **CompactaÃ§Ã£o de Regras de ReflexÃ£o (Rule Compaction)** com Quota MÃ¡xima de 3 Turnos:
1. Limitar a no mÃ¡ximo 3 tentativas de auto-cura consecutivas por passo de missÃ£o.
2. Compactar o histÃ³rico de erros passados num resumo Ãºnico de 3 linhas estruturado em: `Falha Anterior | Causa Raiz | Nova RestriÃ§Ã£o`, descartando stacktraces brutos antigos.

## ConsequÃªncias
- **Positivas**: Reduz drasticamente o consumo de tokens e mantÃ©m o foco atencional do modelo aguÃ§ado.
- **Negativas**: Oculta detalhes histÃ³ricos secundÃ¡rios de tentativas descartadas.

## Tests
- `tests/test_model_harness_rho_she.py`

## Related ADRs
- [[ADR-003 - Reflective Healing Orchestration (RHO) for Model Harness]]
- [[ADR-006 - Context Engineering and AST Fallback Paring]]

## Query Relevance
Como a compactação de regras evita explosão de contexto no RHO e SHE.

