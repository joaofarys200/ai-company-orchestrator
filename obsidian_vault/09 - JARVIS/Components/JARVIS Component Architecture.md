---
type: architecture
domain: jarvis
difficulty: intermediate
tags:
  - jarvis
  - architecture
  - components
  - fastapi
  - websockets
status: verified
---

# ⚙️ JARVIS Component Architecture

## 1. Mapeamento de Componentes do Repositório

| Componente | Ficheiro Fonte | Função Primária no JARVIS |
|---|---|---|
| **API Server** | [`server.py`](file:///c:/Users/joaor/Desktop/JarvisOS/server.py) | Ponto de entrada FastAPI, gestão de rotas REST, despacho de comandos de voz |
| **State & Database** | [`database.py`](file:///c:/Users/joaor/Desktop/JarvisOS/database.py) | Gestão de conexões SQLite, schema de tabelas de missões e telemetria |
| **Security Sandbox** | [`sandbox.py`](file:///c:/Users/joaor/Desktop/JarvisOS/sandbox.py) | Isolamento de processos de terminal, restrição de diretórios e timeouts |
| **Workspace Policy** | [`workspace_policy.py`](file:///c:/Users/joaor/Desktop/JarvisOS/workspace_policy.py) | Regras estritas de permissões de caminhos e bloqueio de comandos destrutivos |
| **Voice Streaming** | [`voice_service.py`](file:///c:/Users/joaor/Desktop/JarvisOS/voice_service.py) | Captura de áudio local, síntese TTS e interface de escuta contínua |
| **Gemini Live** | [`gemini_live.py`](file:///c:/Users/joaor/Desktop/JarvisOS/gemini_live.py) | Sessão WebSocket bidirecional de baixa latência com a API Gemini Live |
| **Swarm Orchestrator**| [`agents/swarm.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/swarm.py) | Coordenação entre agentes especialistas e resolução de tarefas complexas |
| **Obsidian RAG** | [`agents/obsidian_tools.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/obsidian_tools.py) | Recuperação automática de contexto a partir do cofre Obsidian local |

---

## 2. Fluxo de Dados entre Componentes

```
[ Frontend / Desktop App ]
            | (WebSocket /ws/telemetry & HTTP REST)
            v
       [ server.py ] <---> [ voice_service.py / gemini_live.py ]
            |
            +---> [ agents/swarm.py ]
            |            |
            |            +---> [ agents/obsidian_tools.py ] ---> [ obsidian_vault/ ]
            |            |
            |            +---> [ sandbox.py ] ---> [ workspace/sandbox_dir ]
            |
            v
     [ database.py ] ---> [ database.db (SQLite WAL) ]
```

---

## 3. Related Concepts
- [[JARVIS System Architecture]]
- [[JARVIS Autonomous Agent Hierarchy]]
- [[FastAPI and WebSocket Lifecycle Management]]
- [[SQLite WAL Mode and Concurrency]]

---

## 4. Sources
- *JARVIS OS Codebase Architecture Map — `ARCHITECTURE_MAP_REVIEW.md`*
