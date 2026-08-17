---
type: concept
domain: security
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: advanced
tags:
  - security
  - sandboxing
  - namespaces
  - cgroups
  - isolation
prerequisites:
  - "[[Least-Privilege Process Sandboxing and Execution Jail]]"
related:
  - "[[Docker Container Security and Resource Capping]]"
  - "[[Threat Modeling for Autonomous Coding Agents]]"
used_by:
  - "[[JARVIS Security Sandbox and Policy Engine]]"
failure_modes:
  - "[[Lesson - Bounded Autonomy Escape in Subprocess Invocation]]"
implementation:
  - "[[ADR-002 - Process Sandboxing and Path Jail Enforcement]]"
sources:
  - title: Linux Kernel Documentation - Namespaces and Cgroups
    type: PRIMARY_SOURCE
    url: https://docs.kernel.org/admin-guide/cgroup-v2.html
---

# 🧱 Defensive Sandboxing and Linux Namespaces

## 1. Pergunta Central
> *Quais são as primitivas do kernel (Namespaces, Cgroups e Seccomp) que garantem que um subprocesso de IA seja incapaz de inspecionar outros processos, esgotar recursos do host ou escapar para o sistema de ficheiros raiz?*

---

## 2. As 7 Dimensões de Isolamento por Namespaces

| Namespace | Recurso Isolado | Proteção no Sandboxing |
|---|---|---|
| **PID (Process ID)** | Tabela de Processos | O subprocesso enxerga apenas a si mesmo como `PID 1`; não pode dar `kill` em outros processos |
| **MNT (Mount)** | Árvore de Ficheiros | O processo vê apenas uma raiz isolada montada em RAM (`tmpfs`) ou diretório restrito |
| **NET (Network)** | Interfaces de Rede | Isolamento de loopback; desativação de sockets externos não autorizados |
| **UTS (Hostname)** | Nome do Host / Domínio | Previne spoofing do hostname do sistema anfitrião |
| **IPC (Inter-Process)** | Memória Partilhada & Semáforos | Previne espionagem de memória partilhada POSIX de outros processos |
| **USER** | Mapeamento UID/GID | O usuário `root` dentro do namespace mapeia para um UID não-privilegiado no host |
| **CGROUP** | Hierarquia de Limites | Limita consumo de RAM (ex: máx 1024MB) e CPU (ex: 2 cores) |

---

## 3. Related Concepts
- [[Least-Privilege Process Sandboxing and Execution Jail]]
- [[Docker Container Security and Resource Capping]]
- [[Seguranca_Defensiva_DevSecOps_e_Sandboxing]]
