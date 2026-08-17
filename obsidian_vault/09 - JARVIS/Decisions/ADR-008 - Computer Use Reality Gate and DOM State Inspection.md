---
type: decision
domain: jarvis
difficulty: advanced
tags:
  - jarvis
  - adr
  - architectural-decision
  - computer-use
  - playwright
  - reality-gate
status: verified
source_type: JARVIS_INTERNAL
confidence: high
freshness: stable
---

# 📋 ADR-008 - Computer Use Reality Gate and DOM State Inspection

## Status
**Aceite / Em Produção**

## Contexto
Automação de interface web por IA via coordenadas de pixels puras frequentemente clica em elementos fantasmas, modais fechados ou botões desabilitados, assumindo incorretamente que a ação foi bem-sucedida.

## Problema
Como verificar de forma inequívoca que uma ação no navegador produziu o efeito esperado na aplicação web.

## Decisão
Implementar o **Reality Gate de Computer Use**:
Toda ação de clique ou preenchimento no Playwright deve ser seguida obrigatoriamente por uma inspeção do estado do DOM (ex: verificar se um spinner desapareceu, se a URL mudou ou se o nó alvo mudou de atributo `aria-disabled`), combinada com captura de tela multimodal quando necessário.

## Alternativas
1. Confiar unicamente na ausência de exceção no método `click()` (Gera falsos positivos quando eventos de clique são ignorados por lag de hidratação).
2. Aguardar tempos fixos com `time.sleep()` (Lento e não-determinístico).

## Trade-offs
Adiciona pequenas chamadas de inspeção assíncrona após cada passo, garantindo 100% de confiabilidade.

## Tests
- `tests/test_tools.py`

## Related ADRs
- [[ADR-002 - Process Sandboxing and Path Jail Enforcement]]
