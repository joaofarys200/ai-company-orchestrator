---
type: concept
domain: devops
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
difficulty: advanced
tags:
  - devops
  - security
  - ebpf
  - syscalls
  - tracing
  - sandbox-auditing
prerequisites:
  - "[[Defensive Sandboxing and Linux Namespaces]]"
  - "[[Least-Privilege Process Sandboxing and Execution Jail]]"
related:
  - "[[Structured Logging and Distributed Trace Context]]"
  - "[[Zero Trust Architecture and Microsegmentation]]"
used_by:
  - "[[JARVIS Security Sandbox and Policy Engine]]"
failure_modes:
  - "[[Lesson - Bounded Autonomy Escape in Subprocess Invocation]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: Linux Kernel Documentation - Extended BPF (eBPF)
    type: PRIMARY_SOURCE
    url: https://ebpf.io/what-is-ebpf/
  - title: Cilium / Tetragon - eBPF-based Security Observability and Runtime Enforcement
    type: PRIMARY_SOURCE
    url: https://tetragon.io/
---

# 🕵️ eBPF Syscall Tracing and Sandbox Process Auditing

## 1. Pergunta Central
> *Como auditar em tempo real e de forma não-intrusiva todas as chamadas de sistema (syscalls de arquivo, rede e execução) disparadas por processos de agentes sem modificar o código-fonte da aplicação nem sofrer o overhead do `ptrace`?*

---

## 2. A Arquitetura eBPF no Kernel Linux
O **eBPF (Extended Berkeley Packet Filter)** permite carregar e executar programas de bytecode restritos diretamente dentro do espaço do kernel Linux em resposta a eventos de tracepoints e kprobes:

```
[ Espaço de Usuário: Subprocesso do Agente Devon ] -> Executa `openat('/etc/shadow')`
                              |
                     (Syscall Trap no Kernel)
                              |
                              v
[ Kernel Linux: Tracepoint `sys_enter_openat` ]
  - Executa Programa eBPF (Verificado com Segurança Sem Travar o SO)
  - Inspeciona Parâmetros: Caminho do Arquivo, PID do Processo, Cgroup ID
  - Se Viola Política de Sandboxing -> Emite Sinal SIGKILL ou Alerta Instantâneo
                              |
                              v (Buffer em Anel / Ring Buffer sem Cópias)
[ Daemon de Auditoria JARVIS (Espaço de Usuário) ]
```

---

## 3. Principais Syscalls Auditadas em Agentes
- `sys_enter_execve` / `execveat`: Detecta tentativa de execução de binários externos.
- `sys_enter_connect` / `bind`: Detecta abertura de sockets de rede fora da loopback autorizada.
- `sys_enter_unlinkat`: Detecta exclusão de arquivos críticos no sistema anfitrião.

---

## 4. Related Concepts
- [[Defensive Sandboxing and Linux Namespaces]]
- [[Least-Privilege Process Sandboxing and Execution Jail]]
- [[Zero Trust Architecture and Microsegmentation]]
