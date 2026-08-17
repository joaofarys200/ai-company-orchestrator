---
type: comparison
domain: security
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
difficulty: advanced
tags:
  - security
  - sandboxing
  - comparison
  - docker
  - namespaces
  - wasm
prerequisites:
  - "[[Least-Privilege Process Sandboxing and Execution Jail]]"
  - "[[Defensive Sandboxing and Linux Namespaces]]"
  - "[[WASM Sandboxing and Capability-Based Security]]"
related:
  - "[[Docker Container Security and Resource Capping]]"
  - "[[Zero Trust Architecture and Microsegmentation]]"
used_by:
  - "[[JARVIS Security Sandbox and Policy Engine]]"
failure_modes:
  - "[[Lesson - Bounded Autonomy Escape in Subprocess Invocation]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: Linux Namespaces vs Containers vs WebAssembly (IEEE Cloud Computing)
    type: PRIMARY_SOURCE
    url: https://ieeexplore.ieee.org/
---

# ⚖️ Comparison: Docker Container vs Linux Namespaces vs WASM Isolation

## 1. Tabela Comparativa de Sandboxing

| Dimensão | Subprocesso com Namespaces Linux | Container Docker (runc / containerd) | WASM Sandbox (Wasmtime) |
|---|---|---|---|
| **Tempo de Inicialização** | **$< 5\text{ms}$** | $300 - 1500\text{ms}$ | **$< 1\text{ms}$** |
| **Portabilidade de SO** | Apenas Linux (Requer kernel Linux) | Linux / macOS / Windows com WSL | **100% Cross-Platform (Bytecode WASM)** |
| **Superfície de Ataque do Kernel**| Expõe todas as syscalls filtradas por seccomp | Expõe syscalls do kernel compartilhado | **Zero syscalls por padrão (Isolamento de memória linear)** |
| **Compatibilidade de Binários** | Executa qualquer binário ELF do Linux | Executa qualquer imagem OCI completa | Requer compilação para target `wasm32-wasi` |

---

## 2. Decisão de Engenharia para o JARVIS

### When should JARVIS choose Subprocess / Namespaces?
- Para execução de ferramentas CLI nativas locais (Git, Python, Node.js) em máquinas Linux de desenvolvedor.

### When should JARVIS choose Docker Containers?
- Para compilação de projetos complexos com dependências de sistema pesadas (C++, Postgres, Redis em background).

### When should JARVIS choose WASM Sandboxing?
- Para execução de plugins e código de análise untrusted gerado dinamicamente por agentes de forma rápida e segura.

### What failure mode does each introduce?
- **Namespaces**: Configuração errada de flags `CLONE_NEWUSER` permitindo escalada de privilégios.
- **Docker**: Sobrecarga de memória e lentidão na criação/destruição de containers efêmeros.
- **WASM**: Incompatibilidade com bibliotecas que requerem multithreading avançado ou sockets de rede crus.

---

## 3. Related Concepts
- [[Least-Privilege Process Sandboxing and Execution Jail]]
- [[Defensive Sandboxing and Linux Namespaces]]
- [[WASM Sandboxing and Capability-Based Security]]
