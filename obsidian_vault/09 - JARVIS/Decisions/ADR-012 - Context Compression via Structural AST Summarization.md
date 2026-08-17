---
type: decision
domain: jarvis
difficulty: advanced
tags:
  - jarvis
  - adr
  - architectural-decision
  - context-compression
  - ast
  - token-budget
status: verified
source_type: JARVIS_INTERNAL
confidence: high
freshness: stable
---

# 📋 ADR-012 - Context Compression via Structural AST Summarization

## Status
**Aceite / Em Produção**

## Contexto
Agentes precisam de uma visão panorâmica de múltiplos arquivos de um repositório para entender a arquitetura sem esgotar o orçamento de tokens com código que não será modificado.

## Problema
Como fornecer uma representação precisa de toda a base de código mantendo o tamanho do prompt em menos de 10% da janela de contexto.

## Decisão
Implementar a **Compressão Estrutural por Esqueleto de AST (Structural AST Summarization)**:
Gerar resumos estruturais onde apenas assinaturas de classes, métodos, decorators e docstrings de alto nível são extraídos via AST, omitindo 100% dos corpos de funções (`pass` ou `...`).

## Exemplo
```python
# Gerado via AST Compressor
class MissionStateStore:
    def __init__(self, db_path: str) -> None: ...
    def save_checkpoint(self, mission_id: str, state: MissionState) -> None: ...
    def get_latest_checkpoint(self, mission_id: str) -> Optional[MissionState]: ...
```

## Consequences
- **Positivas**: Redução de $85\%$ no volume de tokens necessários para representar módulos do repositório.
- **Negativas**: O agente deve invocar a ferramenta de leitura pontual se precisar do corpo de uma função auxiliar.

## Tests
- `tests/test_context_builder.py`

## Related ADRs
- [[ADR-006 - Context Engineering and AST Fallback Paring]]
