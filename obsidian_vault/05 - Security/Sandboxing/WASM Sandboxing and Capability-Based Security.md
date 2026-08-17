---
type: concept
domain: security
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
difficulty: advanced
tags:
  - security
  - sandboxing
  - wasm
  - wasi
  - capability-security
  - isolation
prerequisites:
  - "[[Least-Privilege Process Sandboxing and Execution Jail]]"
  - "[[Defensive Sandboxing and Linux Namespaces]]"
related:
  - "[[Zero Trust Architecture and Microsegmentation]]"
  - "[[Docker Container Security and Resource Capping]]"
used_by:
  - "[[JARVIS Security Sandbox and Policy Engine]]"
failure_modes:
  - "[[Lesson - Bounded Autonomy Escape in Subprocess Invocation]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: WebAssembly Core Specification (W3C Recommendation)
    type: PRIMARY_SOURCE
    url: https://www.w3.org/TR/wasm-core-2/
  - title: WASI - The WebAssembly System Interface (Bytecode Alliance)
    type: PRIMARY_SOURCE
    url: https://wasi.dev/
---

# 🛡️ WASM Sandboxing and Capability-Based Security

## 1. Pergunta Central
> *Como executar plugins e código arbitrário gerado por agentes de IA com inicialização em microssegundos e isolamento de memória matematicamente seguro sem a sobrecarga de containers Docker ou máquinas virtuais?*

---

## 2. O Modelo de Segurança do WebAssembly (WASM/WASI)

1. **Memória Linear Isolada (Isolated Linear Memory)**:
   - Todo módulo WASM opera dentro de um array contíguo de bytes não-extensível sem ponteiros diretos para a memória física do sistema anfitrião.
   - Tentativas de acessar índices fora dos limites disparam imediatamente um trap de hardware seguro (*Memory Out of Bounds Trap*).

2. **Segurança Baseada em Capacidades (Capability-Based Security no WASI)**:
   - Por padrão, um módulo WASM não possui nenhuma syscall (não pode abrir arquivos, ler o relógio ou criar sockets de rede).
   - O host deve conceder explicitamente descritores de capacidade (*Capabilities*) para diretórios específicos:
     ```bash
     wasmtime run --dir=/workspace/sandbox_dir app.wasm
     # O módulo NÃO CONSEGUE enxergar nenhum outro diretório além do concedido
     ```

---

## 3. Comparativo de Overhead: VM vs Docker vs WASM

| Métrica | Máquina Virtual (KVM/QEMU) | Container Docker | WASM Sandbox (Wasmtime/V8) |
|---|---|---|---|
| **Tempo de Inicialização** | $1 - 10\text{ segundos}$ | $200 - 1000\text{ ms}$ | **$< 1\text{ milissegundo}$** |
| **Overhead de Memória** | $> 512\text{ MB}$ | $> 30\text{ MB}$ | **$< 2\text{ MB}$** |
| **Isolamento de Syscalls** | Kernel Completo | Cgroups + Seccomp Filter | **Deny-by-Default com Capacidades Explícitas** |

---

## 4. Related Concepts
- [[Least-Privilege Process Sandboxing and Execution Jail]]
- [[Defensive Sandboxing and Linux Namespaces]]
- [[Docker Container Security and Resource Capping]]
