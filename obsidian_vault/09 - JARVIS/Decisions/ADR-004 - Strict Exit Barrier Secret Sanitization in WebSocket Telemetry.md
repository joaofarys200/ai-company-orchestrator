---
type: decision
domain: jarvis
difficulty: intermediate
tags:
  - jarvis
  - adr
  - architectural-decision
  - security
  - secrets
  - websockets
status: verified
source_type: JARVIS_INTERNAL
confidence: high
---

# ðŸ“‹ ADR-004 - Strict Exit Barrier Secret Sanitization in WebSocket Telemetry

## Status
**Aceite / Em ProduÃ§Ã£o**

## Contexto
A transmissÃ£o de eventos e saÃ­das de terminal em tempo real via WebSocket para a interface desktop corre o risco de expor credenciais sensÃ­veis (Personal Access Tokens do GitHub, chaves de API, senhas locais) que aparecem em mensagens de erro ou logs de ferramentas (ver [[Lesson - Accidental Secret Leaks in Telemetry Broadcast]]).

## DecisÃ£o
Estabelecer um **Invariante de Barreira de SaÃ­da (Exit Barrier)** no `ConnectionManager` do `server.py`:
Todo payload JSON antes de ser serializado e emitido no mÃ©todo `broadcast()` Ã© obrigatoriamente processado por um filtro heurÃ­stico de entropia de Shannon e expressÃµes regulares que substitui tokens por `[REDACTED_SECRET]`.

## ConsequÃªncias
- **Positivas**: EliminaÃ§Ã£o garantida de vazamentos acidentais de segredos na interface do usuÃ¡rio e logs persistidos do cliente.
- **Negativas**: Pequeno custo de processamento CPU por frame de streaming.

## Related Components
- [[JARVIS WebSocket Telemetry and Dispatcher Protocol]]
- [[Credential Sanitization and Secret Masking]]
- [[Shannon Entropy and Heuristic Secret Scanners]]

## Query Relevance
Sanitização estrita de segredos na barreira de saída websocket exit barrier.

