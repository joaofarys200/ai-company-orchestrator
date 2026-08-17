---
type: architecture
domain: jarvis
difficulty: intermediate
tags:
  - jarvis
  - architecture
  - system-overview
  - swarm
status: verified
---

# 🧠 JARVIS System Architecture

## 1. Visão Geral do Sistema
O **JARVIS OS** é uma plataforma desktop para orquestração local de agentes de inteligência artificial autónomos. A arquitetura é desenhada em torno de um núcleo assíncrono em Python (FastAPI + WebSockets), uma camada de interface desktop moderna (Electron / Vite / Vanilla CSS), uma base de dados local SQLite otimizada em modo WAL e uma camada de memória externa em Obsidian.

```
+--------------------------------------------------------------------+
|                   INTERFACE DE UTILIZADOR (Desktop UI)             |
|   - Electron / Vanilla Webview                                     |
|   - WebSocket Full-Duplex Client (`/ws/telemetry`)                 |
|   - Terminal Interativo & Visualizador de Grafos de Missão        |
+---------------------------------+----------------------------------+
                                  | WebSocket (JSON-RPC Telemetry)
                                  v
+--------------------------------------------------------------------+
|                   CAMADA DE SERVIÇOS & API (Backend)               |
|   - `server.py`: FastAPI, Endpoints REST, Gestão de Conexões       |
|   - `gemini_live.py`: Sessões interativas de áudio bidirecional    |
|   - `voice_service.py`: Síntese e reconhecimento de voz local      |
+---------------------------------+----------------------------------+
                                  |
                                  v
+--------------------------------------------------------------------+
|                   SWARM & ORQUESTRAÇÃO DE AGENTES                  |
|   - `agents/swarm.py`: SwarmOrchestrator & Coordenação             |
|   - Clara (Gestão & Planeamento)                                   |
|   - Devon (Engenharia de Software & AST Patching)                  |
|   - Alex (Validação de Negócio & Pesquisa de Mercado)              |
|   - Quinn (Qualidade, Testes & Auditoria de Segurança)             |
+------------------+------------------------------+------------------+
                   |                              |
                   v                              v
+-----------------------------+    +-----------------------------+
|    PERSISTÊNCIA LOCAL       |    |   SANDBOX & POLÍTICAS       |
|  - `database.py` (SQLite WAL)|    |  - `sandbox.py` (Isolamento)|
|  - `obsidian_vault/` (RAG)  |    |  - `workspace_policy.py`    |
+-----------------------------+    +-----------------------------+
```

---

## 2. Separação de Responsabilidades
1. **Frontend / UI**: Apresenta telemetria em tempo real, estado das missões, terminal de sandbox e logs higienizados.
2. **Orquestrador Swarm**: Distribui tarefas atómicas com base num Grafo Acíclico Dirigido (DAG).
3. **Sandbox de Execução**: Garante que o código modificado ou executado pelos agentes não corrompe o anfitrião.
4. **Cofre Obsidian**: Memória externa desacoplada com tratados, padrões de engenharia e runbooks.

---

## 3. Related Concepts
- [[JARVIS Component Architecture]]
- [[JARVIS Autonomous Agent Hierarchy]]
- [[JARVIS State Store and Persistence]]
- [[Clean Architecture and Hexagonal Ports]]

---

## 4. Sources
- *JARVIS OS Codebase — `server.py`, `README.md`, `ARCHITECTURE_MAP_REVIEW.md`*
