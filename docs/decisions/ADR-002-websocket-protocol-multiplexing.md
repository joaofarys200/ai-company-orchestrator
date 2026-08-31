# ADR-002: Single-Port Multiplexed Duplex WebSocket Protocol

## Context
A real-time desktop AI operating system requires bi-directional streaming for voice audio, chat tokens, live terminal output, Monaco editor buffer synchronization, Kanban mission cards, and Security Sentinel threat alerts. Using separate HTTP polling endpoints creates excessive overhead, connection exhaustion, and state desynchronization.

## Decision
We implemented a **single-port duplex WebSocket protocol** (`ws://127.0.0.1:8000/ws`) with strict message multiplexing:
1. **Canonical Schema Contract (`websocket_schema.py` & `backend/websocket/contracts.py`)**: All inbound and outbound frames use a typed envelope containing a `type` opcode and domain-specific payload.
2. **Central Dispatcher Registry (`WebSocketDispatcher`)**: Handlers are grouped by functional domains (`chat`, `voice`, `projects`, `coding`, `missions`, `sentinel`, `lectures`, `knowledge`). The dispatcher verifies at server startup that all message types in the protocol have registered handlers (`missing == []` and `extra == []`).
3. **Reactive Initial Synchronization (`InitialSyncHandler`)**: Upon WebSocket connection establishment, the server broadcasts an immediate aggregate snapshot containing the active project context, rules, architecture notes, Kanban state, and Sentinel status.

## Alternatives Considered
- *REST API with Server-Sent Events (SSE)*: Rejected because SSE is unidirectional (server-to-client only), requiring separate HTTP POST requests for client interactions.
- *gRPC / Protocol Buffers*: Rejected to keep the frontend client dependency footprint lightweight and easily inspectable in browser dev tools.

## Consequences
- **Positive**: Low latency (&lt;10ms local loopback); atomic bootstrap sync; simple connection lifecycle management in React (`WebSocketContext.tsx`).
- **Negative**: Requires strict protocol assertion tests to ensure backend Python contracts and frontend TypeScript types stay synchronized.

## Status
**ACCEPTED** (Implemented in `backend/websocket/`).
