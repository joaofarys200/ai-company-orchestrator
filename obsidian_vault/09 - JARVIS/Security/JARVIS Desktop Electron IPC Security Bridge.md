---
type: architecture
domain: jarvis
status: verified
source_type: JARVIS_INTERNAL
confidence: high
freshness: stable
difficulty: advanced
tags:
  - jarvis
  - electron
  - ipc
  - security-bridge
  - context-isolation
  - desktop
prerequisites:
  - "[[Least-Privilege Process Sandboxing and Execution Jail]]"
  - "[[Zero Trust Architecture and Microsegmentation]]"
related:
  - "[[JARVIS WebSocket Telemetry and Dispatcher Protocol]]"
  - "[[JARVIS System Architecture]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[Lesson - Accidental Secret Leaks in Telemetry Broadcast]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: JARVIS Codebase - main.js, preload.js and Electron security configuration
    type: JARVIS_INTERNAL
    url: internal://main.js
---

# 🖥️ JARVIS Desktop Electron IPC Security Bridge

## 1. Purpose
A ponte de comunicação IPC do Electron gerencia a fronteira de segurança entre a interface visual de renderização (HTML/CSS/JS da UI) e o processo principal do Node.js/Python anfitrião, impedindo que código do frontend execute comandos do sistema operacional diretamente.

---

## 2. Responsibilities
- Habilitar `contextIsolation: true` e `nodeIntegration: false` em todas as janelas do `BrowserWindow`.
- Expor uma API mínima, tipada e segura através de `contextBridge.exposeInMainWorld('jarvisAPI', {...})` em `preload.js`.
- Interceptar e validar todas as mensagens IPC (`ipcMain.handle` e `ipcRenderer.invoke`).
- Bloquear a navegação do webview para URLs externas não autorizadas.

---

## 3. Inputs & Outputs
- **Inputs**: Eventos de clique, seleção de arquivos e atalhos de teclado do utilizador.
- **Outputs**: Payloads serializados IPC transmitidos para o processo principal.

---

## 4. Dependencies
- [`main.js`](file:///c:/Users/joaor/Desktop/JarvisOS/main.js)
- `preload.js`

---

## 5. Security Boundaries
- O processo de renderização não possui acesso direto a `require('child_process')` ou `require('fs')`.

---

## 6. Related Concepts
- [[Least-Privilege Process Sandboxing and Execution Jail]]
- [[Zero Trust Architecture and Microsegmentation]]
- [[JARVIS WebSocket Telemetry and Dispatcher Protocol]]
