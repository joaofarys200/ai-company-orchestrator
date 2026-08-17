---
type: concept
domain: backend-systems
difficulty: intermediate
tags:
  - backend
  - fastapi
  - websockets
  - async
  - real-time
status: verified
---

# ⚡ FastAPI and WebSocket Lifecycle Management

## 1. Definição & Ciclo de Vida da Conexão
Diferente de requisições HTTP sem estado (*stateless*), uma conexão **WebSocket (RFC 6455)** estabelece um túnel TCP bidirecional persistente e de baixa latência entre o frontend/clientes e o backend do **JARVIS OS**.

```
Cliente (UI/Desktop)                                         FastAPI Backend
       |                                                            |
       | ---- HTTP GET /ws (Upgrade: websocket) ------------------> |
       | <--- HTTP 101 Switching Protocols ------------------------ |
       |                                                            |
       | <============== Túnel Full-Duplex Bidirecional ===========> |
       |                                                            |
       | ---- Ping (Heartbeat a cada 30s) ------------------------> |
       | <--- Pong (Confirmação de liveness) ---------------------- |
       |                                                            |
       | ---- Frame de Fecho (1000 Normal Closure) ---------------> |
       | <--- Frame de Fecho ACK ---------------------------------- |
```

---

## 2. Padrão ConnectionManager com Heartbeat e Broadcast

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
import asyncio
import json

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message_type: str, payload: Dict[str, Any]):
        """Envia mensagem para todos os clientes ativos sem bloquear em conexões lentas."""
        message = json.dumps({"type": message_type, "data": payload})
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                dead_connections.append(connection)

        # Limpar conexões mortas
        for dead in dead_connections:
            self.disconnect(dead)

manager = ConnectionManager()

@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Manter escuta ativa e responder a pings
            data = await websocket.receive_text()
            # Processar comandos recebidos se houver
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
```

---

## 3. Gestão de Desconexões e Zumbis
- **Heartbeat / Ping-Pong**: Enviar pings a cada 30 segundos. Se o cliente não responder ao pong dentro de 10 segundos, a conexão é encerrada ativamente no servidor para libertar descritores de ficheiros de rede (*sockets*).
- **Graceful Shutdown no FastAPI**: No evento `@app.on_event("shutdown")` ou lifespan context manager, notificar todos os clientes com código `1001 Going Away` antes de fechar os sockets.

---

## 4. Related Concepts
- [[Message Queues and Event-Driven Architectures]]
- [[SQLite WAL Mode and Concurrency]]
- [[Structured Outputs and Schema Validation]]

---

## 5. Sources
- *RFC 6455 - The WebSocket Protocol*: https://datatracker.ietf.org/doc/html/rfc6455
- *FastAPI WebSockets Documentation*: https://fastapi.tiangolo.com/advanced/websockets/
