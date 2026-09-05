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

# 📋 ADR-004 - Strict Exit Barrier Secret Sanitization in WebSocket Telemetry

## Status
**Aceite / Em Produção**

## Contexto
A transmissão de eventos e saídas de terminal em tempo real via WebSocket para a interface desktop corre o risco de expor credenciais sensíveis (Personal Access Tokens do GitHub, chaves de API, senhas locais) que aparecem em mensagens de erro ou logs de ferramentas (ver [[Lesson - Accidental Secret Leaks in Telemetry Broadcast]]).

## Decisão
Estabelecer um **Invariante de Barreira de Saída (Exit Barrier)** no `ConnectionManager` do `server.py`:
Todo payload JSON antes de ser serializado e emitido no método `broadcast()` é obrigatoriamente processado por um filtro heurístico de entropia de Shannon e expressões regulares que substitui tokens por `[REDACTED_SECRET]`.

## Consequências
- **Positivas**: Eliminação garantida de vazamentos acidentais de segredos na interface do usuário e logs persistidos do cliente.
- **Negativas**: Pequeno custo de processamento CPU por frame de streaming.

## Related Components
- [[JARVIS WebSocket Telemetry and Dispatcher Protocol]]
- [[Credential Sanitization and Secret Masking]]
- [[Shannon Entropy and Heuristic Secret Scanners]]

## Query Relevance
Sanitização estrita de segredos na barreira de saída websocket exit barrier.

