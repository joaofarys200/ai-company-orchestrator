---
type: decision
domain: jarvis
difficulty: advanced
tags:
  - jarvis
  - adr
  - architectural-decision
  - ast
  - context-engineering
status: verified
source_type: JARVIS_INTERNAL
confidence: high
freshness: stable
---

# 📋 ADR-006 - Context Engineering and AST Fallback Paring

## Status
**Aceite / Em Produção**

## Contexto
Ao enviar arquivos de código grandes para modelos de linguagem durante a resolução de bugs, incluir arquivos inteiros com milhares de linhas satura a janela de contexto e eleva custos desnecessariamente.

## Problema
Como fornecer contexto de código suficiente para o agente entender assinaturas e tipos sem estourar o limite de tokens nem quebrar o raciocínio sintático.

## Decisão
Implementar um mecanismo de **Poda Estrutural por AST (AST Fallback Paring)**:
Se um arquivo exceder 300 linhas, o construtor de contexto preserva integralmente apenas o corpo da função alvo, substituindo os corpos de todas as outras classes e funções vizinhas por `... # [AST Pruned: Body omitted for context efficiency]`.

## Alternativas
1. Truncamento linear por contagem de caracteres (Quebra sintaxe e gera erros de indentação).
2. Não podar arquivos (Leva a context explosion e 429 rate limits).

## Trade-offs
Reduz o consumo de tokens em até 70%, mas oculta detalhes de implementação de métodos auxiliares (exige que o agente requisite o método específico se precisar inspecioná-lo).

## Consequências
- **Positivas**: Economia maciça de tokens e foco atencional do modelo na função defeituosa.
- **Negativas**: Requer parsing de AST rápido em Python e TypeScript.

## Security Impact
Nenhum impacto adverso de segurança; código permanece analisado na sandbox local.

## Failure Modes
- Falha ao parsear arquivos com erros de sintaxe existentes (o sistema faz fallback seguro para truncamento com âncoras de linhas).

## Tests
- `tests/test_context_builder.py`

## Related ADRs
- [[ADR-012 - Context Compression via Structural AST Summarization]]
- [[ADR-003 - Reflective Healing Orchestration (RHO) for Model Harness]]
