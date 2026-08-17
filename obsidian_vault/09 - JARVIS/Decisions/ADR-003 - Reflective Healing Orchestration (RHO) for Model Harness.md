---
type: decision
domain: jarvis
difficulty: advanced
tags:
  - jarvis
  - adr
  - architectural-decision
  - rho
  - self-healing
status: verified
source_type: JARVIS_INTERNAL
confidence: high
---

# 📋 ADR-003 - Reflective Healing Orchestration (RHO) for Model Harness

## Status
**Aceite / Em Produção**

## Contexto
Durante tarefas de codificação autónoma, os agentes frequentemente enfrentam falhas transitórias de compilação, pequenos erros de digitação de imports ou asserções de testes não satisfeitas. Repetir cegamente a mesma chamada sem contexto gera desperdício de tokens, enquanto abortar a missão imediatamente para o utilizador quebra a promessa de autonomia do sistema.

## Decisão
Implementar a arquitetura **RHO (Reflective Healing Orchestrator)** e **SHE (Self-Healing Engine)** no `ModelHarness`, estruturada em:
1. Extração estruturada do erro (isolando tipo de exceção, linha e arquivo afetado);
2. Geração de reflexão semântica ("Por que falhou e qual a correção mínima?");
3. Injeção de prompt de auto-reparo delimitado com no máximo 3 tentativas e circuit breaker por hash de patch.

## Consequências
- **Positivas**: Aumento substancial na taxa de conclusão de missões sem intervenção humana; prevenção de loops infinitos.
- **Negativas**: Aumenta levemente a latência em caso de falhas consecutivas antes do fallback para o utilizador.

## Related Components
- [[JARVIS RHO and SHE Self-Healing Architecture]]
- [[Self-Healing Prompt Loops and Reflective Orchestration (RHO-SHE)]]
- [[JARVIS Model Harness Implementation]]
